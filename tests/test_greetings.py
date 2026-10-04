"""
Comprehensive test suite for Server Welcome & Goodbye Automation.

Tests all 22 required backend test specifications:
1. Greeting settings create
2. Greeting settings update
3. Welcome enable/disable
4. Goodbye enable/disable
5. Welcome channel persistence
6. Goodbye channel persistence
7. Welcome template persistence
8. Goodbye template persistence
9. Template variable rendering
10. Invalid variable validation
11. Join event sends exactly one message
12. Leave event sends exactly one message
13. Disabled welcome sends nothing
14. Disabled goodbye sends nothing
15. Missing channel handled safely
16. Permission failure handled safely
17. Discord send failure handled safely
18. Test Welcome endpoint
19. Test Goodbye endpoint
20. Restart does not generate fake events
21. Mention behavior
22. Mass mention disabled by default
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import discord
from app.dashboard.app import create_dashboard_app
from app.dashboard.auth import hash_password
from app.database.engine import get_engine, get_session_direct, init_engine
from app.database.models import Base, ServerGreetingSettings
from app.database.repositories import AdminUserRepo, ServerGreetingSettingsRepo
from app.greetings.service import GreetingService, get_greeting_service
from app.greetings.templates import (
    DEFAULT_GOODBYE_TITLE,
    DEFAULT_WELCOME_TITLE,
    GOODBYE_VARIABLES,
    WELCOME_VARIABLES,
    render_template,
    validate_variables,
)

GUILD_ID = 123456789012345678


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    engine = get_engine()
    if engine is None:
        await init_engine()
        engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session_direct()
    try:
        user = await AdminUserRepo.get_by_username(session, "test_admin")
        if not user:
            await AdminUserRepo.create(session, "test_admin", hash_password("TestSecret123!"))

        await ServerGreetingSettingsRepo.get_or_create(session, GUILD_ID)
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
        res = await client.post(
            "/api/v1/auth/login",
            json={"username": "test_admin", "password": "TestSecret123!"},
        )
        assert res.status_code == 200
        return res.cookies


# ??? Mock Helpers ?????????????????????????????????????????????????????????????

def make_mock_member(guild=None, user_id=987654321, name="CoolMember"):
    mock_guild = guild or make_mock_guild()
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.name = name
    member.display_name = name
    member.mention = f"<@{user_id}>"
    member.guild = mock_guild
    member.bot = False
    member.created_at = datetime(2023, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    member.joined_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    member.display_avatar = MagicMock()
    member.display_avatar.url = "https://cdn.example.com/avatar.png"
    return member


def make_mock_guild(guild_id=GUILD_ID, guild_name="PB HERO SERVER"):
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = guild_name
    guild.member_count = 142
    guild.icon = MagicMock()
    guild.icon.url = "https://cdn.example.com/server_icon.png"
    guild.me = MagicMock()
    guild.channels = []
    guild.categories = []
    return guild


def make_mock_channel(channel_id=1122334455, name="welcome", guild=None, can_send=True, can_view=True, can_embed=True):
    ch = MagicMock(spec=discord.TextChannel)
    ch.id = channel_id
    ch.name = name
    ch.guild = guild or make_mock_guild()
    ch.category = None
    ch.position = 1
    ch.is_news = MagicMock(return_value=False)
    ch.send = AsyncMock()

    perms = MagicMock()
    perms.view_channel = can_view
    perms.send_messages = can_send
    perms.embed_links = can_embed
    ch.permissions_for = MagicMock(return_value=perms)
    return ch


# ??? Test Cases ???????????????????????????????????????????????????????????????

@pytest.mark.asyncio
async def test_1_greeting_settings_create():
    """1. Greeting settings create with safe defaults."""
    session = await get_session_direct()
    try:
        row = await ServerGreetingSettingsRepo.get_or_create(session, 999999999)
        assert row.guild_id == 999999999
        assert row.welcome_enabled is False
        assert row.goodbye_enabled is False
        assert row.welcome_mention_user is True
        assert row.goodbye_mention_user is False
        assert row.allow_mass_mentions is False
        assert "{server_name}" in row.welcome_title
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_2_greeting_settings_update(app, auth_cookies):
    """2. Greeting settings update via API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={
                "welcome_title": "Hello {username}!",
                "goodbye_title": "Bye {username}!",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["settings"]["welcome_title"] == "Hello {username}!"
        assert data["settings"]["goodbye_title"] == "Bye {username}!"


@pytest.mark.asyncio
async def test_3_welcome_enable_disable(app, auth_cookies):
    """3. Welcome enable and disable toggle."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_enabled": True},
        )
        assert res.status_code == 200
        assert res.json()["settings"]["welcome_enabled"] is True

        res2 = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_enabled": False},
        )
        assert res2.status_code == 200
        assert res2.json()["settings"]["welcome_enabled"] is False


@pytest.mark.asyncio
async def test_4_goodbye_enable_disable(app, auth_cookies):
    """4. Goodbye enable and disable toggle."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"goodbye_enabled": True},
        )
        assert res.status_code == 200
        assert res.json()["settings"]["goodbye_enabled"] is True

        res2 = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"goodbye_enabled": False},
        )
        assert res2.status_code == 200
        assert res2.json()["settings"]["goodbye_enabled"] is False


