import numpy as np

from models import embedding_model, cross_encoder


def calculate_client_alignment(tasks, requirements):

    # handle empty input
    if len(tasks) == 0 or len(requirements) == 0:
        return {"alignment_score": 0, "details": []}

    # extract texts
    task_texts = [t["text"] for t in tasks]
    requirement_texts = [r["text"] for r in requirements]

    # generate embeddings
    task_embeddings = embedding_model.encode(task_texts, normalize_embeddings=True)
    req_embeddings = embedding_model.encode(requirement_texts, normalize_embeddings=True)

    total_priority = 0.0
    covered_priority = 0.0

    details = []

    
    TOP_K = 5                # retrieval depth
    RERANK_WEIGHT = 0.7      # reranking weight
    RETRIEVAL_WEIGHT = 0.3   # embedding retrieval weight

    # process each requirement
    for i, requirement in enumerate(requirements):

        req_embedding = req_embeddings[i]

        # cosine similarity retrieval
        similarities = np.dot(task_embeddings, req_embedding)

        # retrieve top-k most relevant tasks
        top_indices = np.argsort(similarities)[-TOP_K:]

        candidate_pairs = []

        # create requirement-task pairs
        for idx in top_indices:
            candidate_pairs.append(
                (
                    requirement["text"],
                    tasks[idx]["text"]
                )
            )

        # semantic reranking
        rerank_scores = cross_encoder.predict(candidate_pairs)

        # best reranked task
        best_local_idx = np.argmax(rerank_scores)

        best_task_index = top_indices[best_local_idx]

        best_task = tasks[best_task_index]

        # raw reranker score
        raw_rerank_score = float(rerank_scores[best_local_idx])

        # sigmoid normalization
        rerank_score = 1 / (1 + np.exp(-raw_rerank_score))

        # retrieval similarity score
        retrieval_score = float(similarities[best_task_index])

        # normalize cosine similarity from [-1,1] to [0,1]
        retrieval_score = (retrieval_score + 1) / 2

        # final hybrid similarity
        final_similarity = (
            (RERANK_WEIGHT * rerank_score)
            +
            (RETRIEVAL_WEIGHT * retrieval_score)
        )

        # clamp score
        final_similarity = max(0.0, min(final_similarity, 1.0))

        priority = requirement["priority"]

        total_priority += priority

        # weighted contribution
        weighted_contribution = final_similarity * priority

        covered_priority += weighted_contribution

        # explainability details
        details.append({
            "requirement": requirement["text"],
            "best_task": best_task["text"],
            "retrieval_score": round(retrieval_score, 4),
            "rerank_score": round(rerank_score, 4),
            "final_similarity": round(final_similarity, 4),
            "priority": priority,
            "weighted_contribution": round(weighted_contribution, 4),
            "matched": final_similarity >= 0.6
        })

    # final alignment percentage
    final_score = (covered_priority / total_priority) * 100

    final_score = round(final_score, 2)

    return {"alignment_score": final_score, "details": details}