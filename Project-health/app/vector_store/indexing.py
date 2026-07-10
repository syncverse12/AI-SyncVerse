"""
app/vector_store/indexing.py
Upsert documents into Qdrant collections.
"""
from __future__ import annotations

from typing import List
from uuid import uuid5, NAMESPACE_DNS

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.domain import (
    Project,
    VectorDocType,
)
from app.vector_store.qdrant_client import get_qdrant_client

logger = get_logger(__name__)


def _stable_uuid(namespace: str, key: str) -> str:
    """Deterministic UUID so re-indexing is idempotent."""
    return str(uuid5(NAMESPACE_DNS, f"{namespace}:{key}"))


async def index_project(project: Project, embeddings_map: dict[str, list[float]]) -> None:
    """
    Upsert all project documents (requirements, tasks, deliverables, notes)
    into their respective Qdrant collections.

    embeddings_map: {text -> vector}  (pre-computed by embedding_service)
    """
    settings = get_settings()
    client = await get_qdrant_client()

    # ── Requirements ──────────────────────────────────────────────────────────
    req_points: List[PointStruct] = []
    for req in project.requirements:
        vec = embeddings_map.get(req.description)
        if vec is None:
            continue
        req_points.append(PointStruct(
            id=_stable_uuid("req", req.requirement_id),
            vector=vec,
            payload={
                "project_id": project.id,
                "requirement_id": req.requirement_id,
                "type": VectorDocType.REQUIREMENT,
                "text": req.description,
                "weight": req.weight,
            },
        ))

    if req_points:
        await client.upsert(
            collection_name=settings.qdrant_collection_requirements,
            points=req_points,
        )
        logger.info("indexed_requirements", project_id=project.id, count=len(req_points))

    # ── Tasks ─────────────────────────────────────────────────────────────────
    task_points: List[PointStruct] = []
    for task in project.tasks:
        text = f"{task.title}. {task.description}"
        if task.output_summary:
            text += f" {task.output_summary}"
        vec = embeddings_map.get(text)
        if vec is None:
            continue
        task_points.append(PointStruct(
            id=_stable_uuid("task", task.id),
            vector=vec,
            payload={
                "project_id": project.id,
                "task_id": task.id,
                "requirement_id": task.requirement_id,
                "goal_id": task.goal_id,
                "type": VectorDocType.TASK,
                "text": text,
                "status": task.status,
                "priority": task.priority,
                "deadline": task.deadline.isoformat() if task.deadline else None,
            },
        ))

    if task_points:
        await client.upsert(
            collection_name=settings.qdrant_collection_tasks,
            points=task_points,
        )
        logger.info("indexed_tasks", project_id=project.id, count=len(task_points))

    # ── Deliverables ──────────────────────────────────────────────────────────
    del_points: List[PointStruct] = []
    for dlv in project.deliverables:
        text = f"{dlv.title}. {dlv.description}"
        vec = embeddings_map.get(text)
        if vec is None:
            continue
        del_points.append(PointStruct(
            id=_stable_uuid("dlv", dlv.id),
            vector=vec,
            payload={
                "project_id": project.id,
                "deliverable_id": dlv.id,
                "task_id": dlv.task_id,
                "requirement_id": dlv.requirement_id,
                "type": VectorDocType.DELIVERABLE,
                "text": text,
            },
        ))

    if del_points:
        await client.upsert(
            collection_name=settings.qdrant_collection_deliverables,
            points=del_points,
        )
        logger.info("indexed_deliverables", project_id=project.id, count=len(del_points))

    # ── Notes ─────────────────────────────────────────────────────────────────
    note_points: List[PointStruct] = []
    for note in project.notes:
        vec = embeddings_map.get(note.content)
        if vec is None:
            continue
        note_points.append(PointStruct(
            id=_stable_uuid("note", note.id),
            vector=vec,
            payload={
                "project_id": project.id,
                "note_id": note.id,
                "type": VectorDocType.NOTE,
                "text": note.content,
            },
        ))

    if note_points:
        await client.upsert(
            collection_name=settings.qdrant_collection_notes,
            points=note_points,
        )
        logger.info("indexed_notes", project_id=project.id, count=len(note_points))


async def delete_project_vectors(project_id: str) -> None:
    """Remove all vectors for a project from every collection."""
    settings = get_settings()
    client = await get_qdrant_client()
    project_filter = Filter(
        must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
    )
    for col in [
        settings.qdrant_collection_requirements,
        settings.qdrant_collection_tasks,
        settings.qdrant_collection_deliverables,
        settings.qdrant_collection_notes,
    ]:
        await client.delete(collection_name=col, points_selector=project_filter)
    logger.info("deleted_project_vectors", project_id=project_id)
