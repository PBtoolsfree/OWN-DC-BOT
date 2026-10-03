"""
Tests for YouTube feed parsing, channel resolving, and deduplication.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from app.database.models import EventType
from app.youtube.channel_resolver import resolve_channel_id
from app.youtube.dedupe import is_duplicate, record_event
from app.youtube.feed_parser import FeedResult, fetch_feed


@pytest.mark.asyncio
async def test_channel_resolver_direct_id():
    """Verify channel resolver returns direct channel IDs immediately without network requests."""
    res = await resolve_channel_id("UC_x5XG1OV2P6uZZ5FSM9Ttw")
    assert res is not None
    assert res["channel_id"] == "UC_x5XG1OV2P6uZZ5FSM9Ttw"

    # With channel URL
    res2 = await resolve_channel_id("https://youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw")
    assert res2 is not None
    assert res2["channel_id"] == "UC_x5XG1OV2P6uZZ5FSM9Ttw"


@pytest.mark.asyncio
async def test_deduplication_engine(db_session):
    """Verify database-backed event deduplication logic."""
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
    video_id = "test_vid_123"

    # Initially not duplicate
    dup_before = await is_duplicate(db_session, channel_id, video_id, EventType.UPLOAD)
    assert dup_before is False

    # Record event
    event_id = await record_event(
        db_session,
        channel_id=channel_id,
        video_id=video_id,
        event_type=EventType.UPLOAD,
        title="Test Video Title",
    )
    await db_session.commit()
    assert event_id is not None

    # Now duplicate
    dup_after = await is_duplicate(db_session, channel_id, video_id, EventType.UPLOAD)
    assert dup_after is True


SAMPLE_ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="http://www.youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw"/>
  <id>yt:channel:UC_x5XG1OV2P6uZZ5FSM9Ttw</id>
  <title>Google Developers</title>
  <entry>
    <id>yt:video:dQw4w9WgXcQ</id>
    <yt:videoId>dQw4w9WgXcQ</yt:videoId>
    <yt:channelId>UC_x5XG1OV2P6uZZ5FSM9Ttw</yt:channelId>
    <title>Amazing Announcement</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"/>
    <published>2026-10-01T12:00:00+00:00</published>
    <updated>2026-10-01T12:00:00+00:00</updated>
  </entry>
</feed>
"""


@pytest.mark.asyncio
async def test_fetch_feed_parsing():
    """Verify parsing an Atom XML feed response into structured entries."""
    mock_response = MagicMock()
    mock_response.text = SAMPLE_ATOM_FEED
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    res = await fetch_feed("UC_x5XG1OV2P6uZZ5FSM9Ttw", http_client=mock_client)
    assert res.success is True
    assert res.channel_name == "Google Developers"
    assert len(res.entries) == 1
    assert res.entries[0].video_id == "dQw4w9WgXcQ"
    assert res.entries[0].title == "Amazing Announcement"
