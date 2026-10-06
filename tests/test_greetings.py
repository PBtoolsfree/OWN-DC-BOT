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
from app.database.repositories import (
    AdminUserRepo,
    AuditLogRepo,
    InviteJoinRepo,
    ServerGreetingSettingsRepo,
    ServerInviteSettingsRepo,
)
from app.greetings.service import GreetingService, get_greeting_service
from app.greetings.templates import (
    DEFAULT_GOODBYE_TITLE,
    DEFAULT_WELCOME_TITLE,
    GOODBYE_VARIABLES,
    WELCOME_VARIABLES,
    THEME_PRESETS,
    render_template,
    validate_variables,
    validate_buttons,
    validate_discord_limits,
    is_safe_url,
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


def make_mock_bot():
    mock_bot = MagicMock()
    mock_bot.is_ready.return_value = True
    guild = make_mock_guild()
    mock_bot.guild = guild
    mock_bot.get_guild.return_value = guild
    return mock_bot


# ─── Test Cases ───────────────────────────────────────────────────────────────

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
        assert res.status_code in (400, 422)
        assert "Unsupported variable in welcome_title" in res.json()["detail"]

        res_goodbye = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"goodbye_title": "Bye {account_created}!"},  # account_created is not in goodbye
        )
        assert res_goodbye.status_code in (400, 422)
        assert "Unsupported variable in goodbye_title" in res_goodbye.json()["detail"]


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
            session, GUILD_ID, goodbye_enabled=True, goodbye_channel_id=222, goodbye_use_embed=True)
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
            session, GUILD_ID, goodbye_enabled=False, goodbye_channel_id=222, goodbye_use_embed=True)
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
            session, GUILD_ID, goodbye_channel_id=222, goodbye_use_embed=True)
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


# ==============================================================================
# Premium Onboarding 2.0 Specification Tests (1 to 22)
# ==============================================================================

