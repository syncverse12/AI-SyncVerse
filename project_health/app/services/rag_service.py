"""
app/services/rag_service.py
Layer 3a – RAG pipeline: build rich context from Qdrant before calling LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.domain import (
    AlignmentScoreResult,
    HealthScoreResult,
    Priority,
    Project,
    TaskStatus,
)
from app.services.embedding_service import embed_text
from app.vector_store.retrieval import search_similar

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


def _payload_text(point) -> str:
    return point.payload.get("text", "") if point.payload else ""


async def build_rag_context(
    project: Project,
    health_result: HealthScoreResult,
    alignment_result: AlignmentScoreResult,
) -> RAGContext:
    """
    Construct the retrieval query from project weak-points, then
    pull semantically relevant documents from every Qdrant collection.
    """
    settings = get_settings()
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

    query_vec = await embed_text(composite_query)

    # ── Retrieve from Qdrant ──────────────────────────────────────────────────
    req_hits = await search_similar(
        collection=settings.qdrant_collection_requirements,
        query_vector=query_vec,
        project_id=project.id,
        top_k=settings.rag_top_k,
        score_threshold=settings.rag_score_threshold,
    )

    task_hits = await search_similar(
        collection=settings.qdrant_collection_tasks,
        query_vector=query_vec,
        project_id=project.id,
        top_k=settings.rag_top_k,
        score_threshold=settings.rag_score_threshold,
    )

    deliverable_hits = await search_similar(
        collection=settings.qdrant_collection_deliverables,
        query_vector=query_vec,
        project_id=project.id,
        top_k=settings.rag_top_k // 2,
        score_threshold=settings.rag_score_threshold,
    )

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
            {"text": _payload_text(h), "score": round(h.score, 3), **( h.payload or {})}
            for h in req_hits
        ],
        retrieved_tasks=[
            {"text": _payload_text(h), "score": round(h.score, 3), **( h.payload or {})}
            for h in task_hits
        ],
        retrieved_deliverables=[
            {"text": _payload_text(h), "score": round(h.score, 3), **( h.payload or {})}
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
