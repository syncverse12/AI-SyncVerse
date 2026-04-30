from sentence_transformers import SentenceTransformer
from embedding_store import is_noisy_document
import faiss
import pickle
import numpy as np
from chunking import create_chunks


class RAGUpdater:
    def __init__(self, data_dir="data/processed"):
        self.data_dir = data_dir
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device="cuda")    # load model
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
        new_doc = {
            "doc_id": len(self.chunks),
            "title": title,
            "content": content,
            "source": source
        }

        new_chunks = create_chunks([new_doc])                           # chunk the new document
        new_text = [
            chunk["text"]
            for chunk in new_chunks
            if not is_noisy_document(chunk["text"])  # filter out noisy chunks
        ]                                                               # extract text from chunks
        new_embeddings = self.model.encode(new_text).astype("float32")  # embed the new chunks
        self.index.add(new_embeddings)                                  # add embeddings to FAISS index
        self.texts.extend(new_text)                                     # add new texts to list
        self.chunks.extend(new_chunks)                                  # add new chunks to list

        print(f"added {len(new_chunks)} new chunks")
        
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
