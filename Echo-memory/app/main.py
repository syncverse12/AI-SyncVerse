"""SyncVerse Echo - FastAPI application entrypoint.

Echo is mounted as an integrated feature of the SyncVerse backend (prefix
`/echo` by default) rather than a standalone service, so it can be included
directly into the main SyncVerse app if desired:

    from app.main import app as echo_app
    main_app.mount("/echo-service", echo_app)

or by simply including `app.api.routes.*` routers into an existing FastAPI
instance.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import echo, health, memory, summary, timeline
from app.core.config import settings
from app.core.database import init_db
from app.core.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s (env=%s)", settings.APP_NAME, __version__, settings.APP_ENV)
    db_kind = "SQLite (fallback)" if settings.using_sqlite_fallback else "PostgreSQL"
    logger.info("Database: %s", db_kind)
    init_db()
    if not settings.has_llm_credentials:
        logger.warning(
            "GOOGLE_API_KEY is not set. Echo will boot, but chat responses "
            "and embeddings will use degraded local fallbacks until it is "
            "configured."
        )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title="SyncVerse Echo",
    description=(
        "Echo - the AI teammate and living memory of every SyncVerse "
        "project. Not a chatbot: an integrated intelligence layer that "
        "remembers project decisions, coordinates teams, advises on "
        "technical choices, and writes documentation."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(echo.router, prefix=settings.API_PREFIX)
app.include_router(memory.router, prefix=settings.API_PREFIX)
app.include_router(timeline.router, prefix=settings.API_PREFIX)
app.include_router(summary.router, prefix=settings.API_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": settings.APP_NAME,
        "version": __version__,
        "docs": "/docs",
        "chat_endpoint": f"{settings.API_PREFIX}/chat",
    }
