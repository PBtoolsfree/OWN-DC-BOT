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
from app.database.models import EventStatus, EventType, VideoState
from app.database.repositories import YouTubeChannelRepo, YouTubeDestinationRepo, YouTubeEventRepo
from app.youtube.channel_resolver import normalize_channel_id
from app.youtube.dedupe import is_duplicate, mark_failed, mark_notified, mark_skipped, record_event
from app.youtube.feed_parser import fetch_feed
from app.youtube.live_detector import (
    check_channel_live_status,
    check_live_status,
    classify_feed_entry,
)
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
        self._delivery_failures: dict[tuple[str, str, EventType], dict] = {}

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
                    logger.info("Startup repair: restored %d YouTube channel feed URLs to direct RSS polling endpoint", repaired)
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
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    logger.error("Error checking channel %s: %s", channel.youtube_channel_id, str(e))
                    try:
                        await YouTubeChannelRepo.update_feed_status(
                            session,
                            channel.youtube_channel_id,
                            success=False,
                            error=str(e),
                        )
                        await session.commit()
                    except Exception:
                        await session.rollback()

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
            await session.commit()
            return

        # Baseline initialization check: if channel has never had a successful parse AND has no recorded events,
        # baseline all historical entries as seen (EventStatus.SKIPPED) to avoid broadcasting historical videos on setup.
        events_count = await YouTubeEventRepo.count_for_channel(session, channel.youtube_channel_id)
        is_initial_baseline = (events_count == 0 and channel.last_successful_parse_at is None)

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

        if not result.entries:
            await session.commit()
            return

        if is_initial_baseline:
            logger.info(
                "Initial baseline for channel %s (%s): marking %d existing feed entries as seen (no broadcasts)",
                channel.youtube_channel_id, channel.channel_name, len(result.entries)
            )
            for entry in result.entries:
                event_type, sched_start = await classify_feed_entry(entry.video_id, entry.title, self._http_client)
                await record_event(
                    session=session,
                    channel_id=channel.youtube_channel_id,
                    video_id=entry.video_id,
                    event_type=event_type,
                    title=entry.title,
                    video_url=entry.url,
                    published_at=entry.published,
                    status=EventStatus.SKIPPED,
                )
            await session.commit()
            return

        # Process entries (oldest to newest for chronological delivery)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        destinations = await YouTubeDestinationRepo.get_for_channel(
            session, channel.youtube_channel_id
        )

        for entry in reversed(result.entries):
            # Skip entries older than 24h
            pub_time = entry.published or entry.updated
            if pub_time and pub_time < cutoff:
                logger.debug(
                    "Candidate %s: skipping, published at %s is older than cutoff %s",
                    entry.video_id, pub_time, cutoff
                )
                continue

            # Verify channel ID matches
            clean_entry_cid = normalize_channel_id(entry.channel_id) if entry.channel_id else channel.youtube_channel_id
            if clean_entry_cid and clean_entry_cid != channel.youtube_channel_id:
                logger.warning(
                    "Candidate %s: channel mismatch ('%s' != '%s'), skipping",
                    entry.video_id, clean_entry_cid, channel.youtube_channel_id
                )
                continue

            # Classify the feed entry into scheduled live, upload, or premiere
            event_type, sched_start = await classify_feed_entry(entry.video_id, entry.title, self._http_client)
            logger.info(
                "Candidate %s (%s): classified as %s (sched_start=%s)",
                entry.video_id, (entry.title or "")[:40], event_type.value, sched_start
            )

            # Check if this event has already been successfully notified or marked as skipped
            if await is_duplicate(session, channel.youtube_channel_id, entry.video_id, event_type):
                logger.debug(
                    "Candidate %s (%s): already notified for %s, skipping",
                    entry.video_id, (entry.title or "")[:40], event_type.value
                )
                continue

            # Check failure backoff state to prevent uncontrolled retry loops
            fail_key = (channel.youtube_channel_id, entry.video_id, event_type)
            fail_record = self._delivery_failures.get(fail_key)
            if fail_record:
                attempts = fail_record.get("attempts", 0)
                last_try = fail_record.get("last_attempt", datetime.min)
                is_permanent = fail_record.get("permanent", False)
                # Bounded backoff:
                # Permanent validation errors (e.g. HTTP 400 50035): backoff 10m, 30m, 2h, capped at 4 attempts
                # Transient errors: immediate retry on next cycle (0s), then backoff 180s, 600s, 1800s
                backoff_schedule = [600, 1800, 7200] if is_permanent else [0, 180, 600, 1800]
                delay_sec = backoff_schedule[min(attempts - 1, len(backoff_schedule) - 1)]
                now = datetime.utcnow()
                if (now - last_try).total_seconds() < delay_sec:
                    logger.debug(
                        "Candidate %s (%s): in backoff (%d attempts, delay=%ds, permanent=%s), skipping for now",
                        entry.video_id, event_type.value, attempts, delay_sec, is_permanent
                    )
                    continue
                if is_permanent and attempts >= 4:
                    logger.warning(
                        "Candidate %s (%s): delivery permanently failed %d times; suppressing retries until restart or fix",
                        entry.video_id, event_type.value, attempts
                    )
                    continue

            # Check which destinations want this event
            eligible_destinations = []
            for dest in destinations:
                should_send = False
                if event_type == EventType.SCHEDULED_LIVE:
                    if dest.scheduled_live_enabled:
                        should_send = True
                    elif dest.upload_enabled:
                        should_send = True
                elif event_type == EventType.UPLOAD:
                    if dest.upload_enabled:
                        should_send = True
                elif event_type == EventType.PREMIERE:
                    if dest.premiere_enabled or dest.upload_enabled:
                        should_send = True
                elif event_type == EventType.LIVE_STARTED:
                    if dest.live_started_enabled:
                        should_send = True

                if should_send:
                    eligible_destinations.append(dest)
                else:
                    logger.debug(
                        "Candidate %s (%s): destination %d has %s disabled, skipping",
                        entry.video_id, event_type.value, dest.discord_channel_id, event_type.value
                    )

            if not eligible_destinations:
                logger.info(
                    "Candidate %s (%s): no destinations configured for %s, skipping",
                    entry.video_id, event_type.value
                )
                continue

            # Record event in DETECTED state
            event_id = await record_event(
                session=session,
                channel_id=channel.youtube_channel_id,
                video_id=entry.video_id,
                event_type=event_type,
                title=entry.title,
                video_url=entry.url,
                published_at=entry.published,
                status=EventStatus.DETECTED,
            )
            # Commit immediately to release SQLite write lock before Discord network call
            await session.commit()

            # Attempt notification delivery across destinations
            all_sent = True
            has_permanent_error = False
            for dest in eligible_destinations:
                logger.info(
                    "Candidate %s (%s): sending %s notification to Discord channel %d",
                    entry.video_id, (entry.title or "")[:40], event_type.value, dest.discord_channel_id
                )
                res = await send_notification(
                    bot=self.bot,
                    discord_channel_id=dest.discord_channel_id,
                    event_type=event_type,
                    title=entry.title,
                    video_url=entry.url,
                    channel_name=channel.channel_name,
                    thumbnail_url=entry.thumbnail_url,
                    description=entry.description,
                    role_id=dest.notification_role_id,
                    channel_id=channel.youtube_channel_id,
                    published_at=entry.published,
                    scheduled_start=sched_start,
                )

                if not res:
                    all_sent = False
                    if getattr(res, "is_permanent", False):
                        has_permanent_error = True
                    logger.warning(
                        "Candidate %s (%s): delivery failed to Discord channel %d (permanent=%s)",
                        entry.video_id, event_type.value, dest.discord_channel_id, getattr(res, "is_permanent", False)
                    )

            if all_sent:
                await mark_notified(session, event_id)
                await session.commit()
                self._delivery_failures.pop(fail_key, None)
                logger.info(
                    "Candidate %s (%s): successfully notified all destinations (event_id=%d)",
                    entry.video_id, event_type.value, event_id
                )
            else:
                await mark_failed(session, event_id)
                await session.commit()
                prev_attempts = fail_record.get("attempts", 0) if fail_record else 0
                self._delivery_failures[fail_key] = {
                    "attempts": prev_attempts + 1,
                    "last_attempt": datetime.utcnow(),
                    "permanent": has_permanent_error,
                }
                logger.warning(
                    "Candidate %s (%s): delivery failed on at least one destination (event_id=%d, permanent=%s); will retry with backoff",
                    entry.video_id, event_type.value, event_id, has_permanent_error
                )

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
                    await session.commit()

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
                            await session.commit()
                        else:
                            await mark_failed(session, event_id)
                            await session.commit()

                except Exception as e:
                    await session.rollback()
                    logger.error("Live check error for %s: %s", channel.youtube_channel_id, str(e))

                await session.commit()
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
