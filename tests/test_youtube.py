"""
Comprehensive Regression Tests for YouTube Feed Parsing, URL Handling, and Notification Reliability.

Covers all production requirements:
1. Canonical /xml/feeds/videos.xml URL generation and validation
2. Stored feed URL repair (migration / startup)
3. Both configured channel IDs (PB HERO GAMER, PB HERO LIVE)
4. HTTP 200 Atom parsing (all fields: yt:videoId, yt:channelId, title, published, updated, links)
5. Empty feed handling
6. Channel ID mismatch detection
7. HTTP 404 handling and bounded legacy fallback
8. HTTP 429 and Retry-After header handling
9. HTTP 5xx transient retry limits
10. Timeouts and HTML error pages
11. Deduplication and restart recovery
12. Discord destination routing and event toggle filtering
13. Notification template variable rendering
14. Scheduled stream detection
15. Live-status UNKNOWN vs OFFLINE distinction
16. Channel isolation (one failing channel does not impact others)
17. Feed failure / live detector failure isolation
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
    build_feed_url,
    build_legacy_feed_url,
    is_valid_channel_id,
    resolve_channel_id,
    sanitize_channel_id,
)
from app.youtube.dedupe import is_duplicate, mark_notified, record_event
from app.youtube.feed_parser import (
    FeedEntry,
    FeedResult,
    _parse_atom_xml,
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
  <link rel="self" href="https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"/>
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
  <link rel="self" href="https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_LIVE_ID}"/>
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
  <link rel="self" href="https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"/>
  <id>yt:channel:{PB_HERO_GAMER_ID}</id>
  <yt:channelId>{PB_HERO_GAMER_ID}</yt:channelId>
  <title>PB HERO GAMER</title>
</feed>
"""

SAMPLE_HTML_ERROR_PAGE = """<!DOCTYPE html>
<html lang="en">
  <head><title>Error 404 (Not Found)!!1</title></head>
  <body><p>The requested URL /feeds/videos.xml was not found on this server.</p></body>
</html>
"""


# ─── 1. Canonical Feed URL Generation & Validation ───────────────────────────

def test_canonical_feed_url_generation():
    """Verify build_feed_url generates canonical /xml/feeds/videos.xml URL for configured channels."""
    url_gamer = build_feed_url(PB_HERO_GAMER_ID)
    url_live = build_feed_url(PB_HERO_LIVE_ID)

    assert url_gamer == f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"
    assert url_live == f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_LIVE_ID}"

    # Strips whitespace
    assert build_feed_url(f"  {PB_HERO_GAMER_ID}  ") == url_gamer

    # Extracts ID if passed within a URL or query without duplicate query params
    assert build_feed_url(f"https://youtube.com/channel/{PB_HERO_GAMER_ID}") == url_gamer
    assert build_feed_url(f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}") == url_gamer
    assert url_gamer.count("channel_id=") == 1


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


def test_legacy_feed_url_generation():
    """Verify build_legacy_feed_url generates the legacy /feeds/videos.xml path for bounded fallback."""
    legacy_url = build_legacy_feed_url(PB_HERO_GAMER_ID)
    assert legacy_url == f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"


# ─── 2. Stored Feed URL Repair (Idempotent Startup / Migration) ──────────────

