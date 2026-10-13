"""
PB HERO YouTube Live Detector.

Live state detection using YouTube Data API v3 (optional primary) and yt-dlp (secondary fallback):
- Complete isolation between RSS feed health and live-status health
- Anti-bot verification circuit breaker for yt-dlp ("Sign in to confirm you're not a bot")
- Strict separation: UNKNOWN is never classified as OFFLINE
- Never infers live status from unrelated scheduled streams
- Optional YouTube Data API v3 integration without requiring API key for RSS upload monitoring
"""

import asyncio
import json
import logging
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings
from app.youtube.feed_parser import FeedEntry, fetch_feed

logger = logging.getLogger("pbhero.youtube")

# Pattern for YouTube Channel ID
CHANNEL_ID_PATTERN = re.compile(r"^UC[\w-]+$")

# Global anti-bot circuit breaker for yt-dlp
_bot_blocked_until: Optional[datetime] = None
_bot_circuit_lock = asyncio.Lock()


def _get_ytdlp_binary() -> str:
    """Find yt-dlp binary from current Python virtualenv or system PATH."""
    venv_bin = Path(sys.executable).parent
    for candidate in [venv_bin / "yt-dlp", venv_bin / "yt-dlp.exe"]:
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    found = shutil.which("yt-dlp")
    if found:
        return found

    return "yt-dlp"


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
            "status": "live" if self.is_live else ("upcoming" if self.is_upcoming else ("premiere" if self.is_premiere else ("offline" if self.live_state in ("regular_video", "ended") else "unknown"))),
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
    status: str = "unknown"  # live, upcoming, premiere, offline, unknown
    title: Optional[str] = None
    video_id: Optional[str] = None
    scheduled_start: Optional[str] = None
    viewer_count: Optional[int] = None
    error: Optional[str] = None
    api_key_configured: bool = False
    bot_blocked: bool = False

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
            "api_key_configured": self.api_key_configured,
            "bot_blocked": self.bot_blocked,
        }


async def check_live_status_data_api(video_id: str, api_key: str, http_client: Optional[httpx.AsyncClient] = None) -> Optional[LiveStatus]:
    """
    Check live status using YouTube Data API v3.
    Immune to yt-dlp scraping/bot verification blocks.
    """
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,liveStreamingDetails",
        "id": video_id,
        "key": api_key,
    }
    close_client = False
    client = http_client
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)
        close_client = True

    try:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            logger.warning("YouTube Data API error (%d): %s", response.status_code, response.text[:200])
            return None

        data = response.json()
        items = data.get("items", [])
        if not items:
            return LiveStatus(video_id=video_id, live_state="ended")

        item = items[0]
        snippet = item.get("snippet", {})
        live_details = item.get("liveStreamingDetails", {})
        broadcast_content = snippet.get("liveBroadcastContent", "none")
        title = snippet.get("title")

        if broadcast_content == "live":
            viewers = live_details.get("concurrentViewers")
            return LiveStatus(
                video_id=video_id,
                is_live=True,
                live_state="live",
                title=title,
                viewer_count=int(viewers) if viewers and str(viewers).isdigit() else None,
            )
        elif broadcast_content == "upcoming":
            sched_start = live_details.get("scheduledStartTime")
            return LiveStatus(
                video_id=video_id,
                is_upcoming=True,
                live_state="upcoming",
                title=title,
                scheduled_start=sched_start,
            )
        else:
            return LiveStatus(
                video_id=video_id,
                is_live=False,
                live_state="regular_video",
                title=title,
            )
    except Exception as e:
        logger.warning("YouTube Data API call failed for %s: %s", video_id, e)
        return None
    finally:
        if close_client:
            await client.aclose()