@pytest.mark.asyncio
async def test_5_welcome_channel_persistence(app, auth_cookies):
    """5. Welcome channel persistence."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_channel_id": "111222333444"},
        )
        assert res.status_code == 200
        assert res.json()["settings"]["welcome_channel_id"] == "111222333444"

        get_res = await client.get("/api/v1/greetings", cookies=auth_cookies)
        assert get_res.status_code == 200
        assert get_res.json()["settings"]["welcome_channel_id"] == "111222333444"


@pytest.mark.asyncio
async def test_6_goodbye_channel_persistence(app, auth_cookies):
    """6. Goodbye channel persistence."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"goodbye_channel_id": "555666777888"},
        )
        assert res.status_code == 200
        assert res.json()["settings"]["goodbye_channel_id"] == "555666777888"

        get_res = await client.get("/api/v1/greetings", cookies=auth_cookies)
        assert get_res.status_code == 200
        assert get_res.json()["settings"]["goodbye_channel_id"] == "555666777888"


@pytest.mark.asyncio
async def test_7_welcome_template_persistence(app, auth_cookies):
    """7. Welcome template persistence (title, description, footer)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "welcome_title": "Welcome {username} to {server_name}!",
            "welcome_description": "We are glad you are member #{member_count}!",
            "welcome_footer": "Stay awesome!",
        }
        res = await client.put("/api/v1/greetings", cookies=auth_cookies, json=payload)
        assert res.status_code == 200
        s = res.json()["settings"]
        assert s["welcome_title"] == payload["welcome_title"]
        assert s["welcome_description"] == payload["welcome_description"]
        assert s["welcome_footer"] == payload["welcome_footer"]


@pytest.mark.asyncio
async def test_8_goodbye_template_persistence(app, auth_cookies):
    """8. Goodbye template persistence (title, description, footer)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "goodbye_title": "Farewell {display_name}",
            "goodbye_description": "{username} departed from {server_name}.",
            "goodbye_footer": "Goodbye from {server_name}",
        }
        res = await client.put("/api/v1/greetings", cookies=auth_cookies, json=payload)
        assert res.status_code == 200
        s = res.json()["settings"]
        assert s["goodbye_title"] == payload["goodbye_title"]
        assert s["goodbye_description"] == payload["goodbye_description"]
        assert s["goodbye_footer"] == payload["goodbye_footer"]


def test_9_template_variable_rendering():
    """9. Template variable rendering replaces context without crashing."""
    context = {
        "username": "HeroPlayer",
        "display_name": "Hero Player",
        "user_mention": "<@123>",
        "server_name": "PB HERO SERVER",
        "member_count": "150",
    }
    rendered = render_template(
        "Welcome {user_mention} ({username}) to {server_name}! Member #{member_count}.",
        context,
    )
    assert rendered == "Welcome <@123> (HeroPlayer) to PB HERO SERVER! Member #150."

    # Unknown variable remains intact
    rendered_unknown = render_template("Hello {unknown_variable}!", context)
    assert rendered_unknown == "Hello {unknown_variable}!"


