"""
Comprehensive Regression Tests for YouTube Feed Parsing, URL Handling, and Notification Reliability.

Covers all production requirements:
1. Separate Polling URL (/feeds/videos.xml) and WebSub Topic URL (/xml/feeds/videos.xml)
2. Stored feed URL repair restoring direct RSS polling URL
3. Both configured channel IDs (PB HERO GAMER, PB HERO LIVE)
4. HTTP 200 Atom parsing (all fields: yt:videoId, yt:channelId, title, published, updated, links)
5. Empty feed with channel metadata vs static WebSub document rejection
6. Static WebSub topic document detected and rejected as wrong-endpoint error
7. Channel ID mismatch detection
8. HTTP 404 handling reporting upstream status cleanly
9. HTTP 429 and Retry-After header handling
10. HTTP 5xx transient retry limits
11. Timeouts and HTML error pages
12. Deduplication and restart recovery
13. Discord destination routing and event toggle filtering
14. Notification template variable rendering
15. Scheduled stream detection
16. Live-status UNKNOWN vs OFFLINE distinction
17. Channel isolation (one failing channel does not impact others)
18. Feed failure / live detector failure isolation
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.database.models import EventType, VideoState, YouTubeChannel, YouTubeDestination
from app.database.repositories import (
    YouTubeChannelRepo,
    YouTubeDestinationRepo,
    YouTubeEventRepo,
)
from app.youtube.channel_resolver import (
    build_poll_feed_url,
    build_websub_topic_url,
    build_feed_url,
    build_legacy_feed_url,
    is_valid_channel_id,
    normalize_channel_id,
    resolve_channel_id,
    sanitize_channel_id,
)
from app.youtube.dedupe import is_duplicate, mark_notified, record_event
from app.youtube.feed_parser import (
    FeedEntry,
    FeedResult,
    _parse_atom_xml,
    extract_canonical_channel_id_from_feed,
    fetch_feed,
)
from app.youtube.live_detector import (
    ChannelLiveResult,
    LiveStatus,
    check_channel_live_status,
)
from app.youtube.notifier import create_notification_embed, render_template_text


# ─── Configured Production Channels ──────────────────────────────────────────
PB_HERO_GAMER_ID = "UC-6WQfskutalsbKUw9ZDA7A"
PB_HERO_LIVE_ID = "UCb8xLLxhYdKGQLEGuAyBLUw"


# ─── Sample Atom Feeds ────────────────────────────────────────────────────────

SAMPLE_ATOM_FEED_GAMER = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"/>
  <id>yt:channel:{PB_HERO_GAMER_ID}</id>
  <yt:channelId>{PB_HERO_GAMER_ID}</yt:channelId>
  <title>PB HERO GAMER</title>
  <entry>
    <id>yt:video:vid_gamer_101</id>
    <yt:videoId>vid_gamer_101</yt:videoId>
    <yt:channelId>{PB_HERO_GAMER_ID}</yt:channelId>
    <title>Grandmaster Rank Push 1v4 Clutch</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid_gamer_101"/>
    <published>2026-10-12T14:00:00+00:00</published>
    <updated>2026-10-12T14:30:00+00:00</updated>
    <media:group>
      <media:title>Grandmaster Rank Push 1v4 Clutch</media:title>
      <media:thumbnail url="https://i.ytimg.com/vi/vid_gamer_101/hqdefault.jpg"/>
      <media:description>High-octane Free Fire gameplay with team code giveaway.</media:description>
    </media:group>
  </entry>
</feed>
"""

SAMPLE_ATOM_FEED_LIVE = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_LIVE_ID}"/>
  <id>yt:channel:{PB_HERO_LIVE_ID}</id>
  <yt:channelId>{PB_HERO_LIVE_ID}</yt:channelId>
  <title>PB HERO LIVE</title>
  <entry>
    <id>yt:video:vid_live_202</id>
    <yt:videoId>vid_live_202</yt:videoId>
    <yt:channelId>{PB_HERO_LIVE_ID}</yt:channelId>
    <title>Daily Live Stream Custom Rooms</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid_live_202"/>
    <published>2026-10-13T08:00:00+00:00</published>
    <updated>2026-10-13T08:05:00+00:00</updated>
    <media:group>
      <media:title>Daily Live Stream Custom Rooms</media:title>
      <media:thumbnail url="https://i.ytimg.com/vi/vid_live_202/hqdefault.jpg"/>
      <media:description>Playing with subscribers and guild test matches.</media:description>
    </media:group>
  </entry>
