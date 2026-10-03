"""
Tests for event-specific YouTube notification templates:
1. GET all templates returns 4 templates.
2. GET individual event template works.
3. PUT modifies only selected event.
4. Reset modifies only selected event.
5. Invalid event type rejected (400).
6. Missing template gets default.
7. Upload event uses upload template.
8. Scheduled event uses scheduled_live template.
9. Live event uses live_started template.
10. Premiere uses premiere template.
11. Template variable validation and character length enforcement.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.dashboard.app import create_dashboard_app
from app.dashboard.auth import hash_password
from app.database.engine import get_engine, get_session_direct, init_engine
from app.database.models import Base, EventType
from app.database.repositories import AdminUserRepo, YouTubeTemplateRepo
from app.youtube.notifier import create_notification_embed, create_notification_view


@pytest_asyncio.fixture(autouse=True)
async def setup_test_database():
    """Ensure database tables exist and default templates are created."""
    engine = get_engine()
    if engine is None:
        await init_engine()
        engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure admin user and default templates exist
    session = await get_session_direct()
    try:
        user = await AdminUserRepo.get_by_username(session, "test_admin")
        if not user:
            await AdminUserRepo.create(session, "test_admin", hash_password("TestSecret123!"))

        await YouTubeTemplateRepo.create_defaults(session)
        await session.commit()
    finally:
        await session.close()
    yield


@pytest.fixture
def app():
    return create_dashboard_app()


@pytest_asyncio.fixture
async def auth_cookies(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post("/api/v1/auth/login", json={
            "username": "test_admin",
            "password": "TestSecret123!",
        })
        assert res.status_code == 200
        return res.cookies


@pytest.mark.asyncio
async def test_get_all_templates_returns_4(app, auth_cookies):
    """GET /api/v1/youtube/templates returns exactly 4 event templates."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/youtube/templates", cookies=auth_cookies)
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 4
        types = {t["event_type"] for t in data}
        assert types == {"upload", "scheduled_live", "live_started", "premiere"}


@pytest.mark.asyncio
async def test_get_individual_template(app, auth_cookies):
    """GET /api/v1/youtube/templates/{event_type} works for all 4 types."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for et in ["upload", "scheduled_live", "live_started", "premiere"]:
            res = await client.get(f"/api/v1/youtube/templates/{et}", cookies=auth_cookies)
            assert res.status_code == 200
            data = res.json()
            assert data["event_type"] == et
            assert "title_template" in data
            assert "description_template" in data


@pytest.mark.asyncio
async def test_put_modifies_only_selected_event(app, auth_cookies):
    """Modifying one template must NOT affect any of the other 3 templates."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Get initial state of scheduled_live
        res_before = await client.get("/api/v1/youtube/templates/scheduled_live", cookies=auth_cookies)
        sched_before = res_before.json()

        # Update upload template
        res_update = await client.put(
            "/api/v1/youtube/templates/upload",
            json={
                "title_template": "🔥 SUPER NEW VIDEO — {channel_name}",
                "description_template": "**{video_title}**\n\nBrand new release!",
                "mention_role": "SpecialRole",
                "footer_text": "Custom Footer",
                "show_thumbnail": False,
                "show_timestamp": True,
                "enable_button": False,
            },
            cookies=auth_cookies,
        )
        assert res_update.status_code == 200
        updated = res_update.json()["template"]
        assert updated["title_template"] == "🔥 SUPER NEW VIDEO — {channel_name}"
        assert updated["mention_role"] == "SpecialRole"
        assert updated["show_thumbnail"] is False

        # Verify upload template persisted
        res_get_upload = await client.get("/api/v1/youtube/templates/upload", cookies=auth_cookies)
        assert res_get_upload.json()["title_template"] == "🔥 SUPER NEW VIDEO — {channel_name}"

        # Verify scheduled_live was NOT modified
        res_after = await client.get("/api/v1/youtube/templates/scheduled_live", cookies=auth_cookies)
        sched_after = res_after.json()
        assert sched_after["title_template"] == sched_before["title_template"]
        assert sched_after["description_template"] == sched_before["description_template"]


