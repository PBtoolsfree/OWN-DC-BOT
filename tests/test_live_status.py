"""
Regression tests for YouTube live status detection:
1. LiveStatus dataclass typed attribute access (does not use .get())
2. Channel ID converted to candidate video IDs
3. Live video returns is_live=True, status="live"
4. Upcoming video returns is_upcoming=True, status="upcoming"
5. Regular video returns offline/regular
6. Feed failure handled safely (feed error, empty feed)
7. yt-dlp failure handled safely (command failure, timeout)
8. /youtube/test-live/{channel_id} returns HTTP 200 for normal detection
9. Endpoint no longer returns HTTP 500 due to dataclass/dict mismatch
"""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.dashboard.app import create_dashboard_app
from app.dashboard.dependencies import require_auth
from app.youtube.feed_parser import FeedEntry, FeedResult
from app.youtube.live_detector import (
    ChannelLiveResult,
    LiveStatus,
    check_channel_live_status,
)


@pytest.fixture
def mock_feed_entry():
    return FeedEntry(
        video_id="vid_test_001",
        title="PB HERO Live Stream Adventure",
        url="https://www.youtube.com/watch?v=vid_test_001",
        channel_id="UC_x5XG1OV2P6uZZ5FSM9Ttw",
        channel_name="PB HERO",
    )


@pytest.fixture
def test_app():
    """Create FastAPI test application with bypassed auth."""
    app = create_dashboard_app()
    app.dependency_overrides[require_auth] = lambda: "test_admin"
    return app


# ─── Test 1: LiveStatus dataclass does not use .get() ────────────────────────

def test_livestatus_dataclass_typed_attributes():
    """Verify LiveStatus dataclass uses typed attributes and does not have/need .get()."""
    status = LiveStatus(
        video_id="dQw4w9WgXcQ",
        is_live=True,
        live_state="live",
        title="Rick Astley Live",
        viewer_count=10000,
    )
    # Dataclass must provide typed attribute access
    assert status.video_id == "dQw4w9WgXcQ"
    assert status.is_live is True
    assert status.live_state == "live"
    assert status.title == "Rick Astley Live"
    assert status.viewer_count == 10000

    # Ensure calling .to_dict() works cleanly
    d = status.to_dict()
    assert isinstance(d, dict)
    assert d["is_live"] is True
    assert d["status"] == "live"


# ─── Test 2: Channel ID converted to candidate video IDs ──────────────────────

@pytest.mark.asyncio
async def test_channel_id_converted_to_candidate_video_ids(mock_feed_entry):
    """Verify check_channel_live_status receives a channel ID and passes video IDs to check_live_status."""
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"

    feed_result = FeedResult(
        success=True,
        channel_id=channel_id,
        entries=[
            mock_feed_entry,
            FeedEntry(
                video_id="vid_test_002",
                title="Secondary Video",
                url="https://www.youtube.com/watch?v=vid_test_002",
            ),
        ],
    )

    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch, \
         patch("app.youtube.live_detector.check_live_status", new_callable=AsyncMock) as mock_check:

        mock_fetch.return_value = feed_result
        mock_check.return_value = LiveStatus(
            video_id="vid_test_001",
            is_live=True,
            live_state="live",
            title="PB HERO Live Stream Adventure",
        )

        result = await check_channel_live_status(channel_id)

        # fetch_feed was called with channel_id
        mock_fetch.assert_awaited_once_with(channel_id, http_client=None)

        # check_live_status was called with candidate video_id, NEVER channel_id
        assert mock_check.call_count == 1
        called_arg = mock_check.call_args[0][0]
        assert called_arg == "vid_test_001"
        assert called_arg != channel_id

        assert result.channel_id == channel_id
        assert result.video_id == "vid_test_001"


# ─── Test 3: Live video returns is_live=true ─────────────────────────────────

