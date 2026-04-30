from retrieval import RAGRetriever

retriever = RAGRetriever("data/processed")

results = retriever.search("browser session crash")

for r in results:
    print("-----")
    print(r)
    