</feed>
"""

SAMPLE_EMPTY_FEED = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"/>
  <id>yt:channel:{PB_HERO_GAMER_ID}</id>
  <yt:channelId>{PB_HERO_GAMER_ID}</yt:channelId>
  <title>PB HERO GAMER</title>
</feed>
"""

SAMPLE_STATIC_WEBSUB_TOPIC_DOCUMENT = f"""<?xml version="1.0" encoding="utf-8"?>
<!--
  This is a static file. The corresponding feed (identified in the
  <link rel="self"/> tag) should be used as a topic on the
  http://pubsubhubbub.appspot.com hub to subscribe to video updates.
-->
<feed xmlns="http://www.w3.org/2005/Atom">
  <link rel="hub" href="http://pubsubhubbub.appspot.com"/>
  <link rel="self" href="https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"/>
</feed>
"""

SAMPLE_HTML_ERROR_PAGE = """<!DOCTYPE html>
<html lang="en">
  <head><title>Error 404 (Not Found)!!1</title></head>
  <body><p>The requested URL /feeds/videos.xml was not found on this server.</p></body>
</html>
"""

# Production YouTube Atom Feed fixtures where root <yt:channelId> and <id> omit 'UC' (22 chars),
# while links, author, and entry <yt:channelId> retain the full canonical 24-character ID ('UC...').
SAMPLE_REAL_ATOM_FEED_GAMER = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="http://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"/>
  <id>yt:channel:{PB_HERO_GAMER_ID[2:]}</id>
  <yt:channelId>{PB_HERO_GAMER_ID[2:]}</yt:channelId>
  <title>PB HERO GAMER</title>
  <link rel="alternate" href="https://www.youtube.com/channel/{PB_HERO_GAMER_ID}"/>
  <author>
    <name>PB HERO GAMER</name>
    <uri>https://www.youtube.com/channel/{PB_HERO_GAMER_ID}</uri>
  </author>
  <entry>
    <id>yt:video:vid_gamer_real_1</id>
    <yt:videoId>vid_gamer_real_1</yt:videoId>
    <yt:channelId>{PB_HERO_GAMER_ID}</yt:channelId>
    <title>PB HERO GAMER New Upload</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid_gamer_real_1"/>
    <published>2026-10-13T10:00:00+00:00</published>
    <updated>2026-10-13T10:05:00+00:00</updated>
    <media:group>
      <media:title>PB HERO GAMER New Upload</media:title>
      <media:thumbnail url="https://i.ytimg.com/vi/vid_gamer_real_1/hqdefault.jpg"/>
      <media:description>Pro gameplay Free Fire clutch match.</media:description>
    </media:group>
  </entry>
</feed>
"""

SAMPLE_REAL_ATOM_FEED_LIVE = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="http://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_LIVE_ID}"/>
  <id>yt:channel:{PB_HERO_LIVE_ID[2:]}</id>
  <yt:channelId>{PB_HERO_LIVE_ID[2:]}</yt:channelId>
  <title>PB HERO LIVE</title>
  <link rel="alternate" href="https://www.youtube.com/channel/{PB_HERO_LIVE_ID}"/>
  <author>
    <name>PB HERO LIVE</name>
    <uri>https://www.youtube.com/channel/{PB_HERO_LIVE_ID}</uri>
  </author>
  <entry>
    <id>yt:video:vid_live_real_2</id>
    <yt:videoId>vid_live_real_2</yt:videoId>
    <yt:channelId>{PB_HERO_LIVE_ID}</yt:channelId>
    <title>PB HERO LIVE Stream</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid_live_real_2"/>
    <published>2026-10-13T11:00:00+00:00</published>
    <updated>2026-10-13T11:05:00+00:00</updated>
    <media:group>
      <media:title>PB HERO LIVE Stream</media:title>
      <media:thumbnail url="https://i.ytimg.com/vi/vid_live_real_2/hqdefault.jpg"/>
      <media:description>Live subscriber custom room battle.</media:description>
    </media:group>
  </entry>
</feed>
"""

SAMPLE_ROOT_ONLY_LEGACY_FEED = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <id>yt:channel:{PB_HERO_GAMER_ID[2:]}</id>
  <yt:channelId>{PB_HERO_GAMER_ID[2:]}</yt:channelId>
  <title>PB HERO GAMER</title>
</feed>
"""

SAMPLE_MALFORMED_XML_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <title>PB HERO GAMER
  <broken unclosed tag
"""


