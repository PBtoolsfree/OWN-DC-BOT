"""
PB HERO YouTube Feed Parser.

Parses YouTube Atom XML feeds with production-grade reliability:
- Canonical /xml/feeds/videos.xml endpoint with single bounded fallback
- Asynchronous HTTP client with connection and request timeouts
- Separate handling for HTTP 200, 304, 404, 429, and 5xx responses
- Bounded exponential backoff and Retry-After respect
- Per-channel concurrency locking
- Proper XML namespace parsing and channel ID verification
- Safe degradation when optional metadata is missing
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Tuple

import feedparser
import httpx

from app.youtube.channel_resolver import (
    build_feed_url,
    build_legacy_feed_url,
    sanitize_channel_id,
)

logger = logging.getLogger("pbhero.youtube")

DEFAULT_TIMEOUT = httpx.Timeout(timeout=30.0, connect=10.0, read=20.0, write=10.0)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
        "(PBHeroBot/1.0; +https://github.com/PBtoolsfree/OWN-DC-BOT)"
    ),
    "Accept": "application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RETRIES = 2
INITIAL_BACKOFF = 1.0

# Per-channel concurrency lock to prevent overlapping requests for the same channel
_channel_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


async def _get_channel_lock(channel_id: str) -> asyncio.Lock:
    """Get or create an asyncio.Lock for the given channel ID."""
    async with _locks_guard:
        if channel_id not in _channel_locks:
            _channel_locks[channel_id] = asyncio.Lock()
        return _channel_locks[channel_id]


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
    feed_url: str = ""
    http_status: Optional[int] = None
    content_type: str = ""
    fetched_at: Optional[datetime] = None
    parsed_at: Optional[datetime] = None
    consecutive_failures: int = 0
    next_retry_at: Optional[datetime] = None
    is_degraded: bool = False


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
        date_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _parse_atom_xml(
    xml_text: str,
    expected_channel_id: str,
    content_type: str = "",
) -> Tuple[bool, str, list[FeedEntry], Optional[str]]:
    """
    Parse Atom XML into entries with validation and graceful degradation.

    Returns:
        (success, channel_name, entries, error_message)
    """
    clean_text = xml_text.strip()

    # Detect HTML error pages returned instead of XML
    if clean_text.lower().startswith(("<!doctype html", "<html")) or "text/html" in content_type.lower():
        error_msg = "YouTube returned an HTML error page instead of XML Atom feed"
        logger.warning("%s for channel %s", error_msg, expected_channel_id)
        return False, "", [], error_msg

    feed = feedparser.parse(clean_text)

    # Malformed XML with no feed or entries
    if feed.bozo and not getattr(feed, "entries", None) and not getattr(feed, "feed", None):
        bozo_msg = str(getattr(feed, "bozo_exception", "Malformed XML"))
        logger.warning("Feed XML parse error for %s: %s", expected_channel_id, bozo_msg)
        return False, "", [], f"Malformed XML feed: {bozo_msg}"

    # Feed-level metadata
    channel_name = ""
    feed_channel_id = ""
    if hasattr(feed, "feed"):
        channel_name = getattr(feed.feed, "title", "") or ""
        feed_channel_id = getattr(feed.feed, "yt_channelid", "") or ""
        if not feed_channel_id and hasattr(feed.feed, "id"):
            parts = str(feed.feed.id).split(":")
            if len(parts) >= 3 and parts[-1].startswith("UC"):
                feed_channel_id = parts[-1]

    # Verify channel ID at feed level if present
    if feed_channel_id and feed_channel_id != expected_channel_id:
        err = f"Feed channel ID mismatch: got '{feed_channel_id}', expected '{expected_channel_id}'"
        logger.error(err)
        return False, channel_name, [], err

    entries: list[FeedEntry] = []
    for entry in getattr(feed, "entries", []):
        video_id = ""
        if hasattr(entry, "yt_videoid") and entry.yt_videoid:
            video_id = entry.yt_videoid
        elif hasattr(entry, "id") and entry.id:
            parts = str(entry.id).split(":")
            if len(parts) >= 4:
                video_id = parts[-1]

        if not video_id:
            continue

        # Verify entry channel ID if present
        entry_channel_id = getattr(entry, "yt_channelid", None) or expected_channel_id
        if entry_channel_id and entry_channel_id != expected_channel_id:
            logger.warning(
                "Skipping entry %s: channel ID '%s' does not match '%s'",
                video_id, entry_channel_id, expected_channel_id
            )
            continue

        # Extract alternate URL
        url = ""
        if hasattr(entry, "links") and entry.links:
            for link in entry.links:
                if link.get("rel") == "alternate" and link.get("href"):
                    url = link.get("href")
                    break
        if not url:
            url = entry.get("link", f"https://www.youtube.com/watch?v={video_id}")

        # Extract thumbnail
        thumbnail = ""
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            thumbnail = entry.media_thumbnail[0].get("url", "")
        if not thumbnail and video_id:
            thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        # Extract description
        description = ""
        if hasattr(entry, "media_group") and entry.media_group:
            for content in entry.media_group:
                if hasattr(content, "media_description") and content.media_description:
                    description = content.media_description
                    break
        if not description and hasattr(entry, "summary") and entry.summary:
            description = entry.summary

        pub_dt = _parse_datetime(entry.get("published_parsed")) or _parse_datetime_str(entry.get("published"))
        upd_dt = _parse_datetime(entry.get("updated_parsed")) or _parse_datetime_str(entry.get("updated"))

        feed_entry = FeedEntry(
            video_id=video_id,
            title=entry.get("title", "Untitled"),
            url=url,
            published=pub_dt,
            updated=upd_dt,
            channel_id=expected_channel_id,
            channel_name=channel_name,
            thumbnail_url=thumbnail,
            description=description[:500] if description else "",
        )
        entries.append(feed_entry)

    return True, channel_name, entries, None


async def fetch_feed(
    channel_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
    allow_fallback: bool = True,
) -> FeedResult:
    """
    Fetch and parse a YouTube channel's Atom feed using canonical endpoints,
    separate status code handling, bounded retries, and per-channel concurrency lock.

    Args:
        channel_id: YouTube channel ID (UC format)
        http_client: Optional reusable HTTP client
        allow_fallback: Whether to fallback to legacy URL on 404/5xx

    Returns:
        FeedResult with parsed entries or error diagnostics
    """
    # 1. Validate channel ID
    try:
        clean_channel_id = sanitize_channel_id(channel_id)
    except ValueError as e:
        logger.error("Channel validation error: %s", e)
        return FeedResult(success=False, channel_id=channel_id, error=str(e))

    # 2. Acquire channel lock to prevent overlapping concurrent checks
    channel_lock = await _get_channel_lock(clean_channel_id)
    async with channel_lock:
        canonical_url = build_feed_url(clean_channel_id)
        legacy_url = build_legacy_feed_url(clean_channel_id)
        current_target_url = canonical_url

        close_client = False
        client = http_client
        if client is None:
            client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True)
            close_client = True

        try:
            fallback_attempted = False

            while True:
                last_error: Optional[str] = None
                last_status: Optional[int] = None
                content_type = ""
                response_text = ""

                for attempt in range(MAX_RETRIES + 1):
                    try:
                        logger.debug(
                            "Fetching YouTube feed for %s (attempt %d): %s",
                            clean_channel_id, attempt + 1, current_target_url
                        )
                        response = await client.get(current_target_url, headers=DEFAULT_HEADERS)
                        last_status = response.status_code
                        content_type = response.headers.get("content-type", "")

                        # Handle status codes separately
                        if response.status_code == 200:
                            response_text = response.text
                            fetched_at = datetime.utcnow()
                            success, channel_name, entries, parse_error = _parse_atom_xml(
                                response_text, clean_channel_id, content_type
                            )

                            if success:
                                logger.info(
                                    "Successfully parsed %d entries from feed for %s (%s)",
                                    len(entries), clean_channel_id, channel_name
                                )
                                return FeedResult(
                                    success=True,
                                    channel_id=clean_channel_id,
                                    channel_name=channel_name,
                                    entries=entries,
                                    feed_url=current_target_url,
                                    http_status=200,
                                    content_type=content_type,
                                    fetched_at=fetched_at,
                                    parsed_at=datetime.utcnow(),
                                )
                            else:
                                # Parsing failed or HTML returned
                                last_error = parse_error
                                break

                        elif response.status_code == 304:
                            logger.info("Feed not modified (304) for %s", clean_channel_id)
                            return FeedResult(
                                success=True,
                                channel_id=clean_channel_id,
                                feed_url=current_target_url,
                                http_status=304,
                                content_type=content_type,
                                fetched_at=datetime.utcnow(),
                                parsed_at=datetime.utcnow(),
                            )

                        elif response.status_code == 404:
                            last_error = f"HTTP 404: Channel feed not found at {current_target_url}"
                            logger.warning(
                                "HTTP 404 from feed endpoint for %s: %s",
                                clean_channel_id, current_target_url
                            )
                            # Do not retry 404 on the same URL; break to fallback logic
                            break

                        elif response.status_code == 429:
                            # Rate limited - check Retry-After
                            retry_after_val = 60
                            retry_after_hdr = response.headers.get("Retry-After")
                            if retry_after_hdr and retry_after_hdr.isdigit():
                                retry_after_val = int(retry_after_hdr)

                            last_error = f"HTTP 429: Rate limited by YouTube (Retry-After: {retry_after_val}s)"
                            logger.warning(
                                "Rate limit 429 for %s. Retry-After=%ds", clean_channel_id, retry_after_val
                            )

                            if attempt < MAX_RETRIES and retry_after_val <= 5:
                                await asyncio.sleep(retry_after_val)
                                continue

                            next_retry = datetime.utcnow() + timedelta(seconds=retry_after_val)
                            return FeedResult(
                                success=False,
                                channel_id=clean_channel_id,
                                feed_url=current_target_url,
                                http_status=429,
                                content_type=content_type,
                                error=last_error,
                                next_retry_at=next_retry,
                                is_degraded=True,
                            )

                        elif response.status_code >= 500:
                            last_error = f"HTTP {response.status_code}: YouTube service temporarily unavailable"
                            logger.warning(
                                "HTTP %d server error for %s (attempt %d)",
                                response.status_code, clean_channel_id, attempt + 1
                            )
                            if attempt < MAX_RETRIES:
                                backoff = INITIAL_BACKOFF * (2 ** attempt)
                                await asyncio.sleep(backoff)
                                continue
                            break

                        else:
                            last_error = f"HTTP {response.status_code}: Unexpected response"
                            break

                    except (httpx.TimeoutException, httpx.ConnectTimeout) as e:
                        last_error = "Feed request timed out"
                        logger.warning(
                            "Timeout fetching feed for %s (attempt %d): %s",
                            clean_channel_id, attempt + 1, e
                        )
                        if attempt < MAX_RETRIES:
                            backoff = INITIAL_BACKOFF * (2 ** attempt)
                            await asyncio.sleep(backoff)
                            continue
                        break

                    except httpx.HTTPError as e:
                        last_error = f"Network error: {str(e)}"
                        logger.warning(
                            "Network error fetching feed for %s (attempt %d): %s",
                            clean_channel_id, attempt + 1, e
                        )
                        if attempt < MAX_RETRIES:
                            backoff = INITIAL_BACKOFF * (2 ** attempt)
                            await asyncio.sleep(backoff)
                            continue
                        break

                # 3. Check bounded fallback to legacy endpoint
                if (
                    allow_fallback
                    and not fallback_attempted
                    and current_target_url == canonical_url
                ):
                    fallback_attempted = True
                    current_target_url = legacy_url
                    logger.info(
                        "Attempting single bounded fallback to legacy endpoint for %s: %s",
                        clean_channel_id, legacy_url
                    )
                    continue

                # Both attempts / retries exhausted
                logger.error("Feed fetch ultimately failed for %s: %s", clean_channel_id, last_error)
                return FeedResult(
                    success=False,
                    channel_id=clean_channel_id,
                    feed_url=current_target_url,
                    http_status=last_status,
                    content_type=content_type,
                    error=last_error or "Unknown feed fetch failure",
                    is_degraded=True,
                    next_retry_at=datetime.utcnow() + timedelta(minutes=2),
                )

        finally:
            if close_client:
                await client.aclose()
