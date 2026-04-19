from preprocess import build_corpus
from chunking import create_chunks
from embedding_store import build_and_save_index


def main():
    docs = build_corpus()
    chunks = create_chunks(docs)
    build_and_save_index(chunks)
    print("RAG completed successfully.")


if __name__ == "__main__":
    main()