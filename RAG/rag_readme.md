# RAG Feature

This module implements a full **Retrieval-Augmented Generation (RAG) pipeline** with **real-time updates**.

It processes bug/issue datasets, converts them into semantic chunks, generates embeddings using Sentence Transformers (GPU supported), stores them in a FAISS vector database, and enables fast semantic retrieval.

---

## Project Structure

```text
AI-SyncVerse/
│
├── data/
│   ├── raw/
│   │   ├── gitbugs/
│   │   │   ├── *_bugs.csv
│   │   │   └── ...
│   │   └── helpdesk-github-tickets/
│   │       └── a_github_issues_overview_dataset.csv
│   │
│   └── processed/
│       ├── rag_faiss_index.bin   # vector database
│       ├── rag_texts.pkl         # chunk texts
│       └── rag_chunks.pkl        # metadata
│
├── src/
│   ├── preprocess.py
│   ├── chunking.py
│   ├── embedding_store.py
│   ├── retrieval.py
│   ├── realtime_update.py
│   ├── realtime_test.py
│   ├── retrieval_realtime.py
│   ├── generator.py
│   ├── main.py
│   ├── main_chat.py
│   └── __pycache__/
│
├── requirements.txt
└── README.md
```

---

## Data Flow

```text
Raw CSV files
      ↓
preprocess.py       →  build unified document corpus
      ↓
chunking.py         →  split docs into semantic chunks
      ↓
embedding_store.py  →  filter noise, embed, build FAISS index
      ↓
FAISS + Pickle files
      ↓
retrieval.py        →  semantic search over the index
      ↓
generator.py        →  LLM answer generation (Groq)
      ↓
real-time updates (optional via realtime_update.py)
```

---

## File Responsibilities

### `preprocess.py`

Builds the unified corpus from both datasets. Includes structured metadata fields (`Status`, `Priority`, `Resolution`, `Issue id`) from gitbugs CSVs so the LLM can reason over them.

**Input:**

* `data/raw/gitbugs/*.csv`
* `data/raw/helpdesk-github-tickets/a_github_issues_overview_dataset.csv`

**Output format:**

```python
{
    "doc_id": int,
    "title": str,
    "content": str,   # includes Status, Priority, Resolution, Description
    "source": str     # "gitbugs" or "github_tickets"
}
```

---

### `chunking.py`

Splits each document into smaller semantic chunks using `RecursiveCharacterTextSplitter` (chunk size: 1000, overlap: 150).

**Output format:**

```python
{
    "doc_id": int,
    "text": str,
    "source": str
}
```

---

### `embedding_store.py`

Handles:

* noise filtering (logs, stack traces, test output, etc.)
* embedding generation (SentenceTransformer `all-MiniLM-L6-v2`, GPU supported)
* FAISS index creation
* saving processed files — `rag_texts.pkl` and `rag_chunks.pkl` are always aligned by index

**Output:**

* `rag_faiss_index.bin` → vector database
* `rag_texts.pkl` → searchable text chunks
* `rag_chunks.pkl` → metadata aligned 1:1 with texts

---

### `retrieval.py`

Loads the saved FAISS index and performs semantic search. Returns structured results including source metadata and distance score.

**Usage:**

```python
from retrieval import RAGRetriever

retriever = RAGRetriever("data/processed")
results = retriever.search("browser crash issue")

for r in results:
    print(r["text"])       # matched chunk text
    print(r["metadata"])   # source, doc_id
    print(r["distance"])   # L2 similarity score
```

---

### `generator.py`

Generates natural language answers using the Groq LLM, given retrieved chunks as context.

---

### `realtime_update.py`

Adds new documents to the system without rebuilding the full pipeline.

**Features:**

* chunks new data
* embeds only new content
* updates FAISS index in place
* keeps `rag_texts.pkl` and `rag_chunks.pkl` aligned
* persists all changes to disk

---

### `main.py`

Runs the full offline pipeline (preprocess → chunk → embed → save).

**Run:**

```bash
python src/main.py
```

**Only run if:**

* raw data has changed
* a full index rebuild is needed

---

### `main_chat.py`

Launches the Echo interactive chat interface.

```bash
python src/main_chat.py
```

---

### `realtime_test.py`

Simulates adding a new live document via `RAGUpdater`.

```bash
python src/realtime_test.py
```

---

### `retrieval_realtime.py`

Tests retrieval after real-time updates have been applied.

```bash
python src/retrieval_realtime.py
```

---

## How to Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Place raw data

```
data/raw/gitbugs/          ← drop all *_bugs.csv files here
data/raw/helpdesk-github-tickets/   ← drop a_github_issues_overview_dataset.csv here
```

### 3. Build RAG pipeline

```bash
python src/main.py
```

### 4. Launch Echo chat

```bash
python src/main_chat.py
```

### 5. (Optional) Test retrieval

```bash
python src/retrieval_realtime.py
```

### 6. (Optional) Test real-time update

```bash
python src/realtime_test.py
```

Then re-run retrieval to verify the update was indexed.

---

## Notes

* All paths are relative to the project root — always run scripts from there, not from inside `src/`
* Re-run `main.py` any time raw data changes or after modifying `preprocess.py` or `embedding_store.py`
* Real-time updates via `add` persist immediately without a full rebuild