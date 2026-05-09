from sentence_transformers import SentenceTransformer
from sentence_transformers import CrossEncoder


# embedding model
embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# semantic reranker model
cross_encoder = CrossEncoder(
    "cross-encoder/stsb-roberta-base"
)