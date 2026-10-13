"""
PB HERO YouTube Deduplication Engine.

Ensures each video/event generates the same notification only once.
"""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import EventStatus, EventType, VideoState
from app.database.repositories import YouTubeEventRepo

logger = logging.getLogger("pbhero.youtube")


async def is_duplicate(session: AsyncSession, channel_id: str, video_id: str,
                       event_type: EventType) -> bool:
    """
    Check if an event has already been successfully notified or marked as skipped.
    Events that failed or were only detected without delivery are not duplicates and can be retried.
    """
    return await YouTubeEventRepo.is_already_notified(session, channel_id, video_id, event_type)


async def record_event(session: AsyncSession, channel_id: str, video_id: str,
                       event_type: EventType, title: str = None, video_url: str = None,
                       published_at: datetime = None, live_state: VideoState = None,
                       status: EventStatus = EventStatus.DETECTED) -> int:
    """
    Record or update an event for deduplication (idempotent, safe on retries).
    Returns the event ID.
    """
    event = await YouTubeEventRepo.record_or_update(
        session=session,
        youtube_channel_id=channel_id,
        video_id=video_id,
        event_type=event_type,
        title=title,
        video_url=video_url,
        published_at=published_at,
        status=status,
        live_state=live_state,
    )
    logger.info("Recorded event: %s/%s/%s (id=%d, status=%s)", channel_id, video_id, event_type.value, event.id, event.status.value)
    return event.id


async def mark_notified(session: AsyncSession, event_id: int) -> None:
    """Mark an event as successfully notified."""
    await YouTubeEventRepo.mark_notified(session, event_id)
    logger.debug("Event %d marked as notified", event_id)


async def mark_failed(session: AsyncSession, event_id: int) -> None:
    """Mark an event as failed for future delivery retry."""
    await YouTubeEventRepo.mark_failed(session, event_id)
    logger.debug("Event %d marked as failed (eligible for retry)", event_id)


async def mark_skipped(session: AsyncSession, event_id: int) -> None:
    """Mark an event as skipped (e.g. historical baseline)."""
    await YouTubeEventRepo.mark_skipped(session, event_id)
    logger.debug("Event %d marked as skipped", event_id)
