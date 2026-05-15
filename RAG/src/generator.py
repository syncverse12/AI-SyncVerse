"""
generator.py  ·  Echo — The Generation Layer for Sync-Verse
============================================================
Wraps the Groq API (llama3-8b-8192) to produce grounded, cited,
confidence-scored answers from a hybrid Live + Historical RAG context.

Design principles
-----------------
* Live context (source='live') is always injected BEFORE historical
  context so the LLM sees the most current state of the project first.
* Metadata headers embedded in chunks by preprocess.py are parsed here
  to produce structured citations (Bug #ID, file source, etc.).
* The system prompt enforces strict grounding — no hallucinations.
* Confidence scoring is derived from FAISS L2 distances, not LLM output,
  keeping it objective and reproducible.
"""

import re
import pickle
import numpy as np
import torch
from groq import Groq
from sentence_transformers import SentenceTransformer


# Sync-Verse AI System Prompt 

SYSTEM_PROMPT = """You are Echo, the AI memory and assistant for Sync-Verse — an intelligent project management platform.

Your role is to act as the Living Memory of the project: accurate, precise, and strictly grounded in the retrieved context provided to you.

CORE RULES:
1. Answer ONLY from the provided context. Never invent, infer, or hallucinate facts.
2. If the answer is not present in the context, respond exactly with: "I don't have enough information in the current knowledge base to answer that confidently."
3. Always distinguish between Live Updates (current project state) and Historical Records (bug database archives). Prioritize Live Updates.
4. When citing, extract the exact Bug ID (e.g., Bug #13306629), product name, and source file from the metadata headers in the context.
5. Be professional, concise, and precise. Avoid filler phrases.
6. If multiple pieces of context are relevant, synthesize them coherently — do not just list them.
7. If a Live Update contradicts a Historical Record, always defer to the Live Update.

RESPONSE FORMAT:
You will structure every response as follows:

[ANSWER]
<Your grounded answer here>

[CITATIONS]
<Bullet list of sources used. Format: • Bug #ID — Product | Status | Priority  OR  • Live Update: <title>>

[CONFIDENCE]
<Do not include this — it is appended by the system>

Stay in character as Echo at all times. You are the system's memory, not a general-purpose AI."""


#Utility: parse metadata from chunk text 

_BUG_HEADER_RE = re.compile(
    r"\[Bug #(?P<issue_id>[^\]]+)\]\s*"
    r"Product:\s*(?P<product>[^|]+)\s*\|\s*"
    r"Status:\s*(?P<status>[^|]+)\s*\|\s*"
    r"Priority:\s*(?P<priority>[^|]+)\s*\|\s*"
    r"Resolution:\s*(?P<resolution>[^\n]+)",
    re.IGNORECASE,
)

_LIVE_HEADER_RE = re.compile(r"\[LIVE UPDATE\]", re.IGNORECASE)


def _parse_citation(chunk_text: str, source: str) -> str:
    """
    Extract a human-readable citation string from a chunk's text.
    Returns a formatted bullet string.
    """
    if source == "live" or _LIVE_HEADER_RE.search(chunk_text):
        # extract live update title if present
        title_match = re.search(r"Title:\s*(.+)", chunk_text)
        title = title_match.group(1).strip() if title_match else "Live Update"
        return f"• [LIVE] {title}"

    m = _BUG_HEADER_RE.search(chunk_text)
    if m:
        return (
            f"• Bug #{m.group('issue_id').strip()} — "
            f"{m.group('product').strip()} | "
            f"Status: {m.group('status').strip()} | "
            f"Priority: {m.group('priority').strip()}"
        )

    # fallback for github_tickets or unstructured chunks
    return f"• Historical Record ({source})"


def _l2_to_confidence(distances: list[float]) -> float:
    """
    Convert FAISS L2 distances to a 0–100 confidence score.

    Lower L2 distance = more similar = higher confidence.
    We use an exponential decay so very small distances map near 100%
    while large distances gracefully decay toward 0%.
    """
    if not distances:
        return 0.0
    avg_dist = float(np.mean(distances))
    # scale factor tuned for all-MiniLM-L6-v2 typical distance range (0–4)
    score = 100.0 * np.exp(-0.5 * avg_dist)
    return round(min(max(score, 0.0), 100.0), 1)


# ─EchoGenerator