@pytest.mark.asyncio
async def test_live_video_returns_is_live_true(mock_feed_entry):
    """Verify live candidate returns is_live=True and status='live'."""
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
    feed_result = FeedResult(
        success=True,
        channel_id=channel_id,
        entries=[mock_feed_entry],
    )

    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch, \
         patch("app.youtube.live_detector.check_live_status", new_callable=AsyncMock) as mock_check:

        mock_fetch.return_value = feed_result
        mock_check.return_value = LiveStatus(
            video_id="vid_test_001",
            is_live=True,
            live_state="live",
            title="PB HERO Live Gaming",
            viewer_count=450,
        )

        res = await check_channel_live_status(channel_id)

        assert isinstance(res, ChannelLiveResult)
        assert res.is_live is True
        assert res.is_upcoming is False
        assert res.status == "live"
        assert res.title == "PB HERO Live Gaming"
        assert res.video_id == "vid_test_001"
        assert res.viewer_count == 450
        assert res.error is None


# ─── Test 4: Upcoming video returns upcoming ──────────────────────────────────

@pytest.mark.asyncio
async def test_upcoming_video_returns_upcoming():
    """Verify upcoming stream candidate returns is_live=False and status='upcoming'."""
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
    feed_result = FeedResult(
        success=True,
        channel_id=channel_id,
        entries=[
            FeedEntry(
                video_id="vid_upcoming_999",
                title="PB HERO Scheduled Grand Stream",
                url="https://youtube.com/watch?v=vid_upcoming_999",
            ),
        ],
    )

    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch, \
         patch("app.youtube.live_detector.check_live_status", new_callable=AsyncMock) as mock_check:

        mock_fetch.return_value = feed_result
        mock_check.return_value = LiveStatus(
            video_id="vid_upcoming_999",
            is_upcoming=True,
            live_state="upcoming",
            title="PB HERO Scheduled Grand Stream",
            scheduled_start="1760000000",
        )

        res = await check_channel_live_status(channel_id)

        assert isinstance(res, ChannelLiveResult)
        assert res.is_live is False
        assert res.is_upcoming is True
        assert res.status == "upcoming"
        assert res.title == "PB HERO Scheduled Grand Stream"
        assert res.video_id == "vid_upcoming_999"
        assert res.scheduled_start == "1760000000"


# ─── Test 5: Regular video returns offline/regular ───────────────────────────

@pytest.mark.asyncio
async def test_regular_video_returns_offline():
    """Verify non-live regular upload returns is_live=False and status='offline'."""
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
    feed_result = FeedResult(
        success=True,
        channel_id=channel_id,
        entries=[
            FeedEntry(
                video_id="vid_regular_111",
                title="PB HERO Discord Bot Setup Guide",
                url="https://youtube.com/watch?v=vid_regular_111",
            ),
        ],
    )

    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch, \
         patch("app.youtube.live_detector.check_live_status", new_callable=AsyncMock) as mock_check:

        mock_fetch.return_value = feed_result
        mock_check.return_value = LiveStatus(
            video_id="vid_regular_111",
            is_live=False,
            live_state="regular_video",
            title="PB HERO Discord Bot Setup Guide",
        )

        res = await check_channel_live_status(channel_id)

        assert isinstance(res, ChannelLiveResult)
        assert res.is_live is False
        assert res.is_upcoming is False
        assert res.status == "offline"
        assert res.title == "PB HERO Discord Bot Setup Guide"
        assert res.video_id == "vid_regular_111"
        assert res.error is None


# ─── Test 6: Feed failure handled safely ──────────────────────────────────────

