import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from AI_services.app.database.session import init_db
from AI_services.app.database.redis_client import get_redis, close_redis
from AI_services.app.realtime.meeting_consumer import meeting_end_consumer

from AI_services.app.routes.auth_routes import router as auth_router
from AI_services.app.routes.meeting_routes import router as meeting_router
from AI_services.app.routes.employee_routes import router as employee_router
from AI_services.app.routes.summary_routes import router as summary_router
from AI_services.app.routes.stats_routes import router as stats_router
from AI_services.app.websocket.audio_ws import router as audio_ws_router
from AI_services.app.websocket.dashboard_ws import router as dashboard_ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_task
    logger.info("Starting Meeting AI service...")
    await init_db()
    await get_redis()
    _consumer_task = asyncio.create_task(meeting_end_consumer())
    logger.info("Meeting AI service ready.")
    yield
    if _consumer_task:
        _consumer_task.cancel()
    await close_redis()
    logger.info("Meeting AI service shut down.")


app = FastAPI(
    title="AI Meeting Intelligence System",
    description=(
        "Real-time meeting transcription, translation, "
        "task extraction, and employee dashboard delivery."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(meeting_router)
app.include_router(employee_router)
app.include_router(summary_router)
app.include_router(stats_router)
app.include_router(audio_ws_router)
app.include_router(dashboard_ws_router)


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "service": "AI Meeting Intelligence System",
        "version": "1.0.0",
    }
