"""
main_chat.py  ·  Sync-Verse Echo — Interactive CLI
====================================================
Entry point for the Echo AI assistant. Supports:

  ask   — semantic query over the unified knowledge base
  add   — live document ingestion (immediately visible in same session)
  reset — clear conversation history
  quit  — exit

Run from the project root:
    python main_chat.py
"""

import sys
import os
import textwrap
from dotenv import load_dotenv
load_dotenv()

#  path setup 
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from retrieval       import RAGRetriever
from realtime_update import RAGUpdater
from generator       import EchoGenerator, _patch_retriever

#  Display helpers 

WIDTH = 72   # terminal column width for wrapping

def _hr(char: str = "─", label: str = "") -> None:
    if label:
        pad   = (WIDTH - len(label) - 2) // 2
        print(f"{'─' * pad} {label} {'─' * (WIDTH - pad - len(label) - 2)}")
    else:
        print(char * WIDTH)


def _wrap(text: str, indent: int = 0) -> str:
    prefix = " " * indent
    return textwrap.fill(text, width=WIDTH, initial_indent=prefix, subsequent_indent=prefix)


def _print_response(result: dict) -> None:
    """Render the structured [Answer] / [Sources] / [Confidence] output."""
    print()
    _hr(label="ANSWER")
    # wrap each paragraph separately to preserve intentional line breaks
    for para in result["answer"].split("\n"):
        if para.strip():
            print(_wrap(para))
        else:
            print()

    print()
    _hr(label="SOURCES / CITATIONS")
    if result["citations"]:
        for citation in result["citations"]:
            print(_wrap(citation, indent=2))
    else:
        print("  No specific sources identified.")

    print()
    _hr(label="CONFIDENCE SCORE")
    score = result["confidence"]
    bar_len   = int(score / 5)           # 0–20 blocks
    bar       = "█" * bar_len + "░" * (20 - bar_len)
    level     = "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW"
    print(f"  [{bar}] {score:.1f}%  ({level})")
    print()
    _hr()
    print()


def _print_banner() -> None:
    banner = r"""
  ███████╗ ██████╗██╗  ██╗ ██████╗
  ██╔════╝██╔════╝██║  ██║██╔═══██╗
  █████╗  ██║     ███████║██║   ██║
  ██╔══╝  ██║     ██╔══██║██║   ██║
  ███████╗╚██████╗██║  ██║╚██████╔╝
  ╚══════╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝
  Sync-Verse AI Assistant  ·  Living Memory Layer
"""
    print(banner)
    _hr()
    print("  Type  ask   → query the knowledge base")
    print("  Type  add   → ingest a new live update")
    print("  Type  reset → clear conversation history")
    print("  Type  quit  → exit")
    _hr()
    print()


def _prompt_multiline(prompt_text: str) -> str:
    """Collect multi-line input until the user enters an empty line."""
    print(prompt_text)
    lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        lines.append(line)
    return "\n".join(lines).strip()


#  Live ingestion flow

def _add_live_document(updater: RAGUpdater, retriever: RAGRetriever) -> None:
    """
    Prompt the user for a new document, ingest it via RAGUpdater,
    then synchronise the shared index and text lists with the retriever
    so the very next query benefits from the new data.
    """
    _hr(label="ADD LIVE UPDATE")
    title   = input("  Title   : ").strip()
    if not title:
        print("  ⚠  Title cannot be empty. Aborting.\n")
        return

    print("  Content (press Enter twice when done):")
    content = _prompt_multiline("")
    if not content:
        print("  ⚠  Content cannot be empty. Aborting.\n")
        return

    # ingest into updater (mutates updater.index, updater.texts, updater.chunks)
    updater.add_document(title=title, content=content, source="live")

    # ── synchronise retriever to the same live index 
    # Both objects share the FAISS index object by reference after this
    # assignment — no copy, no I/O, O(1) update.
    retriever.index  = updater.index
    retriever.texts  = updater.texts
    retriever.chunks = updater.chunks

    print(f"\n  ✓ Live update '{title}' added. Echo will remember it immediately.\n")
    _hr()
    print()

    # persist to disk in the background so updates survive restarts
    try:
        updater.save()
    except Exception as exc:
        print(f"  ⚠  Could not persist to disk: {exc}")


# ─── Main loop ───────────────────────────────────────────────────────────────

def main() -> None:
    data_dir = os.path.join(_ROOT, "data", "processed")

    print("\nInitialising Echo …", end=" ", flush=True)

    try:
        retriever = RAGRetriever(data_dir)
        _patch_retriever(type(retriever))         # ensure extended search method

        updater   = RAGUpdater(data_dir)
        generator = EchoGenerator(retriever, top_k=5)
    except FileNotFoundError as exc:
        print(f"\n  ✖  Could not load index: {exc}")
        print("  Run `python src/main.py` first to build the RAG pipeline.\n")
        sys.exit(1)

    print("ready.\n")
    _print_banner()

    while True:
        try:
            cmd = input("Echo › ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n\nBye.\n")
            break

        if not cmd:
            continue

        #  ask 
        elif cmd in ("ask", "a"):
            query = input("  Your question: ").strip()
            if not query:
                print("  ⚠  Please enter a question.\n")
                continue

            print("\n  Searching knowledge base …\n")
            try:
                result = generator.generate(query)
                _print_response(result)
            except Exception as exc:
                print(f"\n  ✖  Generation error: {exc}\n")

        # ── add live document 
        elif cmd in ("add", "ingest", "i"):
            _add_live_document(updater, retriever)

        # ── reset conversation history 
        elif cmd in ("reset", "r"):
            generator.reset_history()
            print("  ✓  Conversation history cleared. Starting fresh.\n")

        # ── quit
        elif cmd in ("quit", "exit", "q"):
            print("\nBye.\n")
            break

        # ── inline question (user typed a question directly) 
        elif "?" in cmd or len(cmd.split()) > 3:
            print("\n  Searching knowledge base …\n")
            try:
                result = generator.generate(cmd)
                _print_response(result)
            except Exception as exc:
                print(f"\n  ✖  Generation error: {exc}\n")

        else:
            print(f"  Unknown command '{cmd}'. Type ask / add / reset / quit.\n")


if __name__ == "__main__":
    main()
