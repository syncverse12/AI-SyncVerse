"""
app/services/alignment_service.py
Layer 2 – Client Alignment Score (semantic requirement matching via Qdrant).
"""
from __future__ import annotations

from typing import List, Set

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.domain import (
    AlignmentAlert,
    AlignmentScoreResult,
    Project,
    RequirementAlignment,
    RiskLevel,
)
from app.services.embedding_service import embed_text
from app.vector_store.retrieval import search_similar, fetch_all_by_project

logger = get_logger(__name__)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


async def compute_alignment_score(project: Project) -> AlignmentScoreResult:
    """
    For each requirement, embed it and query Qdrant tasks_collection
    to find the top-k semantically matching tasks.
    Weight-average similarity scores to produce a final alignment score.
    """
    settings = get_settings()
    tasks_col = settings.qdrant_collection_tasks

    alerts: List[AlignmentAlert] = []
    req_details: List[RequirementAlignment] = []
    total_weight = sum(r.weight for r in project.requirements) or 1.0

    # Collect all task IDs that ARE matched to at least one requirement
    matched_task_ids: Set[str] = set()

    for req in project.requirements:
        req_vec = await embed_text(req.description)

        hits = await search_similar(
            collection=tasks_col,
            query_vector=req_vec,
            project_id=project.id,
            top_k=settings.rag_top_k,
            score_threshold=0.0,  # retrieve all; we'll score manually
        )

        if not hits:
            # No tasks at all → drift
            alerts.append(AlignmentAlert(
                level=RiskLevel.CRITICAL,
                message=f"No tasks found for requirement '{req.requirement_id}' – Drift Detected",
                affected_ids=[req.requirement_id],
            ))
            req_details.append(RequirementAlignment(
                requirement_id=req.requirement_id,
                description=req.description,
                weight=req.weight,
                alignment_score=0.0,
                matched_task_ids=[],
                alert="drift_detected",
            ))
            continue

        scores = [h.score for h in hits]
        avg_similarity = sum(scores) / len(scores)
        hit_task_ids = [
            h.payload.get("task_id", "") for h in hits if h.payload
        ]
        matched_task_ids.update(hit_task_ids)

        alert_str: str | None = None
        if avg_similarity < 0.50:
            alerts.append(AlignmentAlert(
                level=RiskLevel.CRITICAL,
                message=(
                    f"Critical misalignment for requirement '{req.requirement_id}' "
                    f"(score={avg_similarity:.2f})"
                ),
                affected_ids=[req.requirement_id],
            ))
            alert_str = "critical_misalignment"
        elif avg_similarity < 0.75:
            alerts.append(AlignmentAlert(
                level=RiskLevel.MEDIUM,
                message=(
                    f"Risk: partial alignment for requirement '{req.requirement_id}' "
                    f"(score={avg_similarity:.2f})"
                ),
                affected_ids=[req.requirement_id],
            ))
            alert_str = "risk"

        req_details.append(RequirementAlignment(
            requirement_id=req.requirement_id,
            description=req.description,
            weight=req.weight,
            alignment_score=round(avg_similarity, 4),
            matched_task_ids=hit_task_ids,
            alert=alert_str,
        ))

    # ── Alignment Score ───────────────────────────────────────────────────────
    weighted_sum = sum(
        r.weight * r.alignment_score for r in req_details
    )
    raw_alignment = weighted_sum / total_weight
    alignment_score = _clamp(raw_alignment * 100)

    # ── Orphan tasks (tasks not matched to any requirement) ───────────────────
    all_task_records = await fetch_all_by_project(tasks_col, project.id)
    all_task_ids = {
        r.payload.get("task_id", "") for r in all_task_records if r.payload
    }
    orphan_ids = list(all_task_ids - matched_task_ids)

    if orphan_ids:
        alerts.append(AlignmentAlert(
            level=RiskLevel.MEDIUM,
            message=f"Orphan work detected: {len(orphan_ids)} task(s) not linked to any requirement",
            affected_ids=orphan_ids,
        ))

    logger.info(
        "alignment_score_computed",
        project_id=project.id,
        alignment_score=round(alignment_score, 2),
        alerts=len(alerts),
        orphans=len(orphan_ids),
    )

    return AlignmentScoreResult(
        project_id=project.id,
        alignment_score=round(alignment_score, 2),
        requirement_details=req_details,
        alerts=alerts,
        orphan_task_ids=orphan_ids,
    )