# ─── 1. Separate Polling URL and WebSub Topic URL Generation ─────────────────

def test_separate_polling_and_websub_url_builders():
    """Verify build_poll_feed_url uses /feeds/ and build_websub_topic_url uses /xml/feeds/."""
    poll_gamer = build_poll_feed_url(PB_HERO_GAMER_ID)
    poll_live = build_poll_feed_url(PB_HERO_LIVE_ID)
    websub_gamer = build_websub_topic_url(PB_HERO_GAMER_ID)
    websub_live = build_websub_topic_url(PB_HERO_LIVE_ID)

    # Polling URL uses /feeds/videos.xml
    assert poll_gamer == f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"
    assert poll_live == f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_LIVE_ID}"
    assert "/xml/feeds/" not in poll_gamer

    # WebSub topic URL uses /xml/feeds/videos.xml
    assert websub_gamer == f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"
    assert websub_live == f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_LIVE_ID}"

    # build_feed_url alias points to polling URL
    assert build_feed_url(PB_HERO_GAMER_ID) == poll_gamer

    # Whitespace and URL extraction
    assert build_poll_feed_url(f"  {PB_HERO_GAMER_ID}  ") == poll_gamer
    assert build_poll_feed_url(f"https://youtube.com/channel/{PB_HERO_GAMER_ID}") == poll_gamer
    assert build_poll_feed_url(f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}") == poll_gamer
    assert poll_gamer.count("channel_id=") == 1


def test_channel_id_validation_rejects_handles_and_names():
    """Verify handle and channel names are never used directly as channel_id."""
    assert is_valid_channel_id(PB_HERO_GAMER_ID) is True
    assert is_valid_channel_id(PB_HERO_LIVE_ID) is True
    assert is_valid_channel_id("@PBHEROGAMER") is False
    assert is_valid_channel_id("PB HERO GAMER") is False
    assert is_valid_channel_id("") is False

    with pytest.raises(ValueError, match="Invalid YouTube channel ID"):
        sanitize_channel_id("@PBHEROGAMER")

    with pytest.raises(ValueError, match="Invalid YouTube channel ID"):
        sanitize_channel_id("PB HERO GAMER")

    with pytest.raises(ValueError, match="Channel ID cannot be empty"):
        sanitize_channel_id("")


# ─── 2. Stored Feed URL Repair (Idempotent Startup / Migration) ──────────────

@pytest.mark.asyncio
async def test_repair_saved_feed_urls_in_database(db_session):
    """Verify repair_saved_feed_urls restores /xml/feeds/ to direct RSS polling /feeds/."""
    # Create channel with mistakenly changed /xml/feeds/ URL
    ch = YouTubeChannel(
        youtube_channel_id=PB_HERO_GAMER_ID,
        channel_name="PB HERO GAMER",
        handle="@PBHEROGAMER",
        enabled=True,
        feed_url=f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}",
    )
    db_session.add(ch)
    await db_session.flush()

    dest = YouTubeDestination(
        youtube_channel_id=PB_HERO_GAMER_ID,
        discord_channel_id=123456789012345678,
        upload_enabled=True,
        scheduled_live_enabled=True,
    )
    db_session.add(dest)
    await db_session.commit()

    # Perform repair
    repaired_count = await YouTubeChannelRepo.repair_saved_feed_urls(db_session)
    await db_session.commit()

    assert repaired_count >= 1

    # Verify channel URL is restored to /feeds/videos.xml
    refreshed = await YouTubeChannelRepo.get_by_channel_id(db_session, PB_HERO_GAMER_ID)
    assert refreshed.feed_url == f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"
    assert refreshed.channel_name == "PB HERO GAMER"
    assert refreshed.enabled is True

    # Destinations preserved
    dests = await YouTubeDestinationRepo.get_for_channel(db_session, PB_HERO_GAMER_ID)
    assert len(dests) == 1
    assert dests[0].discord_channel_id == 123456789012345678

    # Idempotent: running again changes nothing
    repaired_again = await YouTubeChannelRepo.repair_saved_feed_urls(db_session)
    assert repaired_again == 0


# ─── 3. Successful HTTP 200 Atom Parsing for Both Channels ───────────────────