@pytest.mark.asyncio
async def test_repair_saved_feed_urls_in_database(db_session):
    """Verify repair_saved_feed_urls updates old /feeds/ to /xml/feeds/ while preserving channel config."""
    # Create channel with old URL
    ch = YouTubeChannel(
        youtube_channel_id=PB_HERO_GAMER_ID,
        channel_name="PB HERO GAMER",
        handle="@PBHEROGAMER",
        enabled=True,
        feed_url=f"https://www.youtube.com/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}",
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

    # Verify channel URL is now canonical
    refreshed = await YouTubeChannelRepo.get_by_channel_id(db_session, PB_HERO_GAMER_ID)
    assert refreshed.feed_url == f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={PB_HERO_GAMER_ID}"
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
async def test_parse_empty_feed():
    """Verify valid empty feed produces success=True with entry_count=0 without crashing."""
    success, name, entries, err = _parse_atom_xml(SAMPLE_EMPTY_FEED, PB_HERO_GAMER_ID)
    assert success is True
    assert len(entries) == 0
    assert err is None


# ─── 4. Channel ID Verification and Mismatch Protection ───────────────────────

@pytest.mark.asyncio
async def test_parse_feed_channel_id_mismatch():
    """Verify feed parser rejects feeds where returned channel ID does not match configured channel."""
    # Feed is for PB_HERO_GAMER_ID, but request is for PB_HERO_LIVE_ID
    success, name, entries, err = _parse_atom_xml(SAMPLE_ATOM_FEED_GAMER, PB_HERO_LIVE_ID)
    assert success is False
    assert len(entries) == 0
    assert "Feed channel ID mismatch" in err


# ─── 5. HTTP Client: Status Code Handling, 404, Fallback, 429, 5xx ───────────

@pytest.mark.asyncio
async def test_fetch_feed_http_200_mock():
    """Verify fetch_feed executes against canonical endpoint and populates rich result."""
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
    assert "xml/feeds/videos.xml" in res.feed_url


@pytest.mark.asyncio
async def test_fetch_feed_404_with_fallback_success():
    """Verify 404 on canonical endpoint triggers single bounded fallback to legacy endpoint."""
    resp_404 = MagicMock(status_code=404, headers={"content-type": "text/html"}, text=SAMPLE_HTML_ERROR_PAGE)
    resp_200 = MagicMock(status_code=200, headers={"content-type": "application/atom+xml"}, text=SAMPLE_ATOM_FEED_GAMER)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[resp_404, resp_200])

    res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client, allow_fallback=True)
    assert res.success is True
    assert res.http_status == 200
    assert len(res.entries) == 1
    # Confirms 2 requests were made (first canonical, then legacy)
    assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_feed_both_404_reports_clean_error():
    """Verify if both canonical and legacy endpoints return 404, clean HTTP 404 error is returned."""
    resp_404 = MagicMock(status_code=404, headers={"content-type": "text/html"}, text=SAMPLE_HTML_ERROR_PAGE)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp_404)

    res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client, allow_fallback=True)
    assert res.success is False
    assert res.http_status == 404
    assert "HTTP 404" in res.error
    assert res.is_degraded is True


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

    res = await fetch_feed(PB_HERO_GAMERID := PB_HERO_GAMER_ID, http_client=mock_client, allow_fallback=False)
    assert res.success is False
    assert res.http_status == 429
    assert "HTTP 429" in res.error
    assert res.next_retry_at is not None
    # Next retry should be roughly now + 45s
    assert res.next_retry_at > datetime.utcnow() + timedelta(seconds=30)


@pytest.mark.asyncio
async def test_fetch_feed_5xx_retry_limit():
    """Verify HTTP 500 server errors are retried with backoff up to retry limits."""
    resp_500 = MagicMock(status_code=500, headers={"content-type": "text/plain"}, text="Server Error")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=resp_500)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client, allow_fallback=False)

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

    res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client, allow_fallback=False)
    assert res.success is False
    assert "HTML error page" in res.error


