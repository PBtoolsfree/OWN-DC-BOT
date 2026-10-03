"""
PB HERO YouTube Live Detector.

Secondary metadata detection using yt-dlp for live state.
No login cookies, no CAPTCHA bypass, no credential scraping.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app.youtube.feed_parser import FeedEntry, fetch_feed

logger = logging.getLogger("pbhero.youtube")

# Pattern for YouTube Channel ID
CHANNEL_ID_PATTERN = re.compile(r"^UC[\w-]+$")


@dataclass
class LiveStatus:
    """Live status result for a video."""
    video_id: str
    is_live: bool = False
    is_upcoming: bool = False
    is_premiere: bool = False
    live_state: str = "unknown"  # upcoming, live, ended, premiere, regular_video, unknown
    title: Optional[str] = None
    scheduled_start: Optional[str] = None
    viewer_count: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "is_live": self.is_live,
            "is_upcoming": self.is_upcoming,
            "is_premiere": self.is_premiere,
            "live_state": self.live_state,
            "status": "live" if self.is_live else ("upcoming" if self.is_upcoming else ("premiere" if self.is_premiere else "offline")),
            "title": self.title,
            "scheduled_start": self.scheduled_start,
            "viewer_count": self.viewer_count,
            "error": self.error,
        }


@dataclass
class ChannelLiveResult:
    """Channel-level live detection result."""
    channel_id: str
    is_live: bool = False
    is_upcoming: bool = False
    is_premiere: bool = False
    status: str = "offline"  # live, upcoming, premiere, offline, unknown
    title: Optional[str] = None
    video_id: Optional[str] = None
    scheduled_start: Optional[str] = None
    viewer_count: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert result to dictionary representation for API responses."""
        return {
            "success": self.error is None and self.status != "unknown",
            "is_live": self.is_live,
            "is_upcoming": self.is_upcoming,
            "is_premiere": self.is_premiere,
            "status": self.status,
            "title": self.title,
            "video_id": self.video_id,
            "channel_id": self.channel_id,
            "scheduled_start": self.scheduled_start,
            "viewer_count": self.viewer_count,
            "error": self.error,
        }