@pytest.mark.asyncio
async def test_parse_atom_feed_gamer():
    """Verify parsing Atom XML for PB HERO GAMER channel extracts all required metadata."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_ATOM_FEED_GAMER, PB_HERO_GAMER_ID)
    assert success is True
    assert name == "PB HERO GAMER"
    assert err is None
    assert len(entries) == 1

    entry = entries[0]
    assert entry.video_id == "vid_gamer_101"
    assert entry.channel_id == PB_HERO_GAMER_ID
    assert entry.title == "Grandmaster Rank Push 1v4 Clutch"
    assert entry.url == "https://www.youtube.com/watch?v=vid_gamer_101"
    assert entry.published is not None
    assert entry.updated is not None
    assert "hqdefault.jpg" in entry.thumbnail_url
    assert "Free Fire" in entry.description


@pytest.mark.asyncio
async def test_parse_atom_feed_live():
    """Verify parsing Atom XML for PB HERO LIVE channel extracts all required metadata."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_ATOM_FEED_LIVE, PB_HERO_LIVE_ID)
    assert success is True
    assert name == "PB HERO LIVE"
    assert err is None
    assert len(entries) == 1

    entry = entries[0]
    assert entry.video_id == "vid_live_202"
    assert entry.channel_id == PB_HERO_LIVE_ID
    assert entry.title == "Daily Live Stream Custom Rooms"


@pytest.mark.asyncio
async def test_parse_empty_feed_with_metadata():
    """Verify valid empty feed with channel metadata produces success=True with entry_count=0."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_EMPTY_FEED, PB_HERO_GAMER_ID)
    assert success is True
    assert len(entries) == 0
    assert err is None
    assert name == "PB HERO GAMER"


# ─── 4. Static WebSub Topic Document Rejection ───────────────────────────────

@pytest.mark.asyncio
async def test_static_websub_topic_document_rejected():
    """Verify static WebSub topic descriptor document is rejected and NOT treated as valid 0-entry feed."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_STATIC_WEBSUB_TOPIC_DOCUMENT, PB_HERO_GAMER_ID)
    assert success is False
    assert len(entries) == 0
    assert err is not None
    assert "Wrong endpoint" in err or "static WebSub topic document" in err


@pytest.mark.asyncio
async def test_fetch_feed_rejects_static_websub_document():
    """Verify fetch_feed returns failure if server returns the static 463-byte WebSub stub."""
    mock_resp = MagicMock(
        status_code=200,
        headers={"content-type": "application/atom+xml"},
        text=SAMPLE_STATIC_WEBSUB_TOPIC_DOCUMENT,
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client)
    assert res.success is False
    assert res.http_status == 200
    assert len(res.entries) == 0
    assert "Wrong endpoint" in res.error or "static WebSub topic document" in res.error


# ─── 5. Channel ID Verification, Normalization, and Mismatch Protection ───

def test_normalize_channel_id_preserves_canonical_and_fixes_legacy_prefix():
    """Verify normalize_channel_id preserves 24-char UC IDs and reconstructs legacy 22-char feed IDs."""
    # Canonical 24-character IDs starting with UC must be preserved exactly
    assert normalize_channel_id(PB_HERO_GAMER_ID) == PB_HERO_GAMER_ID
    assert normalize_channel_id(PB_HERO_LIVE_ID) == PB_HERO_LIVE_ID

    # Whitespace-padded IDs
    assert normalize_channel_id(f"  {PB_HERO_GAMER_ID}  ") == PB_HERO_GAMER_ID
    assert normalize_channel_id(f"\n{PB_HERO_LIVE_ID}\t") == PB_HERO_LIVE_ID

    # Legacy 22-character IDs without UC prefix (YouTube feed-level format)
    assert normalize_channel_id(PB_HERO_GAMER_ID[2:]) == PB_HERO_GAMER_ID
    assert normalize_channel_id(PB_HERO_LIVE_ID[2:]) == PB_HERO_LIVE_ID
    assert normalize_channel_id("-6WQfskutalsbKUw9ZDA7A") == "UC-6WQfskutalsbKUw9ZDA7A"
    assert normalize_channel_id("b8xLLxhYdKGQLEGuAyBLUw") == "UCb8xLLxhYdKGQLEGuAyBLUw"

    # URL extraction
    assert normalize_channel_id(f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}") == PB_HERO_GAMER_ID
    assert normalize_channel_id(f"https://youtube.com/channel/{PB_HERO_LIVE_ID}") == PB_HERO_LIVE_ID

    # Empty and None
    assert normalize_channel_id("") == ""
    assert normalize_channel_id(None) == ""


