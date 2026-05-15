import faiss
import pickle
from sentence_transformers import SentenceTransformer
import torch


class RAGRetriever:
    def __init__(self, data_dir="data/processed"):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        self.index = faiss.read_index(f"{data_dir}/rag_faiss_index.bin")

        with open(f"{data_dir}/rag_texts.pkl", "rb") as f:
            self.texts = pickle.load(f)

        # load chunk metadata so source/doc_id are available at search time
        with open(f"{data_dir}/rag_chunks.pkl", "rb") as f:
            self.chunks = pickle.load(f)

    def search(self, query, k=3):
        query_vector = self.model.encode([query]).astype("float32")
        distances, indices = self.index.search(query_vector, k=k)

        results = []
        for idx, dist in zip(indices[0], distances[0]):
            results.append({
                "text": self.texts[idx],
                "metadata": self.chunks[idx],   # source, doc_id, etc.
                "distance": float(dist)
            })
        return results