"""
PB HERO YouTube Live Detector.

Secondary metadata detection using yt-dlp for live state.
No login cookies, no CAPTCHA bypass, no credential scraping.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("pbhero.youtube")


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

        import json
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