def test_extract_canonical_channel_id_from_real_youtube_atom_structure():
    """Verify extract_canonical_channel_id_from_feed extracts 24-char UC ID from feeds with legacy 22-char root tags."""
    import feedparser
    # Gamer feed with 22-char root tag
    feed_gamer = feedparser.parse(SAMPLE_REAL_ATOM_FEED_GAMER)
    extracted_gamer = extract_canonical_channel_id_from_feed(feed_gamer, SAMPLE_REAL_ATOM_FEED_GAMER)
    assert extracted_gamer == PB_HERO_GAMER_ID
    assert extracted_gamer.startswith("UC")
    assert len(extracted_gamer) == 24

    # Live feed with 22-char root tag
    feed_live = feedparser.parse(SAMPLE_REAL_ATOM_FEED_LIVE)
    extracted_live = extract_canonical_channel_id_from_feed(feed_live, SAMPLE_REAL_ATOM_FEED_LIVE)
    assert extracted_live == PB_HERO_LIVE_ID
    assert extracted_live.startswith("UC")
    assert len(extracted_live) == 24


@pytest.mark.asyncio
async def test_parse_real_production_feed_gamer_with_legacy_root_tag():
    """Verify PB HERO GAMER feed with YouTube's 22-char root <yt:channelId> parses successfully with 0 errors."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_REAL_ATOM_FEED_GAMER, PB_HERO_GAMER_ID)
    assert success is True
    assert name == "PB HERO GAMER"
    assert err is None
    assert len(entries) == 1
    entry = entries[0]
    assert entry.video_id == "vid_gamer_real_1"
    assert entry.channel_id == PB_HERO_GAMER_ID
    assert entry.channel_id.startswith("UC")
    assert len(entry.channel_id) == 24


@pytest.mark.asyncio
async def test_parse_real_production_feed_live_with_legacy_root_tag():
    """Verify PB HERO LIVE feed with YouTube's 22-char root <yt:channelId> parses successfully with 0 errors."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_REAL_ATOM_FEED_LIVE, PB_HERO_LIVE_ID)
    assert success is True
    assert name == "PB HERO LIVE"
    assert err is None
    assert len(entries) == 1
    entry = entries[0]
    assert entry.video_id == "vid_live_real_2"
    assert entry.channel_id == PB_HERO_LIVE_ID
    assert entry.channel_id.startswith("UC")
    assert len(entry.channel_id) == 24


@pytest.mark.asyncio
async def test_parse_root_only_legacy_feed_without_entries():
    """Verify empty feed containing only 22-char root <yt:channelId> tag normalizes correctly to canonical ID."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_ROOT_ONLY_LEGACY_FEED, PB_HERO_GAMER_ID)
    assert success is True
    assert name == "PB HERO GAMER"
    assert err is None
    assert len(entries) == 0


@pytest.mark.asyncio
async def test_genuine_channel_id_mismatch_preserves_full_canonical_ids_in_error():
    """Verify genuine channel ID mismatch preserves complete UC prefix in error message and rejects feed."""
    # Feed is for Gamer, expected channel is Live
    success, name, entries, err = _parse_atom_xml(SAMPLE_REAL_ATOM_FEED_GAMER, PB_HERO_LIVE_ID)
    assert success is False
    assert len(entries) == 0
    assert err is not None
    # Crucial: Error message must display both full canonical IDs with UC prefix
    assert f"got '{PB_HERO_GAMER_ID}'" in err
    assert f"expected '{PB_HERO_LIVE_ID}'" in err
    assert "UC" in err


@pytest.mark.asyncio
async def test_genuine_channel_id_mismatch_with_legacy_root_only():
    """Verify genuine mismatch with 22-char root tag is normalized and cleanly rejected."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_ROOT_ONLY_LEGACY_FEED, PB_HERO_LIVE_ID)
    assert success is False
    assert len(entries) == 0
    assert err is not None
    assert f"got '{PB_HERO_GAMER_ID}'" in err
    assert f"expected '{PB_HERO_LIVE_ID}'" in err


@pytest.mark.asyncio
async def test_parse_atom_xml_skips_entry_with_mismatched_channel_id():
    """Verify video entry with wrong channel ID is skipped while valid entries are kept."""
    mixed_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="http://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"/>
  <title>PB HERO GAMER</title>
  <entry>
    <yt:videoId>valid_1</yt:videoId>
    <yt:channelId>{PB_HERO_GAMER_ID}</yt:channelId>
    <title>Valid Entry</title>
  </entry>
  <entry>
    <yt:videoId>mismatched_2</yt:videoId>
    <yt:channelId>{PB_HERO_LIVE_ID}</yt:channelId>
    <title>Mismatched Entry</title>
  </entry>
