"""
Regression tests for PB HERO Runtime State and Telemetry:
- Shared runtime state between application entrypoint and dashboard
- /health reports discord=true and youtube=true when bot is connected and scheduler is running
- /api/v1/system/status reports bot.connected=true and youtube.running=true
- Safe lifecycle transitions: STARTING, READY, STOPPING, STOPPED, ERROR
- No stale ONLINE state after shutdown
"""

from unittest.mock import MagicMock
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.dashboard.app import create_dashboard_app
from app.dashboard.auth import hash_password
from app.database.engine import get_engine, get_session_direct, init_engine
from app.database.models import Base
from app.database.repositories import AdminUserRepo
from app.runtime_state import (
    BotState,
    clear_bot_instance,
    get_bot_instance,
    get_bot_state,
    is_bot_ready,
    is_youtube_healthy,
    is_youtube_running,
    set_bot_instance,
    set_bot_state,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database_and_cleanup_runtime():
    """Ensure database is initialized and runtime state is clean before/after tests."""
    engine = get_engine()
    if engine is None:
        await init_engine()
        engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    clear_bot_instance()
    yield
    clear_bot_instance()


@pytest.fixture
def mock_bot():
    """Create a mock PBHeroBot instance with active YouTube scheduler."""
    bot = MagicMock()
    bot.is_ready.return_value = True
    bot.is_closed.return_value = False
    bot.latency = 0.042
    bot.uptime = 3600.0

    guild = MagicMock()
    guild.id = 123456789012345678
    guild.name = "PB HERO Official Server"
    guild.member_count = 42
    bot.guild = guild

    scheduler = MagicMock()
    scheduler.is_running = True
    scheduler.is_healthy = True
    bot.youtube_scheduler = scheduler

    return bot


def test_runtime_state_lifecycle_transitions():
    """Verify lifecycle state transitions and safety."""
    assert get_bot_state() == BotState.STOPPED
    assert get_bot_instance() is None
    assert is_bot_ready() is False

    set_bot_state(BotState.STARTING)
    assert get_bot_state() == BotState.STARTING
    assert is_bot_ready() is False

    set_bot_state(BotState.READY)
    assert get_bot_state() == BotState.READY
    # Bot is still None, so is_bot_ready must remain False
    assert is_bot_ready() is False

    set_bot_state(BotState.STOPPING)
    assert get_bot_state() == BotState.STOPPING
    assert is_bot_ready() is False

    set_bot_state(BotState.ERROR)
    assert get_bot_state() == BotState.ERROR
    assert is_bot_ready() is False

    clear_bot_instance()
    assert get_bot_state() == BotState.STOPPED


def test_runtime_state_registration(mock_bot):
    """Verify registering the bot updates ready checks and scheduler telemetry."""
    set_bot_instance(mock_bot)
    set_bot_state(BotState.READY)

    assert get_bot_instance() is mock_bot
    assert is_bot_ready() is True
    assert is_youtube_healthy() is True
    assert is_youtube_running() is True


@pytest.mark.asyncio
async def test_health_telemetry_online(mock_bot):
    """Verify /health reports discord=true and youtube=true when bot is ready."""
    set_bot_instance(mock_bot)
    set_bot_state(BotState.READY)

    app = create_dashboard_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ok"
        assert data["discord"] is True
        assert data["database"] is True
        assert data["youtube"] is True


@pytest.mark.asyncio
async def test_system_status_telemetry_online(mock_bot):
    """Verify /api/v1/system/status reports bot.connected=true and youtube.running=true."""
    set_bot_instance(mock_bot)
    set_bot_state(BotState.READY)

    # Ensure admin user exists for auth
    session = await get_session_direct()
    try:
        user = await AdminUserRepo.get_by_username(session, "telemetry_admin")
        if not user:
            await AdminUserRepo.create(session, "telemetry_admin", hash_password("Telemetry123!"))
            await session.commit()
    finally:
        await session.close()

    app = create_dashboard_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login_res = await client.post("/api/v1/auth/login", json={
            "username": "telemetry_admin",
            "password": "Telemetry123!",
        })
        assert login_res.status_code == 200

        status_res = await client.get("/api/v1/system/status", cookies=login_res.cookies)
        assert status_res.status_code == 200
        data = status_res.json()

        assert data["status"] == "ok"
        assert data["bot"]["connected"] is True
        assert data["bot"]["guild_name"] == "PB HERO Official Server"
        assert data["bot"]["guild_members"] == 42
        assert data["youtube"]["running"] is True
        assert data["youtube"]["healthy"] is True


@pytest.mark.asyncio
async def test_shutdown_cleans_up_telemetry(mock_bot):
    """Verify that shutting down immediately revokes online telemetry without stale states."""
    set_bot_instance(mock_bot)
    set_bot_state(BotState.READY)
    assert is_bot_ready() is True

    # Transition to STOPPING then clear
    set_bot_state(BotState.STOPPING)
    assert is_bot_ready() is False

    clear_bot_instance()
    assert is_bot_ready() is False
    assert is_youtube_healthy() is False
    assert get_bot_state() == BotState.STOPPED

    app = create_dashboard_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert data["discord"] is False
        assert data["youtube"] is False