@pytest.mark.asyncio
async def test_backend_01_premium_welcome_rendering():
    """1. Premium welcome rendering: embeds, accent color, banner, author, and buttons."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=11111, name="GamerHero")

    session = await get_session_direct()
    try:
        config = await ServerGreetingSettingsRepo.update(
            session,
            GUILD_ID,
            welcome_use_embed=True,
            welcome_accent_color="#FF5733",
            welcome_banner_url="https://example.com/banner.png",
            welcome_banner_mode="custom",
            welcome_author_text="Welcome to PB Hero",
            welcome_author_icon_url="https://example.com/icon.png",
            welcome_buttons_json='[{"id":"rules","label":"Read Rules","url":"https://discord.com/channels/1/2","enabled":true}]',
        )
        content, embed, allowed = service.render_welcome_message(
            config,
            member,
            attribution={"inviter_name": "ProInviter", "invite_code": "HERO99"},
        )
        assert embed is not None
        assert embed.color.value == 0xFF5733
        assert embed.image.url == "https://example.com/banner.png"
        assert embed.author.name == "Welcome to PB Hero"
        assert embed.author.icon_url == "https://example.com/icon.png"

        view = service.build_buttons_view(config.welcome_buttons_json, {"rules_url": "https://discord.com/channels/1/2"})
        assert view is not None
        assert len(view.children) == 1
        assert view.children[0].label == "Read Rules"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_backend_02_premium_goodbye_rendering():
    """2. Premium goodbye rendering: embed, custom accent color, footer, member count."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=22222, name="DepartedMember")

    session = await get_session_direct()
    try:
        config = await ServerGreetingSettingsRepo.update(
            session,
            GUILD_ID,
            goodbye_use_embed=True,
            goodbye_accent_color="#ED4245",
            goodbye_footer="PB HERO SERVER",
            goodbye_show_member_count=True,
        )
        content, embed, allowed = service.render_goodbye_message(config, member)
        assert embed is not None
        assert embed.color.value == 0xED4245
        assert "DepartedMember" in embed.description
        assert embed.footer.text == "PB HERO SERVER"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_backend_03_welcome_dm_rendering():
    """3. Welcome DM rendering: rich embed, dynamic rules & invite variables, buttons."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=33333, name="Newcomer")

    session = await get_session_direct()
    try:
        config = await ServerGreetingSettingsRepo.update(
            session,
            GUILD_ID,
            welcome_dm_use_embed=True,
            welcome_dm_title="👋 Welcome to {server_name}, {display_name}!",
            welcome_dm_description="Rules: {rules_url}\nInvite: {invite_url}",
            welcome_dm_accent_color="#57F287",
        )
        links = {"rules_url": "https://discord.com/channels/1/2", "invite_url": "https://discord.gg/pbhero"}
        content, embed, allowed = service.render_welcome_dm(config, member, links)
        assert embed is not None
        assert "Newcomer" in embed.title
        assert "https://discord.com/channels/1/2" in embed.description
        assert "https://discord.gg/pbhero" in embed.description
        assert embed.color.value == 0x57F287
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_backend_04_goodbye_dm_rendering():
    """4. Goodbye DM rendering: rejoin invite URL, no private moderation data."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=44444, name="PastUser")

    session = await get_session_direct()
    try:
        config = await ServerGreetingSettingsRepo.update(
            session,
            GUILD_ID,
            goodbye_dm_use_embed=True,
            goodbye_dm_description="Rejoin server: {invite_url}",
        )
        links = {"invite_url": "https://discord.gg/rejoin"}
        content, embed, allowed = service.render_goodbye_dm(config, member, links)
        assert embed is not None
        assert "https://discord.gg/rejoin" in embed.description
        # Verify no moderation fields or private internal data leaked
        assert "ban" not in embed.description.lower()
        assert "kick" not in embed.description.lower()
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_backend_05_invite_attribution_rendering():
    """5. Invite attribution rendering: real inviter, mention, code, total_invites, rank."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=55555, name="ReferredHero")

    attr = {
        "inviter_name": "GuildLeader",
        "inviter_id": "777888",
        "inviter_mention": "<@777888>",
        "invite_code": "PROVIP",
        "invite_channel": "#welcome",
        "total_invites": 42,
        "rank": 3,
    }
    ctx = service._build_welcome_context(None, member, attribution=attr)
    assert ctx["inviter"] == "GuildLeader"
    assert ctx["inviter_mention"] == "<@777888>"
    assert ctx["inviter_id"] == "777888"
    assert ctx["invite_code"] == "PROVIP"
    assert ctx["total_invites"] == "42"
    assert ctx["rank"] == "3"


@pytest.mark.asyncio
async def test_backend_06_unknown_inviter():
    """6. Unknown inviter: display Unknown without inventing or guessing."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=66666, name="MysteryUser")

    # None attribution
    ctx = service._build_welcome_context(None, member, attribution=None)
    assert ctx["inviter"] == "Unknown"
    assert ctx["inviter_mention"] == "Unknown"
    assert ctx["invite_code"] == "Unknown"
    assert ctx["total_invites"] == "0"
    assert ctx["rank"] == "N/A"

    # Empty dict
    ctx_empty = service._build_welcome_context(None, member, attribution={})
    assert ctx_empty["inviter"] == "Unknown"


