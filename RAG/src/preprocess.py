import pandas as pd
import os


def clean_text(text, max_chars=2000):
    text = str(text).strip()
    return text[:max_chars]


def build_corpus(
    gitbugs_path="../data/raw/gitbugs",
    tickets_path = "../data/raw/helpdesk-github-tickets/a_github_issues_overview_dataset.csv"
):
    all_documents = []
    doc_id = 0

    # Process GitBugs Datasets
    for project in os.listdir(gitbugs_path):
        project_path = os.path.join(gitbugs_path, project)

        if os.path.isdir(project_path):
            for file in os.listdir(project_path):
                if file.endswith("_bugs.csv"):
                    file_path = os.path.join(project_path, file)
                    df = pd.read_csv(file_path)

                    for _, row in df.iterrows():
                        if pd.isna(row["Summary"]) or pd.isna(row["Description"]):
                            continue

                        description = clean_text(row["Description"])

                        content = f"""
Description: {description}
"""

                        all_documents.append({
                            "doc_id": doc_id,
                            "title": row["Summary"],
                            "content": content.strip(),
                            "source": "gitbugs"
                        })
                        doc_id += 1

    # Process GitHub Tickets Datasets
    tickets_df = pd.read_csv(tickets_path)

    for _, row in tickets_df.iterrows():
        for i in range(1, 6):
            answer_col = f"answer_{i}"

            if pd.notna(row[answer_col]):
                problem = clean_text(row["body"])
                answer = clean_text(row[answer_col])

                content = f"""
Problem: {problem}

Answer: {answer}
"""

                all_documents.append({
                    "doc_id": doc_id,
                    "title": row["title"],
                    "content": content.strip(),
                    "source": "github_tickets"
                })
                doc_id += 1

    return all_documents