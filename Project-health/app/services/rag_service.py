"""
app/services/rag_service.py

Layer 3a - Build semantic context using in-memory similarity before calling the LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List

import math

from app.core.logging import get_logger
from app.models.domain import (
    AlignmentScoreResult,
    HealthScoreResult,
    Priority,
    Project,
    TaskStatus,
)
from app.services.embedding_service import embed_text, embed_texts
logger = get_logger(__name__)


@dataclass
class RAGContext:
    """Assembled context ready to be injected into the LLM prompt."""
    retrieved_requirements: List[dict] = field(default_factory=list)
    retrieved_tasks: List[dict] = field(default_factory=list)
    retrieved_deliverables: List[dict] = field(default_factory=list)
    delayed_tasks_summary: List[dict] = field(default_factory=list)
    goal_progress_summary: List[dict] = field(default_factory=list)
    health_score: float = 0.0
    alignment_score: float = 0.0
    low_alignment_requirements: List[dict] = field(default_factory=list)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if len(a) != len(b):
        raise ValueError("Embedding dimensions do not match.")

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


async def build_rag_context(
    project: Project,
    health_result: HealthScoreResult,
    alignment_result: AlignmentScoreResult,
) -> RAGContext:
    """
    Construct a semantic query from project weak points, then
    retrieve the most relevant requirements, tasks, and deliverables
    using in-memory cosine similarity.
    """
    today = date.today()

    # ── Build composite query from pain-points ────────────────────────────────
    query_parts: List[str] = [
        f"Project: {project.name}. {project.description}",
    ]

    # Add low-alignment requirements to the query signal
    low_align_reqs = [
        r for r in alignment_result.requirement_details
        if r.alignment_score < 0.75
    ]
    for r in low_align_reqs:
        query_parts.append(f"Misaligned requirement: {r.description}")

    # Add delayed task titles
    for dt in health_result.delayed_tasks[:5]:
        query_parts.append(f"Delayed task: {dt.title}")

    # Add goal progress for goals below 50%
    for gp in health_result.goal_details:
        if gp.progress < 0.5:
            query_parts.append(f"Low-progress goal: {gp.title}")

    composite_query = " | ".join(query_parts)
    logger.debug("rag_query", query_preview=composite_query[:200])

    # Build embeddings for all project content
    query_vec = await embed_text(composite_query)

    requirement_embeddings = await embed_texts(
        [r.description for r in project.requirements]
    )

    task_texts = []
    for task in project.tasks:
        text = f"{task.title}. {task.description}"
        if task.output_summary:
            text += f" {task.output_summary}"
        task_texts.append(text)

    task_embeddings = await embed_texts(task_texts)

    deliverable_texts = [
        f"{d.title}. {d.description}"
        for d in project.deliverables
    ]
    deliverable_embeddings = await embed_texts(deliverable_texts)
    TOP_K = 8

    # Requirements
    req_hits = sorted(
        [
            {
                "score": _cosine_similarity(query_vec, emb),
                "item": req,
            }
            for req, emb in zip(project.requirements, requirement_embeddings)
        ],
        key=lambda x: x["score"],
        reverse=True,
    )[:TOP_K]

    # Tasks
    task_hits = sorted(
        [
            {
                "score": _cosine_similarity(query_vec, emb),
                "item": task,
            }
            for task, emb in zip(project.tasks, task_embeddings)
        ],
        key=lambda x: x["score"],
        reverse=True,
    )[:TOP_K]

    # Deliverables
    deliverable_hits = sorted(
        [
            {
                "score": _cosine_similarity(query_vec, emb),
                "item": deliverable,
            }
            for deliverable, emb in zip(project.deliverables, deliverable_embeddings)
        ],
        key=lambda x: x["score"],
        reverse=True,
    )[:TOP_K]

    # ── Delayed tasks detail ──────────────────────────────────────────────────
    delayed_summary = [
        {
            "task_id": dt.task_id,
            "title": dt.title,
            "delay_days": dt.delay_days,
            "priority": dt.priority,
            "delay_contribution": dt.delay_contribution,
        }
        for dt in health_result.delayed_tasks
    ]

    # ── Goal progress summary ─────────────────────────────────────────────────
    goal_summary = [
        {
            "goal_id": gp.goal_id,
            "title": gp.title,
            "progress_pct": round(gp.progress * 100, 1),
            "completed": gp.completed_tasks,
            "total": gp.total_tasks,
        }
        for gp in health_result.goal_details
    ]

    ctx = RAGContext(
        retrieved_requirements=[
        {
            "requirement_id": h["item"].requirement_id,
            "text": h["item"].description,
            "score": round(h["score"], 3),
            "weight": h["item"].weight,
        }
        for h in req_hits
    ],

    retrieved_tasks=[
        {
            "task_id": h["item"].id,
            "text": f"{h['item'].title}. {h['item'].description}",
            "score": round(h["score"], 3),
            "status": h["item"].status,
            "priority": h["item"].priority,
            "goal_id": h["item"].goal_id,
            "requirement_id": h["item"].requirement_id,
        }
        for h in task_hits
    ],

    retrieved_deliverables=[
        {
            "deliverable_id": h["item"].id,
            "text": f"{h['item'].title}. {h['item'].description}",
            "score": round(h["score"], 3),
            "task_id": h["item"].task_id,
            "requirement_id": h["item"].requirement_id,
        }
        for h in deliverable_hits
    ],
        delayed_tasks_summary=delayed_summary,
        goal_progress_summary=goal_summary,
        health_score=health_result.health_score,
        alignment_score=alignment_result.alignment_score,
        low_alignment_requirements=[
            {
                "requirement_id": r.requirement_id,
                "description": r.description,
                "alignment_score": r.alignment_score,
                "alert": r.alert,
            }
            for r in low_align_reqs
        ],
    )

    logger.info(
        "rag_context_built",
        project_id=project.id,
        req_hits=len(req_hits),
        task_hits=len(task_hits),
        deliverable_hits=len(deliverable_hits),
    )
    return ctx