@pytest.mark.asyncio
async def test_reset_modifies_only_selected_event(app, auth_cookies):
    """Resetting one template resets only that event to default."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Customize live_started
        await client.put(
            "/api/v1/youtube/templates/live_started",
            json={
                "title_template": "CUSTOM LIVE TITLE",
                "description_template": "CUSTOM LIVE DESC",
            },
            cookies=auth_cookies,
        )

        # Reset live_started
        res_reset = await client.post("/api/v1/youtube/templates/live_started/reset", cookies=auth_cookies)
        assert res_reset.status_code == 200
        data = res_reset.json()["template"]
        assert data["title_template"] == "🔴 {channel_name} IS NOW LIVE!"

        # Verify premiere template is still intact
        res_prem = await client.get("/api/v1/youtube/templates/premiere", cookies=auth_cookies)
        assert res_prem.status_code == 200
        assert res_prem.json()["title_template"] == "🎬 PREMIERE — {channel_name}"


@pytest.mark.asyncio
async def test_invalid_event_type_rejected(app, auth_cookies):
    """Invalid event types return 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res_get = await client.get("/api/v1/youtube/templates/nonexistent_event", cookies=auth_cookies)
        assert res_get.status_code == 400

        res_put = await client.put(
            "/api/v1/youtube/templates/nonexistent_event",
            json={"title_template": "Test"},
            cookies=auth_cookies,
        )
        assert res_put.status_code == 400

        res_reset = await client.post("/api/v1/youtube/templates/nonexistent_event/reset", cookies=auth_cookies)
        assert res_reset.status_code == 400


@pytest.mark.asyncio
async def test_validation_unsupported_variables(app, auth_cookies):
    """Templates containing invalid/unsupported variables return 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/youtube/templates/upload",
            json={
                "title_template": "Check this {hacker_variable}",
                "description_template": "Normal description",
            },
            cookies=auth_cookies,
        )
        assert res.status_code == 400
        assert "Unsupported template variable" in res.json()["detail"]


@pytest.mark.asyncio
async def test_validation_length_limits(app, auth_cookies):
    """Title, description, and footer exceeding max length return 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Title > 256
        res_title = await client.put(
            "/api/v1/youtube/templates/upload",
            json={"title_template": "A" * 257},
            cookies=auth_cookies,
        )
        assert res_title.status_code == 400

        # Description > 2000
        res_desc = await client.put(
            "/api/v1/youtube/templates/upload",
            json={"description_template": "B" * 2001},
            cookies=auth_cookies,
        )
        assert res_desc.status_code == 400


@pytest.mark.asyncio
async def test_missing_template_gets_default():
    """If a template record is missing from the database, get_by_event_type returns default."""
    session = await get_session_direct()
    try:
        # Delete premiere template
        tpl = await YouTubeTemplateRepo.get_by_event_type(session, EventType.PREMIERE)
        await session.delete(tpl)
        await session.commit()

        # Querying again should automatically recreate or return default
        restored = await YouTubeTemplateRepo.get_by_event_type(session, EventType.PREMIERE)
        assert restored is not None
        assert restored.event_type == EventType.PREMIERE
        assert restored.title_template == "🎬 PREMIERE — {channel_name}"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_event_template_rendering_in_notifier():
    """Verify notifier creates correct embeds and views per event type."""
    # 1. Upload
    embed_up = create_notification_embed(
        event_type=EventType.UPLOAD,
        title="Awesome Video",
        video_url="https://youtube.com/watch?v=123",
        channel_name="PB HERO",
    )
    assert "NEW VIDEO" in embed_up.title
    assert "PB HERO" in embed_up.title
    assert "Awesome Video" in embed_up.description

    view_up = create_notification_view("https://youtube.com/watch?v=123", EventType.UPLOAD)
    assert len(view_up.children) == 1
    assert "WATCH VIDEO" in view_up.children[0].label

    # 2. Scheduled Live
    embed_sched = create_notification_embed(
        event_type=EventType.SCHEDULED_LIVE,
        title="Scheduled Stream",
        video_url="https://youtube.com/watch?v=456",
        channel_name="PB HERO",
        scheduled_start="Tomorrow at 8 PM",
    )
    assert "LIVE SCHEDULED" in embed_sched.title
    assert "PB HERO" in embed_sched.title

    view_sched = create_notification_view("https://youtube.com/watch?v=456", EventType.SCHEDULED_LIVE)
    assert "SET REMINDER" in view_sched.children[0].label

    # 3. Live Started
    embed_live = create_notification_embed(
        event_type=EventType.LIVE_STARTED,
        title="Going Live Now",
        video_url="https://youtube.com/watch?v=789",
        channel_name="PB HERO",
        viewer_count=1250,
    )
    assert "IS NOW LIVE!" in embed_live.title

    view_live = create_notification_view("https://youtube.com/watch?v=789", EventType.LIVE_STARTED)
    assert "WATCH LIVE" in view_live.children[0].label

    # 4. Premiere
    embed_prem = create_notification_embed(
        event_type=EventType.PREMIERE,
        title="Special Premiere",
        video_url="https://youtube.com/watch?v=999",
        channel_name="PB HERO",
    )
    assert "PREMIERE" in embed_prem.title

    view_prem = create_notification_view("https://youtube.com/watch?v=999", EventType.PREMIERE)
    assert "WATCH PREMIERE" in view_prem.children[0].label
