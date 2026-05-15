from sentence_transformers import SentenceTransformer
from embedding_store import is_noisy_document
import faiss
import pickle
import numpy as np
from chunking import create_chunks
import torch


class RAGUpdater:
    def __init__(self, data_dir="data/processed"):
        self.data_dir = data_dir
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device=device)    # load model
        self.index = faiss.read_index(f"{data_dir}/rag_faiss_index.bin")       # load existing index

        # load stored texts
        with open(f"{data_dir}/rag_texts.pkl", "rb") as f:
            self.texts = pickle.load(f)

        #load chunk
        with open(f"{data_dir}/rag_chunks.pkl", "rb") as f:
            self.chunks = pickle.load(f)

        print("RAG Updater initialized successfully")

    #===================
    # add new documents
    #===================
    def add_document(self, title, content, source="live"):
        # use max existing doc_id + 1 to avoid collisions on reload
        next_id = max((c["doc_id"] for c in self.chunks), default=-1) + 1
        new_doc = {
            "doc_id": next_id,
            "title": title,
            "content": content,
            "source": source
        }

        new_chunks = create_chunks([new_doc])                           # chunk the new document
        new_text = [
            chunk["text"]
            for chunk in new_chunks
            if not is_noisy_document(chunk["text"])  # filter out noisy chunks
        ]
        clean_new_chunks = [
            chunk for chunk in new_chunks
            if not is_noisy_document(chunk["text"])  # keep chunks aligned with new_text
        ]
        new_embeddings = self.model.encode(new_text).astype("float32")  # embed the new chunks
        self.index.add(new_embeddings)                                   # add embeddings to FAISS index
        self.texts.extend(new_text)                                      # add new texts to list
        self.chunks.extend(clean_new_chunks)                             # add aligned chunks to list

        print(f"added {len(new_text)} new chunks ({len(new_chunks) - len(new_text)} filtered as noisy)")
        
    #==============
    # save updates
    #==============
    def save(self):
        faiss.write_index(self.index, f"{self.data_dir}/rag_faiss_index.bin")  # save updated index

        with open(f"{self.data_dir}/rag_texts.pkl", "wb") as f:                # save updated texts
            pickle.dump(self.texts, f)

        with open(f"{self.data_dir}/rag_chunks.pkl", "wb") as f:               # save updated chunks
            pickle.dump(self.chunks, f)

        print("RAG Updater saved successfully")