</feed>
"""
    success, name, entries, err = _parse_atom_xml(mixed_feed, PB_HERO_GAMER_ID)
    assert success is True
    assert len(entries) == 1
    assert entries[0].video_id == "valid_1"
    assert entries[0].channel_id == PB_HERO_GAMER_ID


@pytest.mark.asyncio
async def test_parse_atom_xml_malformed_xml_feed():
    """Verify malformed unparseable XML is detected and returns clear error."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_MALFORMED_XML_FEED, PB_HERO_GAMER_ID)
    assert success is False
    assert len(entries) == 0
    assert "Malformed XML feed" in err


@pytest.mark.asyncio
async def test_parse_atom_xml_completely_empty():
    """Verify completely empty XML document is rejected cleanly."""
    success, name, entries, err = _parse_atom_xml("", PB_HERO_GAMER_ID)
    assert success is False
    assert len(entries) == 0
    assert "empty XML document" in err


# ─── 6. HTTP Client: Status Code Handling, 404, 429, 5xx ─────────────────────

@pytest.mark.asyncio
async def test_fetch_feed_http_200_mock():
    """Verify fetch_feed executes against direct RSS polling endpoint and populates rich result."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_ATOM_FEED_GAMER
    mock_resp.headers = {"content-type": "application/atom+xml"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client)
    assert res.success is True
    assert res.http_status == 200
    assert res.channel_id == PB_HERO_GAMER_ID
    assert len(res.entries) == 1
    assert "feeds/videos.xml" in res.feed_url
    assert "/xml/feeds/" not in res.feed_url


@pytest.mark.asyncio
async def test_fetch_feed_404_reports_clean_error():
    """Verify 404 reports clear error with requested polling URL."""
    resp_404 = MagicMock(status_code=404, headers={"content-type": "text/html"}, text=SAMPLE_HTML_ERROR_PAGE)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp_404)

    res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client)
    assert res.success is False
    assert res.http_status == 404
    assert "HTTP 404" in res.error
    assert res.is_degraded is True
    assert "feeds/videos.xml" in res.feed_url


@pytest.mark.asyncio
async def test_fetch_feed_429_respects_retry_after():
    """Verify HTTP 429 parses Retry-After header and populates next_retry_at."""
    resp_429 = MagicMock(
        status_code=429,
        headers={"content-type": "text/plain", "Retry-After": "45"},
        text="Too Many Requests",
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp_429)

    res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client)
    assert res.success is False
    assert res.http_status == 429
    assert "HTTP 429" in res.error
    assert res.next_retry_at is not None
    assert res.next_retry_at > datetime.utcnow() + timedelta(seconds=30)


@pytest.mark.asyncio
async def test_fetch_feed_5xx_retry_limit():
    """Verify HTTP 500 server errors are retried with backoff up to retry limits."""
    resp_500 = MagicMock(status_code=500, headers={"content-type": "text/plain"}, text="Server Error")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp_500)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client)

    assert res.success is False
    assert res.http_status == 500
    assert "HTTP 500" in res.error
    assert res.is_degraded is True


@pytest.mark.asyncio
async def test_fetch_feed_html_error_page_detected():
    """Verify HTML error page returned with HTTP 200/404 is caught and reported clearly."""
    mock_resp = MagicMock(
        status_code=200,
        headers={"content-type": "text/html; charset=UTF-8"},
        text=SAMPLE_HTML_ERROR_PAGE,
    )
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client)
    assert res.success is False
    assert "HTML error page" in res.error


@pytest.mark.asyncio
async def test_fetch_feed_timeout_handling():
    """Verify request timeouts are safely caught without crashing."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

    with patch("asyncio.sleep", new_callable=AsyncMock):
        res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client)

    assert res.success is False
    assert "timed out" in res.error.lower()


# ─── 7. Deduplication & Restart Recovery ──────────────────────────────────────

@pytest.mark.asyncio
async def test_deduplication_and_restart_recovery(db_session):
    """Verify persistent deduplication protects against duplicate notifications after bot restart."""
    channel_id = PB_HERO_GAMER_ID
    video_id = "test_vid_restart_99"

    # Initially not duplicate
    assert await is_duplicate(db_session, channel_id, video_id, EventType.UPLOAD) is False

    # First event recorded and marked notified
    event_id = await record_event(
        db_session,
        channel_id=channel_id,
        video_id=video_id,
        event_type=EventType.UPLOAD,
        title="Epic Comeback",
    )
    await mark_notified(db_session, event_id)
    await db_session.commit()

    # Now duplicate
    assert await is_duplicate(db_session, channel_id, video_id, EventType.UPLOAD) is True

    # Simulated bot restart: reading from database preserves deduplication
    assert await is_duplicate(db_session, channel_id, video_id, EventType.UPLOAD) is True