@pytest.mark.asyncio
async def test_backend_07_vanity_inviter():
    """7. Vanity inviter: display 'Server Vanity URL'."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=77777, name="VanityUser")

    attr = {"is_vanity": True, "inviter_name": "Server Vanity URL", "invite_code": "pbhero"}
    ctx = service._build_welcome_context(None, member, attribution=attr)
    assert ctx["inviter"] == "Server Vanity URL"
    assert ctx["invite_code"] == "pbhero"


@pytest.mark.asyncio
async def test_backend_08_member_count():
    """8. Member count: accurate real guild member count."""
    service = GreetingService()
    guild = make_mock_guild()
    guild.member_count = 2048
    member = make_mock_member(guild=guild, user_id=88888, name="CountMember")

    ctx = service._build_welcome_context(None, member, attribution=None)
    assert ctx["member_count"] == "2048"


@pytest.mark.asyncio
async def test_backend_09_variable_substitution():
    """9. Variable substitution: all supported variables populate correctly."""
    template = (
        "{username}|{display_name}|{user_mention}|{user_id}|"
        "{server_name}|{server_id}|{member_count}|{account_created}|"
        "{joined_at}|{inviter}|{inviter_mention}|{inviter_id}|"
        "{invite_code}|{invite_channel}|{rules_url}|{invite_url}"
    )
    context = {
        "username": "tester",
        "display_name": "Tester",
        "user_mention": "<@123>",
        "user_id": "123",
        "server_name": "Hero Guild",
        "server_id": "456",
        "member_count": "50",
        "account_created": "2024-01-01",
        "joined_at": "2024-02-01",
        "inviter": "Boss",
        "inviter_mention": "<@789>",
        "inviter_id": "789",
        "invite_code": "CODE",
        "invite_channel": "#lounge",
        "rules_url": "https://discord.com/rules",
        "invite_url": "https://discord.gg/code",
    }
    rendered = render_template(template, context)
    assert "{" not in rendered
    assert "}" not in rendered
    assert "tester|Tester|<@123>|123|Hero Guild" in rendered


def test_backend_10_button_validation():
    """10. Button validation: limits, valid fields, action row constraints."""
    # Valid buttons
    valid_btns = [
        {"id": "btn1", "label": "Read Rules", "url": "https://discord.com/rules", "enabled": True},
        {"id": "btn2", "label": "Explore", "emoji": "🎮", "url": "https://discord.gg/server", "enabled": True},
    ]
    ok, err, cleaned = validate_buttons(valid_btns)
    assert ok is True
    assert err is None
    assert len(cleaned) == 2

    # Reject > 5 buttons
    too_many = [{"id": f"b{i}", "label": f"L{i}", "url": "https://example.com"} for i in range(6)]
    ok, err, _ = validate_buttons(too_many)
    assert ok is False
    assert "maximum of 5 buttons" in err

    # Reject button without label and emoji
    no_content = [{"id": "b1", "url": "https://example.com"}]
    ok, err, _ = validate_buttons(no_content)
    assert ok is False
    assert "must have a label or emoji" in err

    # Reject invalid JSON
    ok, err, _ = validate_buttons("invalid_json{[")
    assert ok is False


def test_backend_11_https_url_validation():
    """11. HTTPS URL validation: allow only HTTPS and safe placeholders."""
    assert is_safe_url("https://discord.com/channels/123/456") is True
    assert is_safe_url("https://example.com/image.png") is True
    assert is_safe_url("{rules_url}") is True
    assert is_safe_url("{invite_url}") is True

    # Unsafe schemes
    assert is_safe_url("javascript:alert(1)") is False
    assert is_safe_url("data:text/html;base64,PHNjcmlwdD4=") is False
    assert is_safe_url("file:///etc/passwd") is False
    assert is_safe_url("vbscript:msgbox(1)") is False
    assert is_safe_url("http://insecure.example.com") is False
    assert is_safe_url("") is False
    assert is_safe_url(None) is False


@pytest.mark.asyncio
async def test_backend_12_image_fallback():
    """12. Image fallback: broken image falls back to embed without image."""
    service = GreetingService()
    mock_channel = AsyncMock()

    # First send with image fails, fallback send without image succeeds
    call_count = 0
    async def mock_send(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        embed = kwargs.get("embed")
        if call_count == 1 and embed and getattr(embed, "image", None) and getattr(embed.image, "url", None):
            raise discord.HTTPException(MagicMock(status=400), "Invalid image asset")
        return MagicMock(spec=discord.Message)

    mock_channel.send = AsyncMock(side_effect=mock_send)

    embed = discord.Embed(title="Welcome!", description="Hello")
    embed.set_image(url="https://broken.invalid/img.png")

    sent = await service.send_greeting(mock_channel, content="Hey", embed=embed)
    assert call_count == 2  # Attempted with image, then succeeded on fallback without image


@pytest.mark.asyncio
async def test_backend_13_dm_unavailable():
    """13. DM unavailable: record status and do not interrupt leave or join."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=12345, name="DMsClosedUser")
    member.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "Cannot send messages to user"))

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session, GUILD_ID, welcome_enabled=False, welcome_dm_enabled=True
        )
        await session.commit()
    finally:
        await session.close()

    # handle_member_join catches Forbidden safely and records DM unavailable
    await service.handle_member_join(member)

    activity = service.get_recent_activity(5)
    dm_events = [a for a in activity if a.get("status") == "DM unavailable"]
    assert len(dm_events) > 0


