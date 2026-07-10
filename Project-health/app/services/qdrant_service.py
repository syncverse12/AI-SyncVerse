"""
app/services/qdrant_service.py
Orchestrates: embed all project texts → upsert into Qdrant.
Called on every project create/update/re-index.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.models.domain import Project
from app.services.embedding_service import build_embeddings_map
from app.vector_store.indexing import index_project, delete_project_vectors

logger = get_logger(__name__)


def _collect_texts(project: Project) -> list[str]:
    """Gather every piece of text that needs an embedding."""
    texts: list[str] = []

    for req in project.requirements:
        texts.append(req.description)

    for task in project.tasks:
        t = f"{task.title}. {task.description}"
        if task.output_summary:
            t += f" {task.output_summary}"
        texts.append(t)

    for dlv in project.deliverables:
        texts.append(f"{dlv.title}. {dlv.description}")

    for note in project.notes:
        texts.append(note.content)

    return texts


async def index_full_project(project: Project, force_reindex: bool = False) -> None:
    """
    Full re-index pipeline:
    1. Collect all texts
    2. Batch-embed (with cache)
    3. Upsert into Qdrant collections
    """
    logger.info("qdrant_index_start", project_id=project.id, force=force_reindex)

    if force_reindex:
        await delete_project_vectors(project.id)

    texts = _collect_texts(project)
    if not texts:
        logger.warning("no_texts_to_index", project_id=project.id)
        return

    embeddings_map = await build_embeddings_map(texts)
    await index_project(project, embeddings_map)

    logger.info(
        "qdrant_index_complete",
        project_id=project.id,
        vectors=len(embeddings_map),
    )
