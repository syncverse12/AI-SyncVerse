"""
Background subscriber that listens on Redis pub/sub for "meeting:end:{id}" events
and triggers the MeetingEndPipeline asynchronously without blocking the WebSocket.
"""
import asyncio
import json
import logging
import aioredis
from AI_services.app.config import settings
from AI_services.app.database.session import AsyncSessionLocal
from AI_services.app.pipelines.meeting_end_pipeline import meeting_end_pipeline

logger = logging.getLogger(__name__)


async def meeting_end_consumer():
    """
    Subscribes to Redis channel pattern "meeting:end:*".
    For each event, runs the full post-meeting pipeline in a fresh DB session.
    """
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()

    await pubsub.psubscribe("meeting:end:*")
    logger.info("[Consumer] Subscribed to meeting:end:* events")

    async for message in pubsub.listen():
        if message["type"] not in ("pmessage", "message"):
            continue
        try:
            payload = json.loads(message["data"])
            meeting_id = payload.get("meeting_id")
            if not meeting_id:
                continue
            logger.info(f"[Consumer] Received end signal for meeting {meeting_id}")
            asyncio.create_task(_run_pipeline(meeting_id))
        except Exception as e:
            logger.error(f"[Consumer] Error processing message: {e}")


async def _run_pipeline(meeting_id: str):
    async with AsyncSessionLocal() as db:
        try:
            await meeting_end_pipeline.run(meeting_id, db)
        except Exception as e:
            logger.error(f"[Consumer] Pipeline error for meeting {meeting_id}: {e}")
            await db.rollback()
