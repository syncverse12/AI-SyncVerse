from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import pickle
import torch


def is_noisy_document(text):
    """
    remove noisy documents that contain keywords commonly found in logs, stack traces, or error
    """
    noisy_keywords = [
        "DEBUG", "ERROR -", "stack trace", "core dump", "pid",
        ".java:", "0x", "TEST-UNEXPECTED-FAIL",
        "TEST-START", "TEST-PASS", "TEST-INFO",
        "GECKO(", "logviewer", "intermittent"
        # removed "task " — too broad, filters legitimate content
]

    text_upper = text.upper()
    return any(keyword.upper() in text_upper for keyword in noisy_keywords)


def build_and_save_index(chunks, save_dir="data/processed"):
    """
    embedding chunks
    """
    texts = [chunk["text"] for chunk in chunks]

    # filter both texts AND chunks together so indices stay aligned
    filtered = [
        (chunk, text)
        for chunk, text in zip(chunks, texts)
        if not is_noisy_document(text)
    ]
    clean_chunks = [item[0] for item in filtered]
    clean_texts  = [item[1] for item in filtered]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
    
    embeddings = model.encode(
        clean_texts,
        show_progress_bar=True,
        batch_size=64
    )
    print("Embedding successful")

    embedding_matrix = np.array(embeddings).astype("float32")

    #FAISS index for similarity search
    index = faiss.IndexFlatL2(embedding_matrix.shape[1])
    index.add(embedding_matrix)
    print("Indexing successful")

    # save texts and metadata for retrieval
    faiss.write_index(index, f"{save_dir}/rag_faiss_index.bin")   # vector database

    with open(f"{save_dir}/rag_texts.pkl", "wb") as f:            # actual text chunks
        pickle.dump(clean_texts, f)

    with open(f"{save_dir}/rag_chunks.pkl", "wb") as f:           # metadata aligned with clean_texts
        pickle.dump(clean_chunks, f)
    print("saving successful")