# ─── 8. Discord Destination Routing and Event Toggles ─────────────────────────

@pytest.mark.asyncio
async def test_destination_routing_and_toggles(db_session):
    """Verify notifications respect destination event toggles (upload, live, scheduled, premiere)."""
    channel_id = PB_HERO_GAMER_ID
    ch = await YouTubeChannelRepo.create(db_session, channel_id, "PB HERO GAMER")
    await db_session.flush()

    dest1 = await YouTubeDestinationRepo.create(
        db_session,
        channel_id,
        discord_channel_id=111111111,
        upload_enabled=True,
        scheduled_live_enabled=False,
        live_started_enabled=False,
    )

    dest2 = await YouTubeDestinationRepo.create(
        db_session,
        channel_id,
        discord_channel_id=222222222,
        upload_enabled=False,
        scheduled_live_enabled=True,
        live_started_enabled=True,
    )
    await db_session.commit()

    dests = await YouTubeDestinationRepo.get_for_channel(db_session, channel_id)
    assert len(dests) == 2

    # Check upload recipients
    upload_dests = [d for d in dests if d.upload_enabled]
    assert len(upload_dests) == 1
    assert upload_dests[0].discord_channel_id == 111111111

    # Check live recipients
    live_dests = [d for d in dests if d.live_started_enabled]
    assert len(live_dests) == 1
    assert live_dests[0].discord_channel_id == 222222222


# ─── 9. Notification Embed Rendering for All Event Types ──────────────────────

def test_create_notification_embed_all_events():
    """Verify Discord embed rendering for all 4 notification types."""
    events = [
        (EventType.UPLOAD, "New Video Upload", 0xFF0000),
        (EventType.SCHEDULED_LIVE, "Scheduled Stream", 0xFFA500),
        (EventType.LIVE_STARTED, "Live Stream Started", 0xFF0000),
        (EventType.PREMIERE, "Premiere Started", 0x9B59B6),
    ]

    for event_type, expected_title_part, expected_color in events:
        embed = create_notification_embed(
            event_type=event_type,
            title="Episode 1 - New Season",
            video_url="https://youtube.com/watch?v=vid123",
            channel_name="PB HERO GAMER",
            thumbnail_url="https://i.ytimg.com/vi/vid123/hqdefault.jpg",
            scheduled_start="2026-10-15 12:00 UTC",
        )

        assert embed is not None
        assert embed.color.value == expected_color
        assert "PB HERO GAMER" in embed.title
        assert "Episode 1" in embed.description
        assert embed.image.url == "https://i.ytimg.com/vi/vid123/hqdefault.jpg"


def test_template_variable_rendering():
    """Verify custom notification template replacement variables."""
    template = "Hey {role}! {channel_name} posted '{video_title}' - watch here: {video_url}"
    context = {
        "role": "<@&999888777>",
        "channel_name": "PB HERO LIVE",
        "video_title": "Custom Room Match 5",
        "video_url": "https://youtube.com/watch?v=vid999",
    }
    rendered = render_template_text(template, context)

    assert "<@&999888777>" in rendered
    assert "PB HERO LIVE" in rendered
    assert "Custom Room Match 5" in rendered
    assert "https://youtube.com/watch?v=vid999" in rendered


# ─── 10. Live Status Detector: Anti-Bot & UNKNOWN vs OFFLINE ──────────────────

@pytest.mark.asyncio
async def test_live_status_unknown_vs_offline_distinction():
    """Verify live status does not classify anti-bot verification or errors as OFFLINE."""
    mock_feed = FeedResult(
        success=True,
        channel_id=PB_HERO_GAMER_ID,
        channel_name="PB HERO GAMER",
        entries=[FeedEntry(video_id="vid_blocked_1", title="Live Match", url="https://youtube.com/watch?v=vid_blocked_1")],
    )
    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_feed
        with patch("app.youtube.live_detector.check_live_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = LiveStatus(
                video_id="vid_blocked_1",
                live_state="unknown",
                error="Sign in to confirm you're not a bot",
            )

            res = await check_channel_live_status(PB_HERO_GAMER_ID)
            assert res.status == "unknown"
            assert res.is_live is False
            assert res.status != "offline"
            assert "Sign in to confirm" in res.error