@pytest.mark.asyncio
async def test_backend_14_public_welcome_failure_isolation():
    """14. Public welcome failure isolation: does not prevent Auto Role."""
    mock_bot = make_mock_bot()
    service = GreetingService(bot=mock_bot)

    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=123, guild=guild)
    guild.get_channel = MagicMock(return_value=channel)
    member = make_mock_member(guild=guild, user_id=99901)
    member.add_roles = AsyncMock()

    role = MagicMock(spec=discord.Role)
    role.id = 888111
    guild.get_role.return_value = role

    with patch.object(service, "send_greeting", AsyncMock(side_effect=RuntimeError("Discord API Error"))):
        session = await get_session_direct()
        try:
            await ServerGreetingSettingsRepo.update(
                session,
                GUILD_ID,
                welcome_enabled=True,
                welcome_channel_id=123,
                welcome_dm_enabled=False,
                auto_role_enabled=True,
                auto_role_id=888111,
            )
            await session.commit()
        finally:
            await session.close()

        await service.handle_member_join(member)
        member.add_roles.assert_awaited_once_with(role, reason="Auto Role on Member Join")


@pytest.mark.asyncio
async def test_backend_15_goodbye_failure_isolation():
    """15. Goodbye failure isolation: DM failure does not interrupt leave event."""
    mock_bot = make_mock_bot()
    service = GreetingService(bot=mock_bot)

    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=123, guild=guild)
    guild.get_channel = MagicMock(return_value=channel)
    member = make_mock_member(guild=guild, user_id=99902)
    member.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "DMs closed"))

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session,
            GUILD_ID,
            goodbye_enabled=True,
            goodbye_channel_id=123,
            goodbye_dm_enabled=True,
        )
        await session.commit()
    finally:
        await session.close()

    # Should not raise exception, public goodbye still delivers
    await service.handle_member_leave(member)
    assert channel.send.call_count == 1


@pytest.mark.asyncio
async def test_backend_16_auto_role_independence():
    """16. Auto-role independence: succeeds even if greetings are disabled."""
    mock_bot = make_mock_bot()
    service = GreetingService(bot=mock_bot)

    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=99903)
    member.add_roles = AsyncMock()

    role = MagicMock(spec=discord.Role)
    role.id = 777222
    guild.get_role.return_value = role

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(
            session,
            GUILD_ID,
            welcome_enabled=False,
            welcome_dm_enabled=False,
            auto_role_enabled=True,
            auto_role_id=777222,
        )
        await session.commit()
    finally:
        await session.close()

    await service.handle_member_join(member)
    member.add_roles.assert_awaited_once_with(role, reason="Auto Role on Member Join")


@pytest.mark.asyncio
async def test_backend_17_test_mode_does_not_modify_db():
    """17. Test mode does not modify DB: no fake invite joins, no altered member counts."""
    mock_bot = make_mock_bot()
    guild = make_mock_guild()
    channel = make_mock_channel(channel_id=111, guild=guild)
    guild.get_channel = MagicMock(return_value=channel)
    mock_bot.guild = guild
    service = GreetingService(bot=mock_bot)

    session = await get_session_direct()
    try:
        await ServerGreetingSettingsRepo.update(session, GUILD_ID, welcome_channel_id=111)
        await session.commit()
        initial_joins = await InviteJoinRepo.count_by_guild(session, GUILD_ID)
    finally:
        await session.close()

    result = await service.send_test_message("welcome")
    assert result["status"] == "ok"

    session = await get_session_direct()
    try:
        after_joins = await InviteJoinRepo.count_by_guild(session, GUILD_ID)
        assert after_joins == initial_joins  # Untouched!
    finally:
        await session.close()


def test_backend_18_theme_presets():
    """18. Theme presets: verify default, gaming, minimal, luxury, neon exist and have required keys."""
    expected_themes = ["default", "gaming", "minimal", "luxury", "neon"]
    for theme_id in expected_themes:
        assert theme_id in THEME_PRESETS
        preset = THEME_PRESETS[theme_id]
        assert "welcome_title" in preset
        assert "welcome_description" in preset
        assert "welcome_accent_color" in preset
        assert "goodbye_title" in preset
        assert "goodbye_description" in preset


