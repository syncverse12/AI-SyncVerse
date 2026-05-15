import pandas as pd
import os


def clean_text(text, max_chars=2000):
    text = str(text).strip()
    return text[:max_chars]


def build_corpus(
    gitbugs_path="data/raw/gitbugs",
    tickets_path="data/raw/helpdesk-github-tickets/a_github_issues_overview_dataset.csv"
):
    all_documents = []
    doc_id = 0

    #=========================
    # Process GitBugs Datasets
    #=========================
    for file in os.listdir(gitbugs_path):
        file_path = os.path.join(gitbugs_path, file)
        df = pd.read_csv(file_path)

        # safety check for required columns
        if "Summary" not in df.columns or "Description" not in df.columns:
            continue

        # remove bad rows
        df = df.dropna(subset=["Summary", "Description"])
        df = df[
            (df["Summary"].str.strip() != "") &
            (df["Description"].str.strip() != "")
        ]

        # derive the product name from the filename (e.g. "SeaMonkey_bugs.csv" → "SeaMonkey")
        product_name = os.path.splitext(file)[0].replace("_bugs", "").replace("_", " ").title()

        # iterate through rows and create documents
        for row in df.itertuples(index=False):
            description = clean_text(row.Description)

            # ── Metadata header ──────────────────────────────────────────────
            # Embedding structured metadata directly into the chunk text means
            # the LLM can extract Issue ID, Status, and Priority for citations
            # without needing a separate database lookup at generation time.
            # ─────────────────────────────────────────────────────────────────
            issue_id  = getattr(row, "Issue_id",  None) or getattr(row, "Issue id",  "N/A")
            status    = getattr(row, "Status",    "N/A")
            priority  = getattr(row, "Priority",  "N/A")
            resolution = getattr(row, "Resolution", "N/A")

            metadata_header = (
                f"[Bug #{issue_id}] Product: {product_name} | "
                f"Status: {status} | Priority: {priority} | Resolution: {resolution}"
            )

            content = f"{metadata_header}\nDescription: {description}"

            all_documents.append({
                "doc_id":   doc_id,
                "title":    row.Summary,
                "content":  content,
                "source":   "gitbugs",
                # store structured metadata separately for retriever enrichment
                "metadata": {
                    "issue_id":   str(issue_id),
                    "product":    product_name,
                    "status":     str(status),
                    "priority":   str(priority),
                    "resolution": str(resolution),
                    "file":       file,
                }
            })

            doc_id += 1

    #=======================
    # Process GitHub Tickets
    #=======================
    tickets_df = pd.read_csv(tickets_path)

    # keep only needed columns
    answer_cols = [f"answer_{i}" for i in range(1, 6)]
    needed_cols = ["title", "body"] + answer_cols
    tickets_df = tickets_df[needed_cols]

    # drop rows where body and title are missing or empty
    tickets_df = tickets_df.dropna(subset=["body", "title"])
    tickets_df = tickets_df[
        (tickets_df["body"].str.strip() != "") &
        (tickets_df["title"].str.strip() != "")
    ]

    # flatten answers
    tickets_df = tickets_df.melt(
        id_vars=["title", "body"],
        value_vars=answer_cols,
        value_name="answer"
    )

    # remove empty answers
    tickets_df = tickets_df.dropna(subset=["answer"])
    tickets_df = tickets_df[tickets_df["answer"].str.strip() != ""]

    # iterate through rows and create documents
    for row in tickets_df.itertuples(index=False):
        problem = clean_text(row.body)
        answer  = clean_text(row.answer)

        content = f"""Problem: {problem}

Answer: {answer}"""

        all_documents.append({
            "doc_id":   doc_id,
            "title":    row.title,
            "content":  content.strip(),
            "source":   "github_tickets",
            "metadata": {
                "issue_id": "N/A",
                "product":  "GitHub Tickets",
                "file":     "a_github_issues_overview_dataset.csv",
            }
        })
        doc_id += 1

    return all_documents