async def check_live_status(video_id: str, http_client: Optional[httpx.AsyncClient] = None) -> LiveStatus:
    """
    Check the live status of a YouTube video.

    Uses YouTube Data API v3 if API key is configured.
    Otherwise uses yt-dlp with anti-bot circuit breaker.
    """
    global _bot_blocked_until

    settings = get_settings()

    # 1. Check YouTube Data API v3 if key available
    if getattr(settings, "YOUTUBE_API_KEY", ""):
        api_result = await check_live_status_data_api(video_id, settings.YOUTUBE_API_KEY, http_client)
        if api_result is not None:
            return api_result

    # 2. Check if yt-dlp is currently in anti-bot cooldown
    async with _bot_circuit_lock:
        if _bot_blocked_until and datetime.utcnow() < _bot_blocked_until:
            wait_remaining = int((_bot_blocked_until - datetime.utcnow()).total_seconds())
            logger.info(
                "yt-dlp is in anti-bot verification cooldown (%ds remaining). Skipping process.",
                wait_remaining
            )
            return LiveStatus(
                video_id=video_id,
                live_state="unknown",
                error=f"YouTube anti-bot verification active (yt-dlp in {wait_remaining}s cooldown). Set YOUTUBE_API_KEY for guaranteed checks.",
            )

    # 3. Fallback to yt-dlp
    url = f"https://www.youtube.com/watch?v={video_id}"
    logger.debug("Checking live status via yt-dlp for video: %s", video_id)

    try:
        ytdlp_bin = _get_ytdlp_binary()
        process = await asyncio.create_subprocess_exec(
            ytdlp_bin,
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

            # Check for bot block
            if "confirm you're not a bot" in error_text.lower() or "sign in to confirm" in error_text.lower():
                async with _bot_circuit_lock:
                    _bot_blocked_until = datetime.utcnow() + timedelta(minutes=10)
                logger.warning(
                    "yt-dlp encountered YouTube bot verification block for %s. Activated 10m cooldown.",
                    video_id
                )
                return LiveStatus(
                    video_id=video_id,
                    live_state="unknown",
                    error="YouTube anti-bot verification triggered (Sign in to confirm you're not a bot). Check in 10m cooldown.",
                )

            # Check for known non-error states
            if "is not a video" in error_text.lower() or "premieres in" in error_text.lower():
                return LiveStatus(video_id=video_id, is_upcoming=True, live_state="upcoming")

            logger.warning("yt-dlp error for %s: %s", video_id, error_text[:200])
            return LiveStatus(video_id=video_id, live_state="unknown", error=error_text[:200])

        data = json.loads(stdout.decode("utf-8"))

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
        elif was_live or live_status_str == "post_live":
            status.live_state = "ended"
        else:
            status.live_state = "regular_video"

        logger.info("Live status for %s: %s", video_id, status.live_state)
        return status

    except asyncio.TimeoutError:
        logger.warning("Live status check timed out for %s", video_id)
        return LiveStatus(video_id=video_id, live_state="unknown", error="Request timed out")
    except FileNotFoundError:
        logger.error("yt-dlp binary not found")
        return LiveStatus(video_id=video_id, live_state="unknown", error="yt-dlp binary not found")
    except Exception as e:
        logger.error("Live status check error for %s: %s", video_id, str(e))
        return LiveStatus(video_id=video_id, live_state="unknown", error=str(e))


async def check_channel_live_status(
    channel_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
    max_candidates: int = 3,
) -> ChannelLiveResult:
    """
    Check the live status of a YouTube channel by inspecting recent entries.

    Guarantees:
    - Never classifies UNKNOWN as OFFLINE
    - Never infers active live status from an unrelated scheduled video
    - Does not loop or hammer yt-dlp on bot-blocked states
    - Preserves RSS feed health separately from live detector health
    """
    settings = get_settings()
    has_api_key = bool(getattr(settings, "YOUTUBE_API_KEY", ""))
    is_bot_blocked = bool(_bot_blocked_until and datetime.utcnow() < _bot_blocked_until)

    channel_id = channel_id.strip()
    if not channel_id.startswith("UC") or not CHANNEL_ID_PATTERN.match(channel_id):
        return ChannelLiveResult(
            channel_id=channel_id,
            status="unknown",
            is_live=False,
            error="Invalid YouTube channel ID format. Must start with 'UC'.",
            api_key_configured=has_api_key,
            bot_blocked=is_bot_blocked,
        )

    try:
        # 1. Fetch channel feed (RSS check)
        feed_result = await fetch_feed(channel_id, http_client=http_client)
        if not feed_result.success:
            return ChannelLiveResult(
                channel_id=channel_id,
                status="unknown",
                is_live=False,
                error=f"Feed fetch failed: {feed_result.error or 'Unknown feed error'}",
                api_key_configured=has_api_key,
                bot_blocked=is_bot_blocked,
            )

        if not feed_result.entries:
            return ChannelLiveResult(
                channel_id=channel_id,
                status="offline",
                is_live=False,
                video_id=None,
                title=None,
                error=None,
                api_key_configured=has_api_key,
                bot_blocked=is_bot_blocked,
            )

        # 2. Candidate inspection
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
        all_unknown = True

        for entry in candidates:
            live_status = await check_live_status(entry.video_id, http_client=http_client)
            if live_status.live_state == "unknown":
                if live_status.error:
                    last_error = live_status.error
                continue

            all_unknown = False

            # Active live stream
            if live_status.is_live or live_status.live_state == "live":
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
                    api_key_configured=has_api_key,
                    bot_blocked=is_bot_blocked,
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

        # Prefer upcoming stream if no active stream
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
                api_key_configured=has_api_key,
                bot_blocked=is_bot_blocked,
            )

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
                api_key_configured=has_api_key,
                bot_blocked=is_bot_blocked,
            )

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
                error=None,
                api_key_configured=has_api_key,
                bot_blocked=is_bot_blocked,
            )

        # If all candidates returned unknown, do NOT report offline
        if all_unknown:
            most_recent = feed_result.entries[0] if feed_result.entries else None
            return ChannelLiveResult(
                channel_id=channel_id,
                is_live=False,
                status="unknown",
                title=most_recent.title if most_recent else None,
                video_id=most_recent.video_id if most_recent else None,
                error=f"Live detection check failed: {last_error}" if last_error else "Live status check inconclusive (unknown)",
                api_key_configured=has_api_key,
                bot_blocked=is_bot_blocked,
            )

        return ChannelLiveResult(
            channel_id=channel_id,
            is_live=False,
            status="offline",
            title=feed_result.entries[0].title if feed_result.entries else None,
            video_id=feed_result.entries[0].video_id if feed_result.entries else None,
            error=None,
            api_key_configured=has_api_key,
            bot_blocked=is_bot_blocked,
        )

    except Exception as e:
        logger.error("Channel live detection unexpected error for %s: %s", channel_id, str(e), exc_info=True)
        return ChannelLiveResult(
            channel_id=channel_id,
            status="unknown",
            is_live=False,
            error=f"Live detector error: {str(e)}",
            api_key_configured=has_api_key,
            bot_blocked=is_bot_blocked,
        )


async def is_yt_dlp_available() -> bool:
    """Check if yt-dlp is installed and accessible."""
    try:
        ytdlp_bin = _get_ytdlp_binary()
        process = await asyncio.create_subprocess_exec(
            ytdlp_bin, "--version",
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