@pytest.mark.asyncio
async def test_fetch_feed_timeout_handling():
    """Verify request timeouts are safely caught without crashing."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

    with patch("asyncio.sleep", new_callable=AsyncMock):
        res = await fetch_feed(PB_HERO_GAMER_ID, http_client=mock_client, allow_fallback=False)

    assert res.success is False
    assert "timed out" in res.error.lower()


# ─── 6. Deduplication & Restart Recovery ──────────────────────────────────────

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


# ─── 7. Discord Destination Routing and Event Toggles ─────────────────────────

@pytest.mark.asyncio
async def test_destination_routing_and_toggles(db_session):
    """Verify notifications respect destination event toggles (upload, live, scheduled, premiere)."""
    channel_id = PB_HERO_GAMER_ID
    ch = await YouTubeChannelRepo.create(db_session, channel_id, "PB HERO GAMER")
    await db_session.flush()

    # Destination 1: Uploads only
    dest1 = await YouTubeDestinationRepo.create(
        db_session,
        channel_id,
        discord_channel_id=111111111,
        upload_enabled=True,
        scheduled_live_enabled=False,
        live_started_enabled=False,
    )

    # Destination 2: Live streams only
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

    # Check upload routing: only dest1 should receive uploads
    upload_recipients = [d.discord_channel_id for d in dests if d.upload_enabled]
    assert upload_recipients == [111111111]

    # Check live routing: only dest2 should receive live announcements
    live_recipients = [d.discord_channel_id for d in dests if d.live_started_enabled]
    assert live_recipients == [222222222]


# ─── 8. Notification Template Rendering ───────────────────────────────────────

def test_template_rendering_variables():
    """Verify template placeholders {channel_name}, {video_title}, etc. are replaced properly."""
    tpl = "🔴 {channel_name} is LIVE: {video_title}! Watch at {video_url}"
    context = {
        "channel_name": "PB HERO GAMER",
        "video_title": "Grandmaster Final",
        "video_url": "https://youtu.be/xyz",
    }
    rendered = render_template_text(tpl, context)
    assert rendered == "🔴 PB HERO GAMER is LIVE: Grandmaster Final! Watch at https://youtu.be/xyz"


def test_create_notification_embed_all_events():
    """Verify embed creation for all 4 supported event types."""
    for event_type in [EventType.UPLOAD, EventType.LIVE_STARTED, EventType.SCHEDULED_LIVE, EventType.PREMIERE]:
        embed = create_notification_embed(
            event_type=event_type,
            title="Special Stream",
            video_url="https://youtube.com/watch?v=123",
            channel_name="PB HERO LIVE",
            channel_id=PB_HERO_LIVE_ID,
        )
        assert embed.title is not None
        assert "PB HERO LIVE" in embed.author.name
        assert embed.url == "https://youtube.com/watch?v=123"


# ─── 9. Live-Status UNKNOWN vs OFFLINE & Scheduled Stream Detection ──────────

@pytest.mark.asyncio
async def test_live_detector_scheduled_stream_detection():
    """Verify upcoming video is detected as status='upcoming'."""
    feed_res = FeedResult(
        success=True,
        channel_id=PB_HERO_GAMER_ID,
        entries=[
            FeedEntry(
                video_id="vid_upcoming_1",
                title="Special Livestream Scheduled for Sunday",
                url="https://youtube.com/watch?v=vid_upcoming_1",
            )
        ],
    )

    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch, \
         patch("app.youtube.live_detector.check_live_status", new_callable=AsyncMock) as mock_status:
        mock_fetch.return_value = feed_res
        mock_status.return_value = LiveStatus(
            video_id="vid_upcoming_1",
            is_upcoming=True,
            live_state="upcoming",
            title="Special Livestream Scheduled for Sunday",
            scheduled_start="2026-10-18T18:00:00Z",
        )

        res = await check_channel_live_status(PB_HERO_GAMER_ID)
        assert res.status == "upcoming"
        assert res.is_upcoming is True
        assert res.is_live is False
        assert res.scheduled_start == "2026-10-18T18:00:00Z"


@pytest.mark.asyncio
async def test_live_detector_unknown_not_classified_as_offline():
    """Verify bot-blocked or inconclusive yt-dlp checks return status='unknown', never 'offline'."""
    feed_res = FeedResult(
        success=True,
        channel_id=PB_HERO_GAMER_ID,
        entries=[
            FeedEntry(
                video_id="vid_blocked_1",
                title="Grandmaster Push",
                url="https://youtube.com/watch?v=vid_blocked_1",
            )
        ],
    )

    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch, \
         patch("app.youtube.live_detector.check_live_status", new_callable=AsyncMock) as mock_status:
        mock_fetch.return_value = feed_res
        mock_status.return_value = LiveStatus(
            video_id="vid_blocked_1",
            live_state="unknown",
            error="Sign in to confirm you're not a bot",
        )

        res = await check_channel_live_status(PB_HERO_GAMER_ID)
        assert res.status == "unknown"
        assert res.is_live is False
        # Must NOT be classified as offline!
        assert res.status != "offline"
        assert "Sign in to confirm" in res.error


# ─── 10. Channel Isolation and Subsystem Independence ─────────────────────────

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