@pytest.mark.asyncio
async def test_feed_failure_handled_safely():
    """Verify feed fetch failure and empty feed are handled safely without exceptions."""
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"

    # Case A: Network / parse failure
    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = FeedResult(
            success=False,
            channel_id=channel_id,
            error="HTTP 404: Not Found",
        )

        res = await check_channel_live_status(channel_id)
        assert isinstance(res, ChannelLiveResult)
        assert res.is_live is False
        assert res.status == "unknown"
        assert "Feed fetch failed" in res.error

    # Case B: Feed is valid but has 0 entries
    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = FeedResult(
            success=True,
            channel_id=channel_id,
            entries=[],
        )

        res_empty = await check_channel_live_status(channel_id)
        assert isinstance(res_empty, ChannelLiveResult)
        assert res_empty.is_live is False
        assert res_empty.status == "offline"
        assert res_empty.video_id is None
        assert res_empty.error is None


# ─── Test 7: yt-dlp failure handled safely ───────────────────────────────────

@pytest.mark.asyncio
async def test_ytdlp_failure_handled_safely(mock_feed_entry):
    """Verify yt-dlp error returns controlled unknown state without raising exception."""
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"
    feed_result = FeedResult(
        success=True,
        channel_id=channel_id,
        entries=[mock_feed_entry],
    )

    with patch("app.youtube.live_detector.fetch_feed", new_callable=AsyncMock) as mock_fetch, \
         patch("app.youtube.live_detector.check_live_status", new_callable=AsyncMock) as mock_check:

        mock_fetch.return_value = feed_result
        mock_check.return_value = LiveStatus(
            video_id="vid_test_001",
            live_state="unknown",
            error="yt-dlp: error: video unavailable in this region",
        )

        res = await check_channel_live_status(channel_id)

        assert isinstance(res, ChannelLiveResult)
        assert res.is_live is False
        assert res.status == "unknown"
        assert res.error is not None
        assert "Live detection check failed" in res.error


# ─── Test 8: /youtube/test-live/{channel_id} returns HTTP 200 ─────────────────

@pytest.mark.asyncio
async def test_api_endpoint_returns_http_200(test_app):
    """Verify /youtube/test-live/{channel_id} returns HTTP 200 for normal detection."""
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"

    mock_result = ChannelLiveResult(
        channel_id=channel_id,
        is_live=False,
        status="offline",
        title="PB HERO Gamer Video",
        video_id="vid_xyz_123",
        scheduled_start=None,
        error=None,
    )

    with patch("app.youtube.live_detector.check_channel_live_status", new_callable=AsyncMock) as mock_detect:
        mock_detect.return_value = mock_result

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(f"/api/v1/youtube/test-live/{channel_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["is_live"] is False
            assert data["status"] == "offline"
            assert data["title"] == "PB HERO Gamer Video"
            assert data["video_id"] == "vid_xyz_123"
            assert data["channel_id"] == channel_id
            assert data["error"] is None


# ─── Test 9: Endpoint no longer returns HTTP 500 due to dataclass/dict mismatch ─

@pytest.mark.asyncio
async def test_api_endpoint_no_dataclass_mismatch_500(test_app):
    """
    Verify endpoint handles ChannelLiveResult dataclass directly without AttributeError
    from calling .get() on a dataclass.
    """
    channel_id = "UC_x5XG1OV2P6uZZ5FSM9Ttw"

    # Dataclass with Live status
    live_result = ChannelLiveResult(
        channel_id=channel_id,
        is_live=True,
        status="live",
        title="PB HERO Special 24h Live Stream",
        video_id="live_vid_777",
        viewer_count=5000,
    )

    with patch("app.youtube.live_detector.check_channel_live_status", new_callable=AsyncMock) as mock_detect:
        mock_detect.return_value = live_result

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(f"/api/v1/youtube/test-live/{channel_id}")

            # Must NOT return HTTP 500
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["is_live"] is True
            assert data["status"] == "live"
            assert data["title"] == "PB HERO Special 24h Live Stream"
            assert data["video_id"] == "live_vid_777"
            assert data["viewer_count"] == 5000

    # Also test invalid channel ID returns HTTP 400, not 500
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res_bad = await client.post("/api/v1/youtube/test-live/invalid_channel_id")
        assert res_bad.status_code == 400
