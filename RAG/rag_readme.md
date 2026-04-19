# RAG Feature - Graduation Project

This module implements the **RAG (Retrieval-Augmented Generation) feature** for the management system.

It processes issue/bug datasets, converts them into searchable chunks, generates embeddings, stores them in a FAISS vector database, and provides semantic retrieval.

link to the data(..)

---

## Project Structure

```text
RAG feature/
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
│       ├── rag_faiss_index.bin
│       ├── rag_texts.pkl
│       └── rag_chunks.pkl
│
├── src/
│   ├── preprocess.py
│   ├── chunking.py
│   ├── embedding_store.py
│   ├── retrieval.py
│   └── main.py
│
└── requirements.txt
```

---

## Data Flow

```text
Raw CSV files
   ↓
preprocess.py
   ↓
chunking.py
   ↓
embedding_store.py
   ↓
FAISS + Pickle files
   ↓
retrieval.py
```

---

## File Responsibilities

### `preprocess.py`

Builds the unified corpus from both datasets.

**Input:**

* `data/raw/gitbugs/*.csv`
* `data/raw/helpdesk-github-tickets/*.csv`

**Output format:**

```python
{
    "doc_id": int,
    "title": str,
    "content": str,
    "source": str
}
```

---

### `chunking.py`

Splits each document into smaller semantic chunks using `RecursiveCharacterTextSplitter`.

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

Responsible for:

* removing noisy log-like chunks
* generating embeddings
* building FAISS vector DB
* saving processed files

**Saved files:**

* `rag_faiss_index.bin` → vector database
* `rag_texts.pkl` → searchable texts
* `rag_chunks.pkl` → metadata / chunk mapping

---

### `retrieval.py`

Loads saved FAISS index and performs semantic search.

**Usage:**

```python
from retrieval import RAGRetriever

retriever = RAGRetriever("../data/processed")
results = retriever.search("browser crash issue")
```

---

### `main.py`

Runs the full pipeline from preprocessing to saving the vector database.

**Run:**

```bash
python src/main.py
```

---

## Current Status

Completed:

* data preprocessing
* chunking
* embeddings
* FAISS indexing
* retrieval

---

## Next Steps

1. integrate `retrieval.py` with backend API
2. connect retrieved context to LLM response generation
3. expose endpoint for chatbot / search feature
4. optional: add reranking / better filtering

---

## Notes

* processed files are already generated in `data/processed`
* no need to rerun `main.py` unless raw data changes
* use `retrieval.py` directly for backend integration
