"""One-off script: creates all tables and, optionally, seeds a demo project
with a few memories so Echo has something to talk about immediately after
deployment.

Usage:
    python scripts/init_db.py            # just create tables
    python scripts/init_db.py --seed     # also insert demo memories
"""
import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import init_db, session_scope  # noqa: E402
from app.core.logging_config import configure_logging, get_logger  # noqa: E402
from app.models.memory import MemoryType  # noqa: E402
from app.schemas.memory import MemoryCreate  # noqa: E402
from app.services.memory_service import MemoryService  # noqa: E402

configure_logging()
logger = get_logger(__name__)

DEMO_PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

DEMO_MEMORIES = [
    dict(
        team_name="Backend",
        memory_type=MemoryType.decision,
        title="Chose FastAPI over Flask",
        content=(
            "We chose FastAPI over Flask for native async support, automatic "
            "OpenAPI documentation, and first-class Pydantic validation, "
            "which matters for our high-throughput task and risk APIs."
        ),
        author="Backend Team",
    ),
    dict(
        team_name="AI",
        memory_type=MemoryType.architecture,
        title="Semantic memory uses ChromaDB + PostgreSQL",
        content=(
            "PostgreSQL is the source of truth for every memory record; "
            "ChromaDB stores embeddings for semantic retrieval only. This "
            "keeps data durable and re-indexable if the vector store is "
            "ever rebuilt."
        ),
        author="AI Team",
    ),
    dict(
        team_name="Frontend",
        memory_type=MemoryType.blocker,
        title="Blocker: Frontend blocked on Backend risk API",
        content=(
            "The Risk Dashboard cannot be finished until the Backend team "
            "ships the /risks endpoint with severity filtering."
        ),
        author="Frontend Team",
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="Insert demo memories after creating tables")
    args = parser.parse_args()

    logger.info("Creating database tables (if they do not already exist)...")
    init_db()
    logger.info("Tables ready.")

    if args.seed:
        logger.info("Seeding demo memories for project %s...", DEMO_PROJECT_ID)
        with session_scope() as db:
            service = MemoryService(db)
            for item in DEMO_MEMORIES:
                service.create_memory(
                    MemoryCreate(project_id=DEMO_PROJECT_ID, metadata={}, **item)
                )
        logger.info("Seed complete.")


if __name__ == "__main__":
    main()
