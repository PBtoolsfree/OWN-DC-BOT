"""
PB HERO YouTube Channel Resolver.

Resolves various YouTube URL formats to a stable channel ID.
Supports: @handle, /channel/UCxxxx, /c/name, UCxxxx direct
No API key required - uses public page metadata.
"""

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger("pbhero.youtube")

# Patterns for YouTube URLs
CHANNEL_ID_PATTERN = re.compile(r"^UC[\w-]{22}$")
HANDLE_PATTERN = re.compile(r"^@[\w.-]+$")
URL_PATTERNS = [
    # https://youtube.com/@handle
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/@([\w.-]+)"),
    # https://youtube.com/channel/UCxxxx
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/channel/(UC[\w-]{22})"),
    # https://youtube.com/c/channelname
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/c/([\w.-]+)"),
    # https://youtube.com/user/username
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/user/([\w.-]+)"),
]

# Look for channel ID in page source
CHANNEL_ID_META_PATTERNS = [
    re.compile(r'"channelId"\s*:\s*"(UC[\w-]{22})"'),
    re.compile(r'<meta\s+itemprop="channelId"\s+content="(UC[\w-]{22})"'),
    re.compile(r'"externalId"\s*:\s*"(UC[\w-]{22})"'),
    re.compile(r'data-channel-external-id="(UC[\w-]{22})"'),
    re.compile(r'browse_id.*?"(UC[\w-]{22})"'),
]


async def resolve_channel_id(input_str: str, http_client: httpx.AsyncClient = None) -> Optional[dict]:
    """
    Resolve a YouTube channel URL/handle/ID to a stable channel ID.

    Args:
        input_str: YouTube URL, @handle, or channel ID
        http_client: Optional reusable HTTP client

    Returns:
        Dict with channel_id, channel_name, handle or None
    """
    input_str = input_str.strip()
    logger.debug("Resolving YouTube channel: %s", input_str)

    # Direct channel ID
    if CHANNEL_ID_PATTERN.match(input_str):
        logger.info("Direct channel ID: %s", input_str)
        return {"channel_id": input_str, "channel_name": None, "handle": None}

    # Extract identifier from URL patterns
    identifier = None
    is_channel_url = False

    for pattern in URL_PATTERNS:
        match = pattern.match(input_str)
        if match:
            identifier = match.group(1)
            if CHANNEL_ID_PATTERN.match(identifier):
                return {"channel_id": identifier, "channel_name": None, "handle": None}
            break

    # Handle format (@handle)
    if not identifier:
        if HANDLE_PATTERN.match(input_str):
            identifier = input_str.lstrip("@")
        elif not input_str.startswith("http"):
            identifier = input_str

    if not identifier:
        logger.error("Cannot parse YouTube channel input: %s", input_str)
        return None

    # Resolve by fetching the channel page
    try:
        close_client = False
        if http_client is None:
            http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
            close_client = True

        try:
            # Try @handle URL first
            urls_to_try = [
                f"https://www.youtube.com/@{identifier}",
                f"https://www.youtube.com/c/{identifier}",
            ]

            for url in urls_to_try:
                try:
                    response = await http_client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept-Language": "en-US,en;q=0.9",
                    })
                    if response.status_code == 200:
                        page_text = response.text

                        # Extract channel ID from page metadata
                        for pattern in CHANNEL_ID_META_PATTERNS:
                            match = pattern.search(page_text)
                            if match:
                                channel_id = match.group(1)

                                # Try to extract channel name
                                channel_name = None
                                name_match = re.search(r'"name"\s*:\s*"([^"]+)"', page_text)
                                if name_match:
                                    channel_name = name_match.group(1)

                                logger.info("Resolved %s → %s (%s)", input_str, channel_id, channel_name)
                                return {
                                    "channel_id": channel_id,
                                    "channel_name": channel_name,
                                    "handle": f"@{identifier}",
                                }

                except httpx.HTTPError:
                    continue

        finally:
            if close_client:
                await http_client.aclose()

    except Exception as e:
        logger.error("Channel resolution error for %s: %s", input_str, str(e))

    logger.warning("Could not resolve channel ID for: %s", input_str)
    return None


def build_feed_url(channel_id: str) -> str:
    """Build the Atom feed URL for a channel ID."""
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
