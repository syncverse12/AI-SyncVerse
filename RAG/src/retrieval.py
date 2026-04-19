import faiss
import pickle
from sentence_transformers import SentenceTransformer


class RAGRetriever:
    def __init__(self, data_dir="data"):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.index = faiss.read_index(f"{data_dir}/rag_faiss_index.bin")

        with open(f"{data_dir}/rag_texts.pkl", "rb") as f:
            self.texts = pickle.load(f)

    def search(self, query, k=3):
        query_vector = self.model.encode([query]).astype("float32")
        distances, indices = self.index.search(query_vector, k=k)

        return [self.texts[i] for i in indices[0]]