@pytest.mark.asyncio
async def test_10_invalid_variable_validation(app, auth_cookies):
    """10. Invalid variable rejection on save."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_title": "Welcome {bogus_var}!"},
        )
        assert res.status_code == 400
        assert "Unsupported Welcome variable" in res.json()["detail"]

        res_goodbye = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"goodbye_title": "Bye {account_created}!"},  # account_created is not in goodbye
        )
        assert res_goodbye.status_code == 400
        assert "Unsupported Goodbye variable" in res_goodbye.json()["detail"]


@pytest.mark.asyncio
async def test_11_join_event_sends_exactly_one_message():
    """11. Join event sends exactly one message and deduplicates."""
    service = GreetingService()
    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=111, guild=guild)
    guild.get_channel = MagicMock(return_value=channel)

    member = make_mock_member(guild=guild, user_id=112233)

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, welcome_enabled=True, welcome_channel_id=111
        )
        await session.commit()
    finally:
        await session.close()

    # First join
    await service.handle_member_join(member)
    assert channel.send.call_count == 1

    # Immediate duplicate join (within deduplication window)
    await service.handle_member_join(member)
    assert channel.send.call_count == 1  # Still 1!


@pytest.mark.asyncio
async def test_12_leave_event_sends_exactly_one_message():
    """12. Leave event sends exactly one message and deduplicates."""
    service = GreetingService()
    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=222, guild=guild)
    guild.get_channel = MagicMock(return_value=channel)

    member = make_mock_member(guild=guild, user_id=445566)

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, goodbye_enabled=True, goodbye_channel_id=222
        )
        await session.commit()
    finally:
        await session.close()

    # First leave
    await service.handle_member_leave(member)
    assert channel.send.call_count == 1

    # Immediate duplicate leave
    await service.handle_member_leave(member)
    assert channel.send.call_count == 1


@pytest.mark.asyncio
async def test_13_disabled_welcome_sends_nothing():
    """13. Disabled welcome sends nothing."""
    service = GreetingService()
    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=111, guild=guild)
    guild.get_channel = MagicMock(return_value=channel)
    member = make_mock_member(guild=guild, user_id=778899)

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, welcome_enabled=False, welcome_channel_id=111
        )
        await session.commit()
    finally:
        await session.close()

    await service.handle_member_join(member)
    assert channel.send.call_count == 0


@pytest.mark.asyncio
async def test_14_disabled_goodbye_sends_nothing():
    """14. Disabled goodbye sends nothing."""
    service = GreetingService()
    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=222, guild=guild)
    guild.get_channel = MagicMock(return_value=channel)
    member = make_mock_member(guild=guild, user_id=889900)

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, goodbye_enabled=False, goodbye_channel_id=222
        )
        await session.commit()
    finally:
        await session.close()

    await service.handle_member_leave(member)
    assert channel.send.call_count == 0


@pytest.mark.asyncio
async def test_15_missing_channel_handled_safely():
    """15. Missing channel handled safely without crash."""
    service = GreetingService()
    guild = make_mock_guild()
    guild.get_channel = MagicMock(return_value=None)  # Channel deleted
    member = make_mock_member(guild=guild, user_id=10101)

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, welcome_enabled=True, welcome_channel_id=999
        )
        await session.commit()
    finally:
        await session.close()

    # Must not raise exception
    await service.handle_member_join(member)
    acts = service.get_recent_activity()
    assert len(acts) > 0
    assert acts[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_16_permission_failure_handled_safely():
    """16. Permission failure handled safely."""
    service = GreetingService()
    guild = make_mock_guild()
    # Missing send permission
    channel = make_mock_channel(channel_id=111, guild=guild, can_send=False)
    guild.get_channel = MagicMock(return_value=channel)
    member = make_mock_member(guild=guild, user_id=20202)

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, welcome_enabled=True, welcome_channel_id=111
        )
        await session.commit()
    finally:
        await session.close()

    await service.handle_member_join(member)
    assert channel.send.call_count == 0
    acts = service.get_recent_activity()
    assert acts[0]["status"] == "failed"
    assert "Send Messages" in acts[0]["error_message"]


@pytest.mark.asyncio
async def test_17_discord_send_failure_handled_safely():
    """17. Discord API send failure does not crash service."""
    service = GreetingService()
    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=111, guild=guild)
    channel.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=500), "Discord 500 error"))
    guild.get_channel = MagicMock(return_value=channel)
    member = make_mock_member(guild=guild, user_id=30303)

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, welcome_enabled=True, welcome_channel_id=111
        )
        await session.commit()
    finally:
        await session.close()

    await service.handle_member_join(member)
    acts = service.get_recent_activity()
    assert acts[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_18_test_welcome_endpoint(app, auth_cookies):
    """18. Test Welcome endpoint dispatches test message."""
    mock_bot = MagicMock()
    mock_bot.is_ready.return_value = True
    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=111, name="welcome", guild=guild)
    guild.get_channel = MagicMock(return_value=channel)
    mock_bot.guild = guild

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, welcome_channel_id=111
        )
        await session.commit()
    finally:
        await session.close()

    with patch("app.runtime_state.get_bot_instance", return_value=mock_bot):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.post("/api/v1/greetings/test/welcome", cookies=auth_cookies)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"
            assert "TEST WELCOME" in channel.send.call_args.kwargs["embed"].title


@pytest.mark.asyncio
async def test_19_test_goodbye_endpoint(app, auth_cookies):
    """19. Test Goodbye endpoint dispatches test message."""
    mock_bot = MagicMock()
    mock_bot.is_ready.return_value = True
    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=222, name="goodbye", guild=guild)
    guild.get_channel = MagicMock(return_value=channel)
    mock_bot.guild = guild

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, goodbye_channel_id=222
        )
        await session.commit()
    finally:
        await session.close()

    with patch("app.runtime_state.get_bot_instance", return_value=mock_bot):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.post("/api/v1/greetings/test/goodbye", cookies=auth_cookies)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"
            assert "TEST GOODBYE" in channel.send.call_args.kwargs["embed"].title


def test_20_restart_does_not_generate_fake_events():
    """20. Restart / re-initialization does not trigger events for old members."""
    service = GreetingService()
    # Starting fresh has empty activity and no pending triggers
    assert len(service.get_recent_activity()) == 0
    assert service.get_stats()["welcome_sent_today"] == 0
    assert service.get_stats()["goodbye_sent_today"] == 0


@pytest.mark.asyncio
async def test_21_mention_behavior():
    """21. Mention behavior: respect welcome_mention_user setting."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=50505)

    session = await get_session_direct()
    try:
        config_with_mention = await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, welcome_mention_user=True, welcome_use_embed=True
        )
        content, embed, allowed = service.render_welcome_message(config_with_mention, member)
        assert content == member.mention
        assert allowed.users is True

        config_without_mention = await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, welcome_mention_user=False, welcome_use_embed=True
        )
        content2, embed2, allowed2 = service.render_welcome_message(config_without_mention, member)
        assert content2 is None
        assert allowed2.users is False
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_22_mass_mention_disabled_by_default(app, auth_cookies):
    """22. Mass mention protection: rejection during save and sanitization during render."""
    # Rejection during save when allow_mass_mentions is False
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={
                "allow_mass_mentions": False,
                "welcome_description": "Welcome @everyone to the server!",
            },
        )
        assert res.status_code == 400
        assert "Mass mentions" in res.json()["detail"]

    # Sanitization in render_template if bypassed
    sanitized = render_template("Notice @everyone and @here!", {}, allow_mass_mentions=False)
    assert "@everyone" not in sanitized
    assert "@here" not in sanitized
    assert "@\u200beveryone" in sanitized


@pytest.mark.asyncio
async def test_23_reset_systems_individually(app, auth_cookies):
    """23. Reset welcome only or goodbye only."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # First customize both
        await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={
                "welcome_title": "Custom Welcome",
                "goodbye_title": "Custom Goodbye",
            },
        )

        # Reset welcome only
        res = await client.post("/api/v1/greetings/reset/welcome", cookies=auth_cookies)
        assert res.status_code == 200
        s = res.json()["settings"]
        assert s["welcome_title"] == DEFAULT_WELCOME_TITLE
        assert s["goodbye_title"] == "Custom Goodbye"  # Untouched!