async def check_live_status(video_id: str) -> LiveStatus:
    """
    Check the live status of a YouTube video using yt-dlp.

    Uses public metadata only - no cookies, no login, no anti-bot bypass.

    Args:
        video_id: YouTube video ID

    Returns:
        LiveStatus with detected state
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    logger.debug("Checking live status for video: %s", video_id)

    try:
        # Use yt-dlp to extract metadata (no download)
        process = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--no-playlist",
            "--no-warnings",
            "--socket-timeout", "15",
            "--no-check-certificates",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

        if process.returncode != 0:
            error_text = stderr.decode("utf-8", errors="replace").strip()
            # Check for known non-error states
            if "is not a video" in error_text.lower() or "premieres in" in error_text.lower():
                return LiveStatus(video_id=video_id, is_upcoming=True, live_state="upcoming")

            logger.warning("yt-dlp error for %s: %s", video_id, error_text[:200])
            return LiveStatus(video_id=video_id, error=error_text[:200])

        data = json.loads(stdout.decode("utf-8"))

        # Determine live state
        is_live = data.get("is_live", False)
        was_live = data.get("was_live", False)
        live_status_str = data.get("live_status", "")

        status = LiveStatus(
            video_id=video_id,
            title=data.get("title"),
        )

        if live_status_str == "is_upcoming" or data.get("live_status") == "is_upcoming":
            status.is_upcoming = True
            status.live_state = "upcoming"
            status.scheduled_start = data.get("release_timestamp")
        elif is_live:
            status.is_live = True
            status.live_state = "live"
            status.viewer_count = data.get("concurrent_view_count")
        elif was_live:
            status.live_state = "ended"
        elif live_status_str == "post_live":
            status.live_state = "ended"
        else:
            # Check for premiere
            if data.get("live_status") == "is_upcoming":
                status.is_premiere = True
                status.live_state = "premiere"
            else:
                status.live_state = "regular_video"

        logger.info("Live status for %s: %s", video_id, status.live_state)
        return status

    except asyncio.TimeoutError:
        logger.warning("Live status check timed out for %s", video_id)
        return LiveStatus(video_id=video_id, live_state="unknown", error="Timeout")
    except FileNotFoundError:
        logger.error("yt-dlp not found. Install it: pip install yt-dlp")
        return LiveStatus(video_id=video_id, live_state="unknown", error="yt-dlp not installed")
    except Exception as e:
        logger.error("Live status check error for %s: %s", video_id, str(e))
        return LiveStatus(video_id=video_id, live_state="unknown", error=str(e))


async def check_channel_live_status(
    channel_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
    max_candidates: int = 3,
) -> ChannelLiveResult:
    """
    Check the live status of a YouTube channel by inspecting its Atom feed and candidates.

    Flow:
    1. Validate channel ID.
    2. Fetch channel Atom feed.
    3. Collect candidate video IDs from recent entries.
    4. Check candidate video live states using yt-dlp metadata.
    5. Prioritize live, then upcoming, then offline/regular video.

    Args:
        channel_id: YouTube Channel ID (starts with UC)
        http_client: Optional reusable HTTP client
        max_candidates: Maximum candidate videos to inspect

    Returns:
        ChannelLiveResult with detected channel live state
    """
    channel_id = channel_id.strip()
    if not channel_id.startswith("UC") or not CHANNEL_ID_PATTERN.match(channel_id):
        logger.warning("Invalid YouTube channel ID format: %s", channel_id)
        return ChannelLiveResult(
            channel_id=channel_id,
            status="unknown",
            is_live=False,
            error="Invalid YouTube channel ID format. Must start with 'UC'.",
        )

    try:
        # 1. Fetch channel feed
        feed_result = await fetch_feed(channel_id, http_client=http_client)
        if not feed_result.success:
            logger.warning("Feed fetch failed for channel %s: %s", channel_id, feed_result.error)
            return ChannelLiveResult(
                channel_id=channel_id,
                status="unknown",
                is_live=False,
                error=f"Feed fetch failed: {feed_result.error or 'Unknown feed error'}",
            )

        # 2. Check if entries exist
        if not feed_result.entries:
            logger.info("Channel %s has no feed entries; reporting offline", channel_id)
            return ChannelLiveResult(
                channel_id=channel_id,
                status="offline",
                is_live=False,
                video_id=None,
                title=None,
                scheduled_start=None,
                error=None,
            )

        # 3. Candidate selection strategy:
        # Prioritize entries whose title hints at live/streaming, then newest entries
        raw_entries = feed_result.entries[:max(max_candidates * 2, 6)]
        hinted_entries: list[FeedEntry] = []
        regular_entries: list[FeedEntry] = []
        keywords = ("live", "stream", "premiere", "broadcast", "scheduled")
        for entry in raw_entries:
            title_lower = (entry.title or "").lower()
            if any(k in title_lower for k in keywords):
                hinted_entries.append(entry)
            else:
                regular_entries.append(entry)

        candidates = (hinted_entries + regular_entries)[:max_candidates]

        upcoming_candidate: Optional[tuple[FeedEntry, LiveStatus]] = None
        premiere_candidate: Optional[tuple[FeedEntry, LiveStatus]] = None
        regular_candidate: Optional[tuple[FeedEntry, LiveStatus]] = None
        last_error: Optional[str] = None
        all_failed = True

        # 4. Check candidates with check_live_status
        for entry in candidates:
            live_status = await check_live_status(entry.video_id)
            if live_status.error and live_status.live_state == "unknown":
                last_error = live_status.error
                continue

            all_failed = False

            if live_status.is_live or live_status.live_state == "live":
                # 5. Prefer currently live candidate - stop immediately!
                logger.info(
                    "Found active live stream for channel %s: video %s (%s)",
                    channel_id,
                    entry.video_id,
                    live_status.title or entry.title,
                )
                return ChannelLiveResult(
                    channel_id=channel_id,
                    is_live=True,
                    is_upcoming=False,
                    is_premiere=False,
                    status="live",
                    title=live_status.title or entry.title,
                    video_id=entry.video_id,
                    scheduled_start=live_status.scheduled_start,
                    viewer_count=live_status.viewer_count,
                    error=None,
                )
            elif live_status.is_upcoming or live_status.live_state == "upcoming":
                if upcoming_candidate is None:
                    upcoming_candidate = (entry, live_status)
            elif live_status.is_premiere or live_status.live_state == "premiere":
                if premiere_candidate is None:
                    premiere_candidate = (entry, live_status)
            else:
                if regular_candidate is None:
                    regular_candidate = (entry, live_status)

        # 6. Prefer upcoming candidate if no active live candidate
        if upcoming_candidate:
            entry, live_status = upcoming_candidate
            return ChannelLiveResult(
                channel_id=channel_id,
                is_live=False,
                is_upcoming=True,
                is_premiere=False,
                status="upcoming",
                title=live_status.title or entry.title,
                video_id=entry.video_id,
                scheduled_start=live_status.scheduled_start,
                viewer_count=live_status.viewer_count,
                error=None,
            )

        # Premiere candidate
        if premiere_candidate:
            entry, live_status = premiere_candidate
            return ChannelLiveResult(
                channel_id=channel_id,
                is_live=False,
                is_upcoming=False,
                is_premiere=True,
                status="premiere",
                title=live_status.title or entry.title,
                video_id=entry.video_id,
                scheduled_start=live_status.scheduled_start,
                viewer_count=live_status.viewer_count,
                error=None,
            )

        # 7. Otherwise return regular candidate as offline
        if regular_candidate:
            entry, live_status = regular_candidate
            return ChannelLiveResult(
                channel_id=channel_id,
                is_live=False,
                is_upcoming=False,
                is_premiere=False,
                status="offline",
                title=live_status.title or entry.title,
                video_id=entry.video_id,
                scheduled_start=live_status.scheduled_start,
                viewer_count=live_status.viewer_count,
                error=None,
            )

        # If all candidates failed with yt-dlp errors
        if all_failed and last_error:
            most_recent = feed_result.entries[0] if feed_result.entries else None
            return ChannelLiveResult(
                channel_id=channel_id,
                is_live=False,
                status="unknown",
                title=most_recent.title if most_recent else None,
                video_id=most_recent.video_id if most_recent else None,
                error=f"Live detection check failed: {last_error}",
            )

        # Fallback offline with the most recent entry
        most_recent = feed_result.entries[0]
        return ChannelLiveResult(
            channel_id=channel_id,
            is_live=False,
            status="offline",
            title=most_recent.title,
            video_id=most_recent.video_id,
            error=None,
        )

    except Exception as e:
        logger.error("Channel live detection unexpected error for %s: %s", channel_id, str(e), exc_info=True)
        return ChannelLiveResult(
            channel_id=channel_id,
            status="unknown",
            is_live=False,
            error=f"Channel live status error: {str(e)}",
        )


async def is_yt_dlp_available() -> bool:
    """Check if yt-dlp is installed and accessible."""
    try:
        process = await asyncio.create_subprocess_exec(
            "yt-dlp", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10.0)
        version = stdout.decode("utf-8").strip()
        logger.info("yt-dlp available: %s", version)
        return True
    except (FileNotFoundError, asyncio.TimeoutError):
        logger.warning("yt-dlp not available for live detection")
        return False
