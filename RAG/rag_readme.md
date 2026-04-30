# RAG Feature

This module implements a full **Retrieval-Augmented Generation (RAG) pipeline** with **real-time updates**.

It processes bug/issue datasets, converts them into semantic chunks, generates embeddings using Sentence Transformers (GPU supported), stores them in a FAISS vector database, and enables fast semantic retrieval.

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
│   ├── main.py
│   └── __pycache__/
│
├── requirements.txt
├── README.md

   ```

   ---

   ## Data Flow

   ```text
      Raw CSV files
         ↓
      preprocess.py
         ↓
      nking.py
         ↓
      edding_store.py
         ↓
      SS + Pickle files
         ↓
      rieval.py
         ↓
real-time updates (optional)
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

   Handles:

   * noise filtering (logs, stack traces, etc.)
   * embedding generation (SentenceTransformer)
   * FAISS index creation
   * saving processed files

   **Output:**

   * `rag_faiss_index.bin` → vector database
   * `rag_texts.pkl` → searchable texts
   * `rag_chunks.pkl` → metadata / chunk mapping

   ---

   ### `retrieval.py`

   Loads saved FAISS index and performs semantic search.

   **Usage:**

   ```python
   from retrieval import RAGRetriever

   retriever = RAGRetriever("data/processed")
   results = retriever.search("browser crash issue")
   ```

   ---
   ### `realtime_update.py`

   Adds new documents to the system without rebuilding the pipeline.

   **Features:**

   * chunk new data
   * embed only new content
   * update FAISS index
   * persist changes

   ---
   ### `realtime_test.py`

   Simulates adding a new document.

   ```python
   python src/realtime_test.py
   ```

   ---
   ### `retrieval_realtime.py`

   Tests retrieval after real-time updates.

   ```python
   python src/retrieval_realtime.py
   ```

   ### `main.py`

   Runs full pipeline:

   **Run:**

   ```bash
   python src/main.py
   ```

   **Only run if:**

   * raw data changed
   * rebuilding index is needed

   ---

   ## How to run 

   ### 1. Install dependencies

   ```bash
   > pip install -r requirements.txt
   ```

   ### 2. Build RAG pipeline

   ```bash
   > python src/main.py
   ```
   
   ### 3. Test retrieval

   ```bash
   > python src/retrieval_realtime.py
   ```
   
   ### 4. Test real-time update

   ```bash
   > python src/realtime_test.py
   ```

   Then run retrieval again.

   ---

   ## Notes

   * paths are relative to project root (important for running scripts)
