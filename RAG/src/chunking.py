from langchain_text_splitters import RecursiveCharacterTextSplitter


def create_chunks(all_documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )

    chunks = []

    for doc in all_documents:
        full_text = f"{doc['title']}\n{doc['content']}"
        split_texts = splitter.split_text(full_text)

        for chunk in split_texts:
            chunks.append({
                "doc_id": doc["doc_id"],
                "text": chunk,
                "source": doc["source"]
            })
    print("successfull chunking")

    return chunks