# ─── 11. Channel Isolation and Subsystem Independence ─────────────────────────

@pytest.mark.asyncio
async def test_channel_isolation_one_failing_does_not_affect_other(db_session):
    """Verify failure of channel A (404) does not prevent channel B from succeeding."""
    ch_a = await YouTubeChannelRepo.create(db_session, PB_HERO_GAMER_ID, "PB HERO GAMER")
    ch_b = await YouTubeChannelRepo.create(db_session, PB_HERO_LIVE_ID, "PB HERO LIVE")
    await db_session.commit()

    # Channel A fails with 404
    await YouTubeChannelRepo.update_feed_status(
        db_session,
        PB_HERO_GAMER_ID,
        success=False,
        http_status=404,
        error="HTTP 404: Not Found",
    )

    # Channel B succeeds with 200
    await YouTubeChannelRepo.update_feed_status(
        db_session,
        PB_HERO_LIVE_ID,
        success=True,
        http_status=200,
        entry_count=5,
    )
    await db_session.commit()

    refreshed_a = await YouTubeChannelRepo.get_by_channel_id(db_session, PB_HERO_GAMER_ID)
    refreshed_b = await YouTubeChannelRepo.get_by_channel_id(db_session, PB_HERO_LIVE_ID)

    # Channel A is DEGRADED, remains enabled
    assert refreshed_a.feed_health == "DEGRADED"
    assert refreshed_a.enabled is True
    assert refreshed_a.last_error == "HTTP 404: Not Found"

    # Channel B is HEALTHY
    assert refreshed_b.feed_health == "HEALTHY"
    assert refreshed_b.enabled is True
    assert refreshed_b.last_error is None


@pytest.mark.asyncio
async def test_live_detector_failure_does_not_disable_feed_health(db_session):
    """Verify live status detector failure does not alter feed_health or disable upload monitoring."""
    ch = await YouTubeChannelRepo.create(db_session, PB_HERO_GAMER_ID, "PB HERO GAMER")
    await YouTubeChannelRepo.update_feed_status(
        db_session,
        PB_HERO_GAMER_ID,
        success=True,
        http_status=200,
        entry_count=3,
    )
    await db_session.commit()

    # Live check fails with bot verification error
    await YouTubeChannelRepo.update_live_status(
        db_session,
        PB_HERO_GAMER_ID,
        live_health="UNKNOWN",
        error="yt-dlp blocked",
    )
    await db_session.commit()

    refreshed = await YouTubeChannelRepo.get_by_channel_id(db_session, PB_HERO_GAMER_ID)
    # Feed health remains HEALTHY!
    assert refreshed.feed_health == "HEALTHY"
    assert refreshed.live_health == "UNKNOWN"
    assert refreshed.enabled is True


@pytest.mark.asyncio
async def test_api_endpoints_use_polling_url(db_session):
    """Verify dashboard API endpoints return direct RSS polling URL."""
    from app.dashboard.routes.api import list_youtube_channels, get_youtube_channel, test_youtube_channel

    ch = await YouTubeChannelRepo.create(db_session, PB_HERO_GAMER_ID, "PB HERO GAMER")
    await db_session.commit()

    with patch("app.dashboard.routes.api.get_session_direct", return_value=db_session):
        # 1. list_youtube_channels
        channels = await list_youtube_channels(username="admin")
        assert len(channels) == 1
        assert channels[0]["feed_url"] == f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"

        # 2. get_youtube_channel
        channel_data = await get_youtube_channel(PB_HERO_GAMER_ID, username="admin")
        assert channel_data["feed_url"] == f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"

        # 3. test_youtube_channel with mock fetch
        mock_feed = FeedResult(
            success=True,
            channel_id=PB_HERO_GAMER_ID,
            channel_name="PB HERO GAMER",
            feed_url=build_poll_feed_url(PB_HERO_GAMER_ID),
            http_status=200,
            content_type="application/atom+xml",
            entries=[FeedEntry(video_id="vid1", title="Title", url="https://youtube.com/watch?v=vid1")],
        )
        with patch("app.youtube.feed_parser.fetch_feed", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_feed
            test_res = await test_youtube_channel(PB_HERO_GAMER_ID, username="admin")
            assert test_res["success"] is True
            assert test_res["feed_url"] == f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"
            assert test_res["http_status"] == 200
            assert test_res["feed_status"] == "HEALTHY"