class EchoGenerator:
    """
    Generation layer for Sync-Verse's Echo assistant.

    Parameters
    ----------
    retriever : RAGRetriever
        An initialised retriever that exposes `search_with_metadata(query, k)`.
        This method is added to RAGRetriever by this module (see below).
    top_k : int
        Number of chunks to retrieve per query (default 5).
    model : str
        Groq model string to use (default: llama3-8b-8192).
    """
    def __init__(self, retriever, top_k: int = 5, model: str = "llama-3.1-8b-instant"):
        self.retriever = retriever
        self.top_k     = top_k
        self.client    = Groq()   # reads GROQ_API_KEY from environment
        self.model     = model
        self.conversation_history: list[dict] = []

    # context assembly 

    def _assemble_context(self, results: list[dict]) -> tuple[str, list[str], float]:
        """
        Split results into Live and Historical buckets, build the context
        block injected into the prompt, and collect citation strings.

        Returns
        -------
        context_block : str   — formatted context for the prompt
        citations     : list  — citation strings for the output
        confidence    : float — confidence score derived from distances
        """
        live_chunks       = [r for r in results if r["source"] == "live"]
        historical_chunks = [r for r in results if r["source"] != "live"]

        context_parts: list[str] = []
        citations:     list[str] = []
        distances:     list[float] = [r["distance"] for r in results]

        #  Live context (highest priority)
        if live_chunks:
            context_parts.append("=== LIVE UPDATES (Current Project State) ===")
            for i, chunk in enumerate(live_chunks, 1):
                context_parts.append(f"[Live-{i}]\n{chunk['text']}")
                citations.append(_parse_citation(chunk["text"], "live"))

        #  Historical context 
        if historical_chunks:
            context_parts.append("\n=== HISTORICAL RECORDS (Bug Database Archive) ===")
            for i, chunk in enumerate(historical_chunks, 1):
                context_parts.append(f"[Hist-{i}]\n{chunk['text']}")
                citations.append(_parse_citation(chunk["text"], chunk["source"]))

        context_block = "\n\n".join(context_parts)
        confidence    = _l2_to_confidence(distances)

        # deduplicate citations while preserving order
        seen = set()
        unique_citations = []
        for c in citations:
            if c not in seen:
                seen.add(c)
                unique_citations.append(c)

        return context_block, unique_citations, confidence

    #  main generation method

    def generate(self, query: str) -> dict:
        """
        Retrieve relevant context and generate a grounded answer.

        Parameters
        ----------
        query : str — the user's natural language question

        Returns
        -------
        dict with keys:
            answer     : str   — the LLM's answer section
            citations  : list  — formatted citation strings
            confidence : float — 0–100 confidence score
            raw        : str   — full raw LLM output (for debugging)
        """
        # 1. retrieve with metadata
        results = self.retriever.search_with_metadata(query, k=self.top_k)

        if not results:
            return {
                "answer":     "I don't have enough information in the current knowledge base to answer that confidently.",
                "citations":  [],
                "confidence": 0.0,
                "raw":        "",
            }

        # 2. assemble context
        context_block, citations, confidence = self._assemble_context(results)

        # 3. build user message
        user_message = (
            f"Use ONLY the following retrieved context to answer the question.\n\n"
            f"{context_block}\n\n"
            f"---\n"
            f"Question: {query}"
        )

        # 4. maintain multi-turn history
        self.conversation_history.append({"role": "user", "content": user_message})

        # 5. call the Groq API (OpenAI-compatible chat completions interface)
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *self.conversation_history,
            ],
        )

        raw_output = response.choices[0].message.content

        # 6. persist assistant turn in history
        self.conversation_history.append({"role": "assistant", "content": raw_output})

        # 7. parse [ANSWER] block from LLM output
        answer_match = re.search(
            r"\[ANSWER\]\s*(.*?)(?=\[CITATIONS\]|\[CONFIDENCE\]|$)",
            raw_output,
            re.DOTALL | re.IGNORECASE,
        )
        answer = answer_match.group(1).strip() if answer_match else raw_output.strip()

        return {
            "answer":     answer,
            "citations":  citations,
            "confidence": confidence,
            "raw":        raw_output,
        }

    def reset_history(self):
        """Clear multi-turn conversation history (start fresh session)."""
        self.conversation_history = []
        print("Conversation history cleared.")


# ─── RAGRetriever extension: search_with_metadata ──────────────────────
# We monkey-patch the existing RAGRetriever at import time so generator.py
# remains the only file that needs to change. This keeps retrieval.py intact.

def _search_with_metadata(self, query: str, k: int = 5) -> list[dict]:
    """
    Extended search that returns chunks with source metadata and L2 distances.

    Each result dict:
        text     : str   — the chunk text
        source   : str   — 'live', 'gitbugs', 'github_tickets', etc.
        distance : float — raw FAISS L2 distance (lower = more similar)
        doc_id   : int   — originating document ID
    """
    query_vector = self.model.encode([query]).astype("float32")
    distances, indices = self.index.search(query_vector, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(self.texts):
            continue

        text   = self.texts[idx]
        source = "unknown"
        doc_id = -1

        # cross-reference chunk metadata if available
        if hasattr(self, "chunks") and idx < len(self.chunks):
            chunk  = self.chunks[idx]
            if isinstance(chunk, dict):
              source = chunk.get("source", "unknown")
              doc_id = chunk.get("doc_id", -1)
            else:
            # infer source from embedded header text as fallback
              if _LIVE_HEADER_RE.search(text):
                 source = "live"
              elif _BUG_HEADER_RE.search(text):
                 source = "gitbugs"            

        results.append({
            "text":     text,
            "source":   source,
            "distance": float(dist),
            "doc_id":   doc_id,
        })

    return results


def _patch_retriever(retriever_class):
    """Attach search_with_metadata to RAGRetriever if not already present."""
    if not hasattr(retriever_class, "search_with_metadata"):
        retriever_class.search_with_metadata = _search_with_metadata

    # also ensure chunks are loaded (retrieval.py only loads texts by default)
    original_init = retriever_class.__init__

    def patched_init(self, data_dir="data/processed"):
        original_init(self, data_dir)
        chunks_path = f"{data_dir}/rag_chunks.pkl"
        try:
            with open(chunks_path, "rb") as f:
                self.chunks = pickle.load(f)
        except FileNotFoundError:
            self.chunks = []

    retriever_class.__init__ = patched_init


# apply patch on import
try:
    from retrieval import RAGRetriever
    _patch_retriever(RAGRetriever)
except ImportError:
    pass  # will be patched when retrieval.py is importable