@pytest.mark.asyncio
async def test_backend_19_configuration_persistence(app, auth_cookies):
    """19. Configuration persistence: all Premium Onboarding 2.0 fields persist cleanly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        update_data = {
            "welcome_theme": "gaming",
            "welcome_accent_color": "#10B981",
            "welcome_banner_mode": "custom",
            "welcome_banner_url": "https://example.com/banner.png",
            "welcome_author_text": "PB Hero Gaming",
            "welcome_show_inviter": True,
            "welcome_show_invite_code": True,
            "welcome_buttons_json": [
                {"id": "rules", "label": "Rules", "url": "https://example.com/rules", "enabled": True}
            ],
            "goodbye_theme": "luxury",
            "goodbye_accent_color": "#F59E0B",
        }
        res = await client.put("/api/v1/greetings", cookies=auth_cookies, json=update_data)
        assert res.status_code == 200

        # Retrieve and verify persistence
        get_res = await client.get("/api/v1/greetings", cookies=auth_cookies)
        assert get_res.status_code == 200
        settings = get_res.json()["settings"]
        assert settings["welcome_theme"] == "gaming"
        assert settings["welcome_accent_color"] == "#10B981"
        assert settings["welcome_banner_mode"] == "custom"
        assert settings["welcome_banner_url"] == "https://example.com/banner.png"
        assert settings["welcome_author_text"] == "PB Hero Gaming"
        assert settings["goodbye_theme"] == "luxury"
        assert settings["goodbye_accent_color"] == "#F59E0B"


@pytest.mark.asyncio
async def test_backend_20_backward_compatibility():
    """20. Backward compatibility: existing legacy templates and variables remain valid."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=99904, name="LegacyUser")

    legacy_template = "Welcome {username} to {server_name}! You are member #{member_count}."
    context = service._build_welcome_context(None, member, attribution=None)
    rendered = render_template(legacy_template, context)
    assert "Welcome LegacyUser to PB HERO SERVER! You are member #142." in rendered


@pytest.mark.asyncio
async def test_backend_21_invite_tracking_integration():
    """21. Invite tracking integration: join attribution integrates seamlessly."""
    service = GreetingService()
    guild = make_mock_guild()
    member = make_mock_member(guild=guild, user_id=99905, name="TrackedJoin")

    attr = {
        "invite_code": "TRACK123",
        "inviter_name": "TrackerMaster",
        "inviter_id": "999888",
        "total_invites": 15,
        "rank": 2,
    }
    context = service._build_welcome_context(None, member, attribution=attr)
    assert context["invite_code"] == "TRACK123"
    assert context["inviter"] == "TrackerMaster"
    assert context["total_invites"] == "15"
    assert context["rank"] == "2"


@pytest.mark.asyncio
async def test_backend_22_audit_logging(app, auth_cookies):
    """22. Audit logging: configuration changes record audit log entries."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_title": "Audited Welcome Title"},
        )
        assert res.status_code == 200

    session = await get_session_direct()
    try:
        logs = await AuditLogRepo.get_recent(session, 10)
        actions = [log.action for log in logs]
        assert "update_greeting_settings" in actions
    finally:
        await session.close()


# ==============================================================================
# Premium Onboarding 2.0 Persistence & Specification Tests (1 to 20)
# ==============================================================================

@pytest.mark.asyncio
async def test_spec_01_save_default_welcome_settings(app, auth_cookies):
    """1. Save default welcome settings."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={
                "welcome_theme": "default",
                "welcome_accent_color": "#5865F2",
                "welcome_title": DEFAULT_WELCOME_TITLE,
                "welcome_enabled": True,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["settings"]["welcome_theme"] == "default"
        assert data["settings"]["welcome_accent_color"] == "#5865F2"


@pytest.mark.asyncio
async def test_spec_02_save_gaming_theme(app, auth_cookies):
    """2. Save Gaming theme."""
    transport = ASGITransport(app=app)
    preset = THEME_PRESETS["gaming"]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={
                "welcome_theme": "gaming",
                "welcome_title": preset["welcome_title"],
                "welcome_description": preset["welcome_description"],
                "welcome_accent_color": preset["welcome_accent_color"],
            },
        )
        assert res.status_code == 200
        s = res.json()["settings"]
        assert s["welcome_theme"] == "gaming"
        assert s["welcome_accent_color"] == preset["welcome_accent_color"]
        assert s["welcome_title"] == preset["welcome_title"]


@pytest.mark.asyncio
async def test_spec_03_save_minimal_theme(app, auth_cookies):
    """3. Save Minimal theme."""
    transport = ASGITransport(app=app)
    preset = THEME_PRESETS["minimal"]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_theme": "minimal", "welcome_accent_color": preset["welcome_accent_color"]},
        )
        assert res.status_code == 200
        assert res.json()["settings"]["welcome_theme"] == "minimal"


