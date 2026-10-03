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
    """Check if an event has already been processed."""
    return await YouTubeEventRepo.exists(session, channel_id, video_id, event_type)


async def record_event(session: AsyncSession, channel_id: str, video_id: str,
                       event_type: EventType, title: str = None, video_url: str = None,
                       published_at: datetime = None, live_state: VideoState = None) -> int:
    """
    Record a new event for deduplication.

    Returns the event ID.
    """
    event = await YouTubeEventRepo.create(
        session=session,
        youtube_channel_id=channel_id,
        video_id=video_id,
        event_type=event_type,
        title=title,
        video_url=video_url,
        published_at=published_at,
        status=EventStatus.DETECTED,
        live_state=live_state,
    )
    logger.info("Recorded event: %s/%s/%s (id=%d)", channel_id, video_id, event_type.value, event.id)
    return event.id


async def mark_notified(session: AsyncSession, event_id: int) -> None:
    """Mark an event as successfully notified."""
    await YouTubeEventRepo.mark_notified(session, event_id)
    logger.debug("Event %d marked as notified", event_id)
