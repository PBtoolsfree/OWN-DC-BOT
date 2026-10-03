"""
PB HERO YouTube Scheduler.

Background task that periodically checks YouTube feeds and detects
new uploads, live streams, and premieres. Sends notifications through
the Discord bot.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
import httpx

from app.config import get_settings
from app.database.engine import get_session_direct
from app.database.models import EventType, VideoState
from app.database.repositories import YouTubeChannelRepo, YouTubeDestinationRepo
from app.youtube.dedupe import is_duplicate, mark_notified, record_event
from app.youtube.feed_parser import fetch_feed
from app.youtube.live_detector import check_live_status
from app.youtube.notifier import send_notification

logger = logging.getLogger("pbhero.youtube")


class YouTubeScheduler:
    """
    Background scheduler for YouTube feed monitoring.

    Polls YouTube Atom feeds at configurable intervals.
    Uses yt-dlp for live state detection as secondary check.
    All notifications target the single configured Discord guild.
    """

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.settings = get_settings()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._live_task: Optional[asyncio.Task] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._healthy = True
        self._last_check: Optional[datetime] = None
        self._error_count = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    @property
    def last_check(self) -> Optional[datetime]:
        return self._last_check

    async def start(self) -> None:
        """Start the YouTube monitoring scheduler."""
        if self._running:
            return

        self._running = True
        self._http_client = httpx.AsyncClient(timeout=30.0)

        # Start feed polling task
        self._task = asyncio.create_task(self._feed_poll_loop())
        # Start live detection task
        self._live_task = asyncio.create_task(self._live_check_loop())

        logger.info("YouTube scheduler started (poll=%ds, live=%ds)",
                     self.settings.YOUTUBE_POLL_INTERVAL,
                     self.settings.YOUTUBE_LIVE_CHECK_INTERVAL)

    async def stop(self) -> None:
        """Stop the YouTube monitoring scheduler."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._live_task:
            self._live_task.cancel()
            try:
                await self._live_task
            except asyncio.CancelledError:
                pass

        if self._http_client:
            await self._http_client.aclose()

        logger.info("YouTube scheduler stopped")

    async def _feed_poll_loop(self) -> None:
        """Main feed polling loop."""
        # Wait for bot to be ready
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)  # Initial delay

        while self._running:
            try:
                await self._check_all_feeds()
                self._last_check = datetime.utcnow()
                self._error_count = 0
                self._healthy = True
            except Exception as e:
                self._error_count += 1
                self._healthy = self._error_count < 5
                logger.error("Feed poll error (count=%d): %s", self._error_count, str(e))

            await asyncio.sleep(self.settings.YOUTUBE_POLL_INTERVAL)

    async def _live_check_loop(self) -> None:
        """Live state detection loop."""
        await self.bot.wait_until_ready()
        await asyncio.sleep(15)  # Stagger from feed polling

        while self._running:
            try:
                await self._check_live_states()
            except Exception as e:
                logger.error("Live check error: %s", str(e))

            await asyncio.sleep(self.settings.YOUTUBE_LIVE_CHECK_INTERVAL)

    async def _check_all_feeds(self) -> None:
        """Check feeds for all enabled YouTube channels."""
        session = await get_session_direct()
        try:
            channels = await YouTubeChannelRepo.get_all(session, enabled_only=True)
            if not channels:
                return

            logger.debug("Checking %d YouTube channels", len(channels))

            for channel in channels:
                try:
                    await self._check_single_feed(session, channel)
                except Exception as e:
                    logger.error("Error checking channel %s: %s", channel.youtube_channel_id, str(e))
                    await YouTubeChannelRepo.update_check_status(
                        session, channel.youtube_channel_id, success=False, error=str(e)
                    )

                # Small delay between channels to be respectful
                await asyncio.sleep(2)

            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def _check_single_feed(self, session, channel) -> None:
        """Check a single YouTube channel's feed."""
        result = await fetch_feed(channel.youtube_channel_id, self._http_client)

        if not result.success:
            await YouTubeChannelRepo.update_check_status(
                session, channel.youtube_channel_id, success=False, error=result.error
            )
            return

        # Update channel name if discovered
        if result.channel_name and result.channel_name != channel.channel_name:
            channel.channel_name = result.channel_name

        await YouTubeChannelRepo.update_check_status(
            session, channel.youtube_channel_id, success=True
        )

        # Process entries (newest first, but we want chronological notifications)
        # Only process recent entries (last 24 hours) to avoid flooding on first run
        cutoff = datetime.utcnow() - timedelta(hours=24)

        for entry in reversed(result.entries):
            # Skip old entries
            if entry.published and entry.published < cutoff:
                continue

            # Check for duplicate
            if await is_duplicate(session, channel.youtube_channel_id, entry.video_id, EventType.UPLOAD):
                continue

            # Record and notify
            event_id = await record_event(
                session=session,
                channel_id=channel.youtube_channel_id,
                video_id=entry.video_id,
                event_type=EventType.UPLOAD,
                title=entry.title,
                video_url=entry.url,
                published_at=entry.published,
            )

            # Get destinations
            destinations = await YouTubeDestinationRepo.get_for_channel(
                session, channel.youtube_channel_id
            )

            for dest in destinations:
                if not dest.upload_enabled:
                    continue

                success = await send_notification(
                    bot=self.bot,
                    discord_channel_id=dest.discord_channel_id,
                    event_type=EventType.UPLOAD,
                    title=entry.title,
                    video_url=entry.url,
                    channel_name=channel.channel_name,
                    thumbnail_url=entry.thumbnail_url,
                    description=entry.description,
                    role_id=dest.notification_role_id,
                )

                if success:
                    await mark_notified(session, event_id)

    async def _check_live_states(self) -> None:
        """Check live states for recent videos using yt-dlp."""
        session = await get_session_direct()
        try:
            channels = await YouTubeChannelRepo.get_all(session, enabled_only=True)

            for channel in channels:
                try:
                    # Get recent feed entries to check for live
                    result = await fetch_feed(channel.youtube_channel_id, self._http_client)
                    if not result.success or not result.entries:
                        continue

                    # Check only the most recent entry for live status
                    latest = result.entries[0]
                    live_status = await check_live_status(latest.video_id)

                    if live_status.live_state == "live":
                        event_type = EventType.LIVE_STARTED
                    elif live_status.live_state == "upcoming":
                        event_type = EventType.SCHEDULED_LIVE
                    elif live_status.live_state == "premiere":
                        event_type = EventType.PREMIERE
                    else:
                        continue

                    # Deduplicate
                    if await is_duplicate(session, channel.youtube_channel_id, latest.video_id, event_type):
                        continue

                    event_id = await record_event(
                        session=session,
                        channel_id=channel.youtube_channel_id,
                        video_id=latest.video_id,
                        event_type=event_type,
                        title=live_status.title or latest.title,
                        video_url=latest.url,
                        live_state=VideoState(live_status.live_state),
                    )

                    destinations = await YouTubeDestinationRepo.get_for_channel(
                        session, channel.youtube_channel_id
                    )

                    for dest in destinations:
                        should_notify = False
                        if event_type == EventType.LIVE_STARTED and dest.live_started_enabled:
                            should_notify = True
                        elif event_type == EventType.SCHEDULED_LIVE and dest.scheduled_live_enabled:
                            should_notify = True
                        elif event_type == EventType.PREMIERE and dest.premiere_enabled:
                            should_notify = True

                        if not should_notify:
                            continue

                        success = await send_notification(
                            bot=self.bot,
                            discord_channel_id=dest.discord_channel_id,
                            event_type=event_type,
                            title=live_status.title or latest.title,
                            video_url=latest.url,
                            channel_name=channel.channel_name,
                            thumbnail_url=latest.thumbnail_url,
                            role_id=dest.notification_role_id,
                        )

                        if success:
                            await mark_notified(session, event_id)

                except Exception as e:
                    logger.error("Live check error for %s: %s", channel.youtube_channel_id, str(e))

                await asyncio.sleep(3)  # Stagger between channels

            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def force_check(self, channel_id: str = None) -> dict:
        """Force an immediate feed check. Used by dashboard test button."""
        result = {"success": False, "message": ""}
        try:
            session = await get_session_direct()
            try:
                if channel_id:
                    channel = await YouTubeChannelRepo.get_by_channel_id(session, channel_id)
                    if channel:
                        await self._check_single_feed(session, channel)
                        result = {"success": True, "message": f"Checked {channel.channel_name}"}
                    else:
                        result = {"success": False, "message": "Channel not found"}
                else:
                    await self._check_all_feeds()
                    result = {"success": True, "message": "All channels checked"}
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
        except Exception as e:
            result = {"success": False, "message": str(e)}
        return result
