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
from app.youtube.live_detector import check_channel_live_status, check_live_status
from app.youtube.notifier import send_notification

logger = logging.getLogger("pbhero.youtube")


class YouTubeScheduler:
    """
    Background scheduler for YouTube feed monitoring.

    Polls YouTube Atom feeds at configurable intervals.
    Maintains complete isolation between feed health and live-status health.
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

        # 1. Perform safe, idempotent startup repair of saved YouTube feed URLs
        try:
            session = await get_session_direct()
            try:
                repaired = await YouTubeChannelRepo.repair_saved_feed_urls(session)
                if repaired > 0:
                    await session.commit()
                    logger.info("Startup repair: migrated %d YouTube channel feed URLs to canonical endpoint", repaired)
            finally:
                await session.close()
        except Exception as e:
            logger.warning("Startup YouTube URL repair check encountered an issue: %s", e)

        # 2. Start background tasks
        self._task = asyncio.create_task(self._feed_poll_loop())
        self._live_task = asyncio.create_task(self._live_check_loop())

        logger.info(
            "YouTube scheduler started (poll=%ds, live=%ds)",
            self.settings.YOUTUBE_POLL_INTERVAL,
            self.settings.YOUTUBE_LIVE_CHECK_INTERVAL,
        )

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
                logger.error("Feed poll loop error (count=%d): %s", self._error_count, str(e))

            await asyncio.sleep(self.settings.YOUTUBE_POLL_INTERVAL)

    async def _live_check_loop(self) -> None:
        """Live state detection loop."""
        await self.bot.wait_until_ready()
        await asyncio.sleep(15)  # Stagger from feed polling

        while self._running:
            try:
                await self._check_live_states()
            except Exception as e:
                logger.error("Live check loop error: %s", str(e))

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
                    await YouTubeChannelRepo.update_feed_status(
                        session,
                        channel.youtube_channel_id,
                        success=False,
                        error=str(e),
                    )

                # Delay between channels to be respectful to rate limits
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
            await YouTubeChannelRepo.update_feed_status(
                session,
                channel.youtube_channel_id,
                success=False,
                http_status=result.http_status,
                error=result.error,
                next_retry_at=result.next_retry_at,
            )
            return

        # Update channel name if discovered
        if result.channel_name and result.channel_name != channel.channel_name:
            channel.channel_name = result.channel_name

        await YouTubeChannelRepo.update_feed_status(
            session,
            channel.youtube_channel_id,
            success=True,
            http_status=result.http_status or 200,
            entry_count=len(result.entries),
        )

        # Process entries (newest first, chronological notification delivery)
        cutoff = datetime.utcnow() - timedelta(hours=24)

        for entry in reversed(result.entries):
            # Skip entries older than 24h
            if entry.published and entry.published < cutoff:
                continue

            # Verify channel ID matches
            if entry.channel_id and entry.channel_id != channel.youtube_channel_id:
                continue

            # Check for duplicate
            if await is_duplicate(session, channel.youtube_channel_id, entry.video_id, EventType.UPLOAD):
                continue

            # Record event
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
                    channel_id=channel.youtube_channel_id,
                    published_at=entry.published,
                )

                if success:
                    await mark_notified(session, event_id)

    async def _check_live_states(self) -> None:
        """Check live states for monitored channels without affecting RSS feed health."""
        session = await get_session_direct()
        try:
            channels = await YouTubeChannelRepo.get_all(session, enabled_only=True)

            for channel in channels:
                try:
                    live_res = await check_channel_live_status(
                        channel.youtube_channel_id,
                        http_client=self._http_client,
                        max_candidates=3,
                    )

                    # Update live health telemetry in DB separately from feed health
                    if live_res.status == "unknown":
                        await YouTubeChannelRepo.update_live_status(
                            session, channel.youtube_channel_id, live_health="UNKNOWN", error=live_res.error
                        )
                        continue
                    else:
                        await YouTubeChannelRepo.update_live_status(
                            session, channel.youtube_channel_id, live_health="HEALTHY"
                        )

                    # Determine event type
                    event_type: Optional[EventType] = None
                    if live_res.status == "live" and live_res.is_live:
                        event_type = EventType.LIVE_STARTED
                    elif live_res.status == "upcoming" and live_res.is_upcoming:
                        event_type = EventType.SCHEDULED_LIVE
                    elif live_res.status == "premiere" and live_res.is_premiere:
                        event_type = EventType.PREMIERE

                    if not event_type or not live_res.video_id:
                        continue

                    # Deduplicate
                    if await is_duplicate(session, channel.youtube_channel_id, live_res.video_id, event_type):
                        continue

                    video_url = f"https://www.youtube.com/watch?v={live_res.video_id}"
                    video_state_map = {
                        EventType.LIVE_STARTED: VideoState.LIVE,
                        EventType.SCHEDULED_LIVE: VideoState.UPCOMING,
                        EventType.PREMIERE: VideoState.PREMIERE,
                    }

                    event_id = await record_event(
                        session=session,
                        channel_id=channel.youtube_channel_id,
                        video_id=live_res.video_id,
                        event_type=event_type,
                        title=live_res.title,
                        video_url=video_url,
                        live_state=video_state_map.get(event_type),
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
                            title=live_res.title or "Live Stream",
                            video_url=video_url,
                            channel_name=channel.channel_name,
                            thumbnail_url=f"https://i.ytimg.com/vi/{live_res.video_id}/hqdefault.jpg",
                            role_id=dest.notification_role_id,
                            channel_id=channel.youtube_channel_id,
                            scheduled_start=live_res.scheduled_start,
                            viewer_count=live_res.viewer_count,
                        )

                        if success:
                            await mark_notified(session, event_id)

                except Exception as e:
                    logger.error("Live check error for %s: %s", channel.youtube_channel_id, str(e))

                await asyncio.sleep(2)  # Delay between channels

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