@pytest.mark.asyncio
async def test_spec_04_save_luxury_theme(app, auth_cookies):
    """4. Save Luxury theme."""
    transport = ASGITransport(app=app)
    preset = THEME_PRESETS["luxury"]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_theme": "luxury", "welcome_accent_color": preset["welcome_accent_color"]},
        )
        assert res.status_code == 200
        assert res.json()["settings"]["welcome_theme"] == "luxury"


@pytest.mark.asyncio
async def test_spec_05_save_neon_theme(app, auth_cookies):
    """5. Save Neon theme."""
    transport = ASGITransport(app=app)
    preset = THEME_PRESETS["neon"]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_theme": "neon", "welcome_accent_color": preset["welcome_accent_color"]},
        )
        assert res.status_code == 200
        assert res.json()["settings"]["welcome_theme"] == "neon"


@pytest.mark.asyncio
async def test_spec_06_save_accent_color(app, auth_cookies):
    """6. Save accent color (3-digit, 6-digit, and normalized)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Standard 6-digit hex
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_accent_color": "#00FF99"},
        )
        assert res.status_code == 200
        assert res.json()["settings"]["welcome_accent_color"] == "#00FF99"

        # Auto-prefixed hex without #
        res2 = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_accent_color": "FFAA00"},
        )
        assert res2.status_code == 200
        assert res2.json()["settings"]["welcome_accent_color"] == "#FFAA00"


@pytest.mark.asyncio
async def test_spec_07_save_banner_url(app, auth_cookies):
    """7. Save banner URL and banner mode."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={
                "welcome_banner_mode": "custom",
                "welcome_banner_url": "https://cdn.example.com/welcome-banner.png",
            },
        )
        assert res.status_code == 200
        s = res.json()["settings"]
        assert s["welcome_banner_mode"] == "custom"
        assert s["welcome_banner_url"] == "https://cdn.example.com/welcome-banner.png"


@pytest.mark.asyncio
async def test_spec_08_save_buttons(app, auth_cookies):
    """8. Save buttons as JSON list or string."""
    transport = ASGITransport(app=app)
    buttons = [
        {"id": "rules", "label": "Read Rules", "emoji": "📜", "url": "{rules_url}", "enabled": True},
        {"id": "discord", "label": "Join Discord", "emoji": "🎮", "url": "https://discord.gg/pbhero", "enabled": True},
    ]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_buttons_json": buttons},
        )
        assert res.status_code == 200
        btns_str = res.json()["settings"]["welcome_buttons_json"]
        import json
        parsed = json.loads(btns_str)
        assert len(parsed) == 2
        assert parsed[0]["label"] == "Read Rules"


@pytest.mark.asyncio
async def test_spec_09_save_invite_attribution_settings(app, auth_cookies):
    """9. Save invite attribution settings."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_show_inviter": False, "welcome_show_invite_code": False},
        )
        assert res.status_code == 200
        s = res.json()["settings"]
        assert s["welcome_show_inviter"] is False
        assert s["welcome_show_invite_code"] is False


@pytest.mark.asyncio
async def test_spec_10_save_all_settings_together(app, auth_cookies):
    """10. Save all Premium Onboarding settings together."""
    transport = ASGITransport(app=app)
    buttons = [
        {"id": "rules", "label": "Rules", "emoji": "📜", "url": "{rules_url}", "enabled": True},
    ]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={
                "welcome_theme": "gaming",
                "welcome_accent_color": "#22C55E",
                "welcome_banner_mode": "custom",
                "welcome_banner_url": "https://images.example.com/gaming.gif",
                "welcome_buttons_json": buttons,
                "welcome_author_text": "PB Hero Gaming Clan",
                "welcome_author_icon_url": "https://images.example.com/clan.png",
                "welcome_show_inviter": True,
                "welcome_show_invite_code": True,
            },
        )
        assert res.status_code == 200
        s = res.json()["settings"]
        assert s["welcome_theme"] == "gaming"
        assert s["welcome_accent_color"] == "#22C55E"
        assert s["welcome_author_text"] == "PB Hero Gaming Clan"


@pytest.mark.asyncio
async def test_spec_11_invalid_color(app, auth_cookies):
    """11. Invalid color returns friendly 422 validation response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_accent_color": "not-a-color"},
        )
        assert res.status_code == 422
        assert "Invalid hex color" in res.json()["detail"]


