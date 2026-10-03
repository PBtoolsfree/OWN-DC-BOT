"""
PB HERO YouTube Feed Parser.

Parses YouTube Atom/RSS feeds without requiring a YouTube API key.
Primary feed URL: https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import feedparser
import httpx

logger = logging.getLogger("pbhero.youtube")

FEED_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
REQUEST_TIMEOUT = 30.0


@dataclass
class FeedEntry:
    """Represents a parsed YouTube feed entry."""
    video_id: str
    title: str
    url: str
    published: Optional[datetime] = None
    updated: Optional[datetime] = None
    channel_id: str = ""
    channel_name: str = ""
    thumbnail_url: str = ""
    description: str = ""


@dataclass
class FeedResult:
    """Result of parsing a YouTube feed."""
    success: bool
    channel_id: str = ""
    channel_name: str = ""
    entries: list[FeedEntry] = field(default_factory=list)
    error: Optional[str] = None


def _parse_datetime(time_struct) -> Optional[datetime]:
    """Safely parse a feedparser time struct to datetime."""
    if not time_struct:
        return None
    try:
        from time import mktime
        return datetime.fromtimestamp(mktime(time_struct))
    except (TypeError, ValueError, OverflowError):
        return None


def _parse_datetime_str(date_str: str) -> Optional[datetime]:
    """Parse an ISO datetime string."""
    if not date_str:
        return None
    try:
        # Handle various ISO formats
        date_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(date_str.replace("+00:00", ""))
    except (ValueError, TypeError):
        return None


async def fetch_feed(channel_id: str, http_client: httpx.AsyncClient = None) -> FeedResult:
    """
    Fetch and parse a YouTube channel's Atom feed.

    Args:
        channel_id: YouTube channel ID (UCxxxxxx format)
        http_client: Optional reusable HTTP client

    Returns:
        FeedResult with parsed entries or error
    """
    feed_url = FEED_URL_TEMPLATE.format(channel_id=channel_id)
    logger.debug("Fetching feed for channel %s: %s", channel_id, feed_url)

    try:
        close_client = False
        if http_client is None:
            http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
            close_client = True

        try:
            response = await http_client.get(feed_url, headers={
                "User-Agent": "PBHeroBot/1.0 (Feed Reader)",
                "Accept": "application/atom+xml, application/xml, text/xml",
            })
            response.raise_for_status()
        finally:
            if close_client:
                await http_client.aclose()

        # Parse the Atom feed
        feed = feedparser.parse(response.text)

        if feed.bozo and not feed.entries:
            error_msg = str(feed.bozo_exception) if hasattr(feed, "bozo_exception") else "Feed parse error"
            logger.warning("Feed parse issue for %s: %s", channel_id, error_msg)
            return FeedResult(success=False, channel_id=channel_id, error=error_msg)

        # Extract channel info
        channel_name = ""
        if hasattr(feed, "feed") and hasattr(feed.feed, "title"):
            channel_name = feed.feed.title or ""

        # Parse entries
        entries = []
        for entry in feed.entries:
            video_id = ""
            if hasattr(entry, "yt_videoid"):
                video_id = entry.yt_videoid
            elif hasattr(entry, "id"):
                # Extract from tag:youtube.com,2008:video:VIDEO_ID
                parts = entry.id.split(":")
                if len(parts) >= 4:
                    video_id = parts[-1]

            if not video_id:
                continue

            # Get thumbnail
            thumbnail = ""
            if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                thumbnail = entry.media_thumbnail[0].get("url", "")
            elif video_id:
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

            # Get description
            description = ""
            if hasattr(entry, "media_group") and entry.media_group:
                for content in entry.media_group:
                    if hasattr(content, "media_description"):
                        description = content.media_description or ""
                        break

            feed_entry = FeedEntry(
                video_id=video_id,
                title=entry.get("title", "Untitled"),
                url=entry.get("link", f"https://www.youtube.com/watch?v={video_id}"),
                published=_parse_datetime(entry.get("published_parsed")),
                updated=_parse_datetime(entry.get("updated_parsed")),
                channel_id=channel_id,
                channel_name=channel_name,
                thumbnail_url=thumbnail,
                description=description[:500] if description else "",
            )
            entries.append(feed_entry)

        logger.info("Parsed %d entries from feed for channel %s (%s)", len(entries), channel_id, channel_name)
        return FeedResult(
            success=True,
            channel_id=channel_id,
            channel_name=channel_name,
            entries=entries,
        )

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
        logger.error("Feed fetch failed for %s: %s", channel_id, error_msg)
        return FeedResult(success=False, channel_id=channel_id, error=error_msg)
    except httpx.TimeoutException:
        logger.error("Feed fetch timed out for %s", channel_id)
        return FeedResult(success=False, channel_id=channel_id, error="Request timed out")
    except Exception as e:
        logger.error("Feed fetch error for %s: %s", channel_id, str(e))
        return FeedResult(success=False, channel_id=channel_id, error=str(e))
