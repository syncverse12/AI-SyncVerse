import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.extraction_routes import router
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = FastAPI(
    title=settings.SERVICE_NAME,
    description=(
        "Stateless microservice that extracts actionable tasks from meeting transcripts. "
        "Uses Groq LLM (llama-3.3-70b) with optional spaCy NER for assignee detection."
    ),
    version=settings.SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "docs": "/docs",
        "health": "/health",
        "endpoint": "POST /extract-tasks",
    }