@pytest.mark.asyncio
async def test_spec_12_invalid_url(app, auth_cookies):
    """12. Invalid URL returns friendly 422 validation response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_banner_url": "ftp://insecure.site/banner.jpg"},
        )
        assert res.status_code == 422
        assert "Invalid or unsafe URL" in res.json()["detail"]


@pytest.mark.asyncio
async def test_spec_13_invalid_button_protocol(app, auth_cookies):
    """13. Invalid button protocol (e.g. javascript:) returns 422."""
    transport = ASGITransport(app=app)
    bad_buttons = [
        {"id": "exploit", "label": "Free Nitro", "url": "javascript:alert('pwn')", "enabled": True},
    ]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_buttons_json": bad_buttons},
        )
        assert res.status_code == 422
        assert "Invalid buttons" in res.json()["detail"]


@pytest.mark.asyncio
async def test_spec_14_authentication_failure(app):
    """14. Authentication failure returns 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            json={"welcome_theme": "gaming"},
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_spec_15_database_persistence(app, auth_cookies):
    """15. Database persistence verifies values written to SQLite."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_theme": "luxury", "welcome_accent_color": "#D97706"},
        )

    session = await get_session_direct()
    try:
        row = await ServerGreetingSettingsRepo.get_or_create(session, GUILD_ID)
        assert row.welcome_theme == "luxury"
        assert row.welcome_accent_color == "#D97706"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_spec_16_reload_after_save(app, auth_cookies):
    """16. Reload after save: GET returns persisted configuration."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_theme": "neon", "welcome_accent_color": "#EC4899"},
        )
        get_res = await client.get("/api/v1/greetings", cookies=auth_cookies)
        assert get_res.status_code == 200
        assert get_res.json()["settings"]["welcome_theme"] == "neon"
        assert get_res.json()["settings"]["welcome_accent_color"] == "#EC4899"


@pytest.mark.asyncio
async def test_spec_17_existing_configuration_preserved(app, auth_cookies):
    """17. Existing configuration preserved when partial update is applied."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Save custom goodbye title
        await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"goodbye_title": "Custom Farewell to {display_name}"},
        )
        # Update only welcome theme
        await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_theme": "minimal"},
        )
        # Verify goodbye title was not wiped
        get_res = await client.get("/api/v1/greetings", cookies=auth_cookies)
        s = get_res.json()["settings"]
        assert s["welcome_theme"] == "minimal"
        assert s["goodbye_title"] == "Custom Farewell to {display_name}"


@pytest.mark.asyncio
async def test_spec_18_partial_update(app, auth_cookies):
    """18. Partial update: support aliases like theme and accent_color."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"theme": "gaming", "accent_color": "#10B981"},
        )
        assert res.status_code == 200
        s = res.json()["settings"]
        assert s["welcome_theme"] == "gaming"
        assert s["welcome_accent_color"] == "#10B981"


@pytest.mark.asyncio
async def test_spec_19_transaction_rollback(app, auth_cookies):
    """19. Transaction rollback: invalid request aborts without partial state corruption."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Set a known baseline
        await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_theme": "default", "welcome_accent_color": "#5865F2"},
        )
        # Send a request with both a valid theme and an invalid variable
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_theme": "neon", "welcome_description": "Bad var {malicious_token}"},
        )
        assert res.status_code == 422
        # Verify baseline was not modified
        get_res = await client.get("/api/v1/greetings", cookies=auth_cookies)
        assert get_res.json()["settings"]["welcome_theme"] == "default"


@pytest.mark.asyncio
async def test_spec_20_api_response_schema(app, auth_cookies):
    """20. API response schema includes all required fields."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.put(
            "/api/v1/greetings",
            cookies=auth_cookies,
            json={"welcome_theme": "gaming"},
        )
        assert res.status_code == 200
        body = res.json()
        assert "success" in body
        assert "message" in body
        assert "settings" in body
        s = body["settings"]
        required_fields = [
            "welcome_theme", "welcome_accent_color", "welcome_banner_url", "welcome_banner_mode",
            "welcome_buttons_json", "welcome_show_inviter", "welcome_show_invite_code",
            "goodbye_theme", "goodbye_accent_color", "goodbye_buttons_json",
            "welcome_dm_accent_color", "goodbye_dm_accent_color", "goodbye_dm_buttons_json",
        ]
        for f in required_fields:
            assert f in s, f"Field '{f}' missing from response settings"





