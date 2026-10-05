"""
Comprehensive test suite for Dedicated Discord Invite Activity Log System.

Covers all 20 required backend test cases:
1. Channel configuration
2. Valid channel
3. Inaccessible channel
4. Permission validation
5. Successful attributed join sends embed
6. Unknown join sends unknown embed
7. Vanity join sends vanity embed
8. No false inviter attribution
9. Total invite counter increments
10. Leaderboard updates
11. Rank calculation
12. Duplicate event prevention
13. Reconnect safety
14. Restart safety
15. Template rendering
16. Test notification does not change counters
17. Discord send failure does not lose attribution
18. Disabled logging
19. Channel switch
20. Historical data preserved
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

import discord
from app.dashboard.app import create_dashboard_app
from app.dashboard.auth import hash_password
from app.database.engine import get_engine, get_session_direct, init_engine
from app.database.models import Base, DiscordInvite, InviteActivitySettings, InviteJoin
from app.database.repositories import (
    AdminUserRepo,
    DiscordInviteRepo,
    InviteActivitySettingsRepo,
    InviteJoinRepo,
    ServerConfigRepo,
    ServerGreetingSettingsRepo,
)
from app.invites.tracker import AttributionResult, CachedInvite, InviteTracker

GUILD_ID = 123456789012345678


# ─── Mock Helpers ─────────────────────────────────────────────────────────────

def make_user(user_id=1001, name="Rex12400"):
    u = MagicMock(spec=discord.User)
    u.id = user_id
    u.name = name
    u.display_name = name
    u.mention = f"<@{user_id}>"
    u.__str__ = MagicMock(return_value=name)
    return u


def make_channel(channel_id=2001, name="invites", view=True, send=True, embed=True):
    c = MagicMock(spec=discord.TextChannel)
    c.id = channel_id
    c.name = name
    c.mention = f"<#{channel_id}>"
    c.category = None
    c.position = 1

    msg = MagicMock()
    msg.id = 999000111
    c.send = AsyncMock(return_value=msg)

    perms = MagicMock()
    perms.view_channel = view
    perms.send_messages = send
    perms.embed_links = embed
    c.permissions_for = MagicMock(return_value=perms)
    return c


def make_member(member_id=2002, name="Rahul"):
    m = MagicMock(spec=discord.Member)
    m.id = member_id
    m.name = name
    m.mention = f"<@{member_id}>"
    m.display_avatar = MagicMock()
    m.display_avatar.url = "https://cdn.discord.com/avatars/123/avatar.png"
    m.joined_at = datetime.now(timezone.utc)
    m.__str__ = MagicMock(return_value=name)
    return m


def make_invite(code="xFP2SD3UVF", uses=0, inviter=None, channel=None):
    inv = MagicMock(spec=discord.Invite)
    inv.code = code
    inv.uses = uses
    inv.max_uses = 0
    inv.max_age = 0
    inv.temporary = False
    inv.inviter = inviter or make_user()
    inv.channel = channel or make_channel()
    inv.created_at = datetime.now(timezone.utc)
    inv.expires_at = None
    inv.guild = MagicMock(id=GUILD_ID)
    inv.delete = AsyncMock()
    return inv


def setup_mock_bot(channel=None, invites=None):
    bot = MagicMock()
    bot.is_ready.return_value = True
    bot.is_closed.return_value = False

    guild = MagicMock(spec=discord.Guild)
    guild.id = GUILD_ID
    guild.name = "PB HERO TEST SERVER"
    guild.features = []
    guild.invites = AsyncMock(return_value=invites or [])

    me = MagicMock(spec=discord.Member)
    perms = MagicMock()
    perms.manage_guild = True
    perms.administrator = True
    perms.view_channel = True
    perms.send_messages = True
    perms.embed_links = True
    me.guild_permissions = perms
    guild.me = me

    active_chan = channel or make_channel()
    guild.channels = [active_chan]
    guild.get_channel = MagicMock(side_effect=lambda cid: active_chan if int(cid) == active_chan.id else None)

    bot.get_guild.return_value = guild
    bot.guild = guild
    bot.intents = MagicMock()
    bot.intents.members = True
    bot.intents.invites = True

    return bot, guild, active_chan


# ─── Fixtures ─────────────────────────────────────────────────────────────────

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
        await session.execute(delete(InviteJoin))
        await session.execute(delete(DiscordInvite))
        await session.execute(delete(InviteActivitySettings))
        user = await AdminUserRepo.get_by_username(session, "test_admin")
        if not user:
            await AdminUserRepo.create(session, "test_admin", hash_password("TestSecret123!"))
        await ServerGreetingSettingsRepo.get_or_create(session, GUILD_ID)
        await ServerConfigRepo.get_or_create(session)
        await session.commit()
    finally:
        await session.close()
    yield


@pytest_asyncio.fixture
async def auth_cookies():
    app = create_dashboard_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/v1/auth/login",
            json={"username": "test_admin", "password": "TestSecret123!"},
        )
        assert res.status_code == 200
        return client.cookies


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_01_channel_configuration():
    """1. Channel configuration persists and loads correctly."""
    session = await get_session_direct()
    try:
        cfg = await InviteActivitySettingsRepo.get_or_create(session, GUILD_ID)
        assert cfg.enabled is False
        assert cfg.channel_id is None

        updated = await InviteActivitySettingsRepo.update(
            session,
            GUILD_ID,
            enabled=True,
            channel_id=987654321,
            title_template="🎉 NEW MEMBER INVITED",
            color_hex="#2ECC71",
            log_unknown=True,
            log_vanity=True,
        )
        await session.commit()

        assert updated.enabled is True
        assert updated.channel_id == 987654321
        assert updated.color_hex == "#2ECC71"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_02_valid_channel():
    """2. Valid channel with all permissions returns HEALTHY status."""
    channel = make_channel(channel_id=2001, name="invites", view=True, send=True, embed=True)
    bot, guild, _ = setup_mock_bot(channel=channel)

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    tracker = InviteTracker(bot)
    diag = await tracker.get_activity_diagnostics()
    assert diag["enabled"] is True
    assert diag["channel_id"] == str(channel.id)
    assert diag["channel_name"] == "invites"
    assert diag["status"] == "HEALTHY"
    assert diag["is_ready"] is True
    assert diag["can_view"] is True
    assert diag["can_send"] is True
    assert diag["can_embed"] is True


@pytest.mark.asyncio
async def test_03_inaccessible_channel():
    """3. Inaccessible channel reports DEGRADED and proper reason."""
    channel = make_channel(channel_id=2001)
    bot, guild, _ = setup_mock_bot(channel=channel)

    session = await get_session_direct()
    try:
        # Configure a channel ID that does NOT exist on the guild
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=999999)
        await session.commit()
    finally:
        await session.close()

    tracker = InviteTracker(bot)
    diag = await tracker.get_activity_diagnostics()
    assert diag["status"] == "DEGRADED"
    assert "cannot send messages" in diag["reason"] or "not find" in diag["reason"]
    assert diag["is_ready"] is False


@pytest.mark.asyncio
async def test_04_permission_validation():
    """4. Permission validation detects missing Embed Links."""
    channel = make_channel(channel_id=2001, name="invites", view=True, send=True, embed=False)
    bot, guild, _ = setup_mock_bot(channel=channel)

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    tracker = InviteTracker(bot)
    diag = await tracker.get_activity_diagnostics()
    assert diag["status"] == "DEGRADED"
    assert diag["can_view"] is True
    assert diag["can_send"] is True
    assert diag["can_embed"] is False
    assert diag["is_ready"] is False


@pytest.mark.asyncio
async def test_05_successful_attributed_join_sends_embed():
    """5. Successful attributed join sends rich embed with correct details and saves message_id."""
    inviter = make_user(user_id=1001, name="Rex12400")
    channel = make_channel(channel_id=2001, name="invites")
    inv = make_invite(code="xFP2SD3UVF", uses=0, inviter=inviter, channel=channel)

    bot, guild, _ = setup_mock_bot(channel=channel, invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    # Member joins using invite
    new_member = make_member(member_id=2002, name="Rahul")
    new_member.guild = guild
    inv.uses = 1

    res = await tracker.attribute_member_join(new_member)
    assert res.source_type == "NORMAL_INVITE"
    assert res.invite_code == "xFP2SD3UVF"
    assert res.inviter_name == "Rex12400"

    # Verify channel.send was called
    assert channel.send.called
    call_kwargs = channel.send.call_args.kwargs
    embed = call_kwargs.get("embed")
    assert embed is not None
    assert "🎉 NEW MEMBER INVITED" in embed.title

    field_dict = {f.name: f.value for f in embed.fields}
    assert "<@1001>" in field_dict.get("👤 Inviter", "") or "Rex12400" in field_dict.get("👤 Inviter", "")
    assert "<@2002>" in field_dict.get("👥 New Member", "") or "Rahul" in field_dict.get("👥 New Member", "")
    assert "xFP2SD3UVF" in field_dict.get("🔗 Invite", "")
    assert field_dict.get("📊 Total Invites") == "1"
    assert field_dict.get("🏆 Rank") == "#1"

    # Verify message_id is saved on the DB join record
    session = await get_session_direct()
    try:
        q = await session.execute(select(InviteJoin).where(InviteJoin.member_id == 2002))
        join_row = q.scalar_one_or_none()
        assert join_row is not None
        assert join_row.activity_message_id == 999000111
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_06_unknown_join_sends_unknown_embed():
    """6. Unknown join sends unknown embed without attributing to any user or incrementing counters."""
    channel = make_channel(channel_id=2001, name="invites")
    bot, guild, _ = setup_mock_bot(channel=channel, invites=[])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(
            session, GUILD_ID, enabled=True, channel_id=channel.id, log_unknown=True
        )
        await session.commit()
    finally:
        await session.close()

    new_member = make_member(member_id=2003, name="Aman")
    new_member.guild = guild

    res = await tracker.attribute_member_join(new_member)
    assert res.source_type == "UNKNOWN"
    assert res.inviter_id is None

    assert channel.send.called
    embed = channel.send.call_args.kwargs.get("embed")
    assert embed is not None
    assert "⚠️ MEMBER JOINED" in embed.title
    field_dict = {f.name: f.value for f in embed.fields}
    assert field_dict.get("🔗 Invite") == "Unknown"
    assert field_dict.get("📍 Source") == "Unknown"


@pytest.mark.asyncio
async def test_07_vanity_join_sends_vanity_embed():
    """7. Vanity join sends vanity embed and does not increment personal counters."""
    channel = make_channel(channel_id=2001, name="invites")
    vanity = MagicMock(spec=discord.Invite)
    vanity.code = "pbhero"
    vanity.uses = 10
    vanity.max_uses = 0
    vanity.max_age = 0
    vanity.temporary = False
    vanity.inviter = None
    vanity.channel = channel
    vanity.guild = MagicMock(id=GUILD_ID)

    bot, guild, _ = setup_mock_bot(channel=channel, invites=[])
    guild.features = ["VANITY_URL"]
    guild.vanity_invite = AsyncMock(return_value=vanity)

    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(
            session, GUILD_ID, enabled=True, channel_id=channel.id, log_vanity=True
        )
        await session.commit()
    finally:
        await session.close()

    new_member = make_member(member_id=2004, name="VanityUser")
    new_member.guild = guild
    vanity.uses = 11  # Delta = 1

    res = await tracker.attribute_member_join(new_member)
    assert res.source_type == "VANITY_URL"
    assert res.inviter_id is None

    assert channel.send.called
    embed = channel.send.call_args.kwargs.get("embed")
    assert "✨ MEMBER JOINED VIA VANITY" in embed.title
    field_dict = {f.name: f.value for f in embed.fields}
    assert field_dict.get("📍 Source") == "Server Vanity URL"


@pytest.mark.asyncio
async def test_08_no_false_inviter_attribution():
    """8. When multiple invites delta simultaneously (ambiguous), do not assign to a random user."""
    channel = make_channel(channel_id=2001)
    inv1 = make_invite(code="INV1", uses=0, inviter=make_user(101, "User1"))
    inv2 = make_invite(code="INV2", uses=0, inviter=make_user(102, "User2"))

    bot, guild, _ = setup_mock_bot(channel=channel, invites=[inv1, inv2])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    # Both increment simultaneously
    inv1.uses = 1
    inv2.uses = 1

    m = make_member(2005, "AmbiguousUser")
    m.guild = guild
    res = await tracker.attribute_member_join(m)
    assert res.source_type == "UNKNOWN"
    assert res.inviter_id is None


@pytest.mark.asyncio
async def test_09_total_invite_counter_increments():
    """9. Inviter's total count increments properly across joins."""
    inviter = make_user(1001, "Rex12400")
    channel = make_channel(2001)
    inv = make_invite(code="xFP2SD3UVF", uses=0, inviter=inviter, channel=channel)

    bot, guild, _ = setup_mock_bot(channel=channel, invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    # Join 1
    inv.uses = 1
    m1 = make_member(3001, "Joiner1")
    m1.guild = guild
    await tracker.attribute_member_join(m1)
    embed1 = channel.send.call_args.kwargs.get("embed")
    fields1 = {f.name: f.value for f in embed1.fields}
    assert fields1["📊 Total Invites"] == "1"

    # Join 2
    inv.uses = 2
    m2 = make_member(3002, "Joiner2")
    m2.guild = guild
    await tracker.attribute_member_join(m2)
    embed2 = channel.send.call_args.kwargs.get("embed")
    fields2 = {f.name: f.value for f in embed2.fields}
    assert fields2["📊 Total Invites"] == "2"


@pytest.mark.asyncio
async def test_10_leaderboard_updates():
    """10. Leaderboard query reflects newly attributed joins."""
    session = await get_session_direct()
    try:
        await InviteJoinRepo.record_join(
            session, GUILD_ID, 4001, "User1", "CODE1", 1001, "Rex12400", "NORMAL_INVITE", 2001, "invites"
        )
        await InviteJoinRepo.record_join(
            session, GUILD_ID, 4002, "User2", "CODE2", 1002, "OtherUser", "NORMAL_INVITE", 2001, "invites"
        )
        await InviteJoinRepo.record_join(
            session, GUILD_ID, 4003, "User3", "CODE1", 1001, "Rex12400", "NORMAL_INVITE", 2001, "invites"
        )
        await session.commit()

        leaderboard = await InviteJoinRepo.get_leaderboard(session, GUILD_ID, limit=10)
        assert len(leaderboard) == 2
        assert leaderboard[0]["user_id"] == "1001"
        assert leaderboard[0]["joins"] == 2
        assert leaderboard[1]["user_id"] == "1002"
        assert leaderboard[1]["joins"] == 1
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_11_rank_calculation():
    """11. Rank calculation returns fast and accurate 1-based ranks."""
    session = await get_session_direct()
    try:
        # User 1001 gets 3 joins -> Rank #1
        for i in range(3):
            await InviteJoinRepo.record_join(
                session, GUILD_ID, 5000 + i, f"Joiner{i}", "C1", 1001, "UserTop", "NORMAL_INVITE", 2001, "inv"
            )
        # User 1002 gets 1 join -> Rank #2
        await InviteJoinRepo.record_join(
            session, GUILD_ID, 5010, "JoinerX", "C2", 1002, "UserSecond", "NORMAL_INVITE", 2001, "inv"
        )
        await session.commit()

        rank_top = await InviteJoinRepo.get_user_rank(session, GUILD_ID, 1001)
        rank_sec = await InviteJoinRepo.get_user_rank(session, GUILD_ID, 1002)
        rank_none = await InviteJoinRepo.get_user_rank(session, GUILD_ID, 9999)

        assert rank_top == 1
        assert rank_sec == 2
        assert rank_none is None
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_12_duplicate_event_prevention():
    """12. Dispatching activity log for an already processed join_record_id does not re-send embed."""
    channel = make_channel(2001)
    bot, guild, _ = setup_mock_bot(channel=channel)

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        # Create a join record that already has activity_message_id set
        join_rec = await InviteJoinRepo.record_join(
            session, GUILD_ID, 6001, "AlreadyLogged", "CODE", 1001, "Rex12400", "NORMAL_INVITE", 2001, "inv",
            activity_message_id=888999
        )
        await session.commit()
        join_id = join_rec.id
    finally:
        await session.close()

    tracker = InviteTracker(bot)
    m = make_member(6001, "AlreadyLogged")
    m.guild = guild
    res = AttributionResult(
        member_id=6001,
        member_name="AlreadyLogged",
        invite_code="CODE",
        inviter_id=1001,
        inviter_name="Rex12400",
        source_type="NORMAL_INVITE",
        channel_id=2001,
        channel_name="inv",
        joined_at=datetime.now(timezone.utc),
    )

    msg_id = await tracker._dispatch_activity_log(m, res, join_record_id=join_id)
    assert msg_id == 888999
    # channel.send should NOT have been called again!
    assert not channel.send.called


@pytest.mark.asyncio
async def test_13_reconnect_safety():
    """13. Syncing invites on reconnect never replays joins or sends activity messages."""
    channel = make_channel(2001)
    inv = make_invite(code="RECONNECT_CODE", uses=5)
    bot, guild, _ = setup_mock_bot(channel=channel, invites=[inv])

    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    # Re-sync
    await tracker.sync_invites(force=True)
    assert not channel.send.called


@pytest.mark.asyncio
async def test_14_restart_safety():
    """14. Bot restart re-initializes cache from Discord without generating false join logs."""
    channel = make_channel(2001)
    inv = make_invite(code="RESTART_CODE", uses=10)
    bot, guild, _ = setup_mock_bot(channel=channel, invites=[inv])

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    # Brand new tracker instance (simulates restart)
    new_tracker = InviteTracker(bot)
    await new_tracker.sync_invites()
    assert not channel.send.called


@pytest.mark.asyncio
async def test_15_template_rendering():
    """15. Configured template variables render cleanly in embed title and description."""
    channel = make_channel(2001)
    bot, guild, _ = setup_mock_bot(channel=channel)

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(
            session,
            GUILD_ID,
            enabled=True,
            channel_id=channel.id,
            title_template="👑 VIP JOIN: {member}",
            description_template="{inviter} brought {member} into {server_name}! Rank: {rank}",
        )
        await session.commit()
    finally:
        await session.close()

    tracker = InviteTracker(bot)
    m = make_member(7001, "Alice")
    m.guild = guild
    res = AttributionResult(
        member_id=7001,
        member_name="Alice",
        invite_code="VIP123",
        inviter_id=1001,
        inviter_name="Bob",
        source_type="NORMAL_INVITE",
        channel_id=2001,
        channel_name="invites",
        joined_at=datetime.now(timezone.utc),
    )

    await tracker._dispatch_activity_log(m, res)
    assert channel.send.called
    embed = channel.send.call_args.kwargs.get("embed")
    assert embed.title == "👑 VIP JOIN: Alice"
    assert "Bob brought Alice into PB HERO TEST SERVER! Rank:" in embed.description


@pytest.mark.asyncio
async def test_16_test_notification_does_not_change_counters():
    """16. Test activity log sends preview embed without modifying database counters."""
    channel = make_channel(2001, name="invites")
    bot, guild, _ = setup_mock_bot(channel=channel)

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    tracker = InviteTracker(bot)
    res = await tracker.send_test_activity_log()
    assert res["success"] is True
    assert res["channel_id"] == str(channel.id)

    assert channel.send.called
    embed = channel.send.call_args.kwargs.get("embed")
    assert "🧪 INVITE TRACKING TEST" in embed.title

    # Verify 0 records in InviteJoin table
    session = await get_session_direct()
    try:
        q = await session.execute(select(InviteJoin))
        rows = q.scalars().all()
        assert len(rows) == 0
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_17_discord_send_failure_does_not_lose_attribution():
    """17. If sending to Discord channel fails, database attribution remains intact."""
    channel = make_channel(2001)
    channel.send.side_effect = discord.DiscordException("Simulated Discord API Error")

    inv = make_invite(code="FAIL_SEND", uses=0, inviter=make_user(1001), channel=channel)
    bot, guild, _ = setup_mock_bot(channel=channel, invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    inv.uses = 1
    m = make_member(8001, "Dave")
    m.guild = guild

    # Should not raise exception
    res = await tracker.attribute_member_join(m)
    assert res.source_type == "NORMAL_INVITE"

    # DB join must exist!
    session = await get_session_direct()
    try:
        q = await session.execute(select(InviteJoin).where(InviteJoin.member_id == 8001))
        row = q.scalar_one_or_none()
        assert row is not None
        assert row.invite_code == "FAIL_SEND"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_18_disabled_logging():
    """18. When logging is disabled, join attribution persists but no message is sent."""
    channel = make_channel(2001)
    inv = make_invite(code="DISABLED_LOG", uses=0, inviter=make_user(1001), channel=channel)
    bot, guild, _ = setup_mock_bot(channel=channel, invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=False, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    inv.uses = 1
    m = make_member(9001, "Eve")
    m.guild = guild

    res = await tracker.attribute_member_join(m)
    assert res.source_type == "NORMAL_INVITE"
    assert not channel.send.called


@pytest.mark.asyncio
async def test_19_channel_switch():
    """19. Switching channel sends future joins to the new channel without touching old channel."""
    channel1 = make_channel(2001, name="old-invites")
    channel2 = make_channel(2002, name="new-invites")

    bot = MagicMock()
    bot.is_ready.return_value = True
    guild = MagicMock(spec=discord.Guild)
    guild.id = GUILD_ID
    guild.name = "PB HERO TEST SERVER"
    guild.features = []

    inv = make_invite(code="SWITCH_CODE", uses=0, inviter=make_user(1001), channel=channel1)
    guild.invites = AsyncMock(return_value=[inv])
    guild.get_channel = MagicMock(side_effect=lambda cid: channel1 if int(cid) == 2001 else (channel2 if int(cid) == 2002 else None))

    me = MagicMock()
    me.guild_permissions = MagicMock(manage_guild=True, administrator=True, view_channel=True, send_messages=True, embed_links=True)
    guild.me = me
    bot.get_guild.return_value = guild

    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        # Start on channel 1
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=2001)
        await session.commit()
    finally:
        await session.close()

    inv.uses = 1
    m1 = make_member(10001, "FirstJoiner")
    m1.guild = guild
    await tracker.attribute_member_join(m1)
    assert channel1.send.called
    assert not channel2.send.called

    channel1.send.reset_mock()

    # Switch to channel 2
    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, channel_id=2002)
        await session.commit()
    finally:
        await session.close()

    inv.uses = 2
    m2 = make_member(10002, "SecondJoiner")
    m2.guild = guild
    await tracker.attribute_member_join(m2)
    assert not channel1.send.called
    assert channel2.send.called


@pytest.mark.asyncio
async def test_20_historical_data_preserved():
    """20. When member leaves, original join and inviter stats remain intact."""
    inviter = make_user(1001, "Rex12400")
    channel = make_channel(2001)
    inv = make_invite(code="HIST_PRESERVE", uses=0, inviter=inviter, channel=channel)
    bot, guild, _ = setup_mock_bot(channel=channel, invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        await InviteActivitySettingsRepo.update(session, GUILD_ID, enabled=True, channel_id=channel.id)
        await session.commit()
    finally:
        await session.close()

    inv.uses = 1
    m = make_member(11001, "Leaver")
    m.guild = guild
    await tracker.attribute_member_join(m)

    # Member leaves
    await tracker.handle_member_leave(m)

    session = await get_session_direct()
    try:
        q = await session.execute(select(InviteJoin).where(InviteJoin.member_id == 11001))
        row = q.scalar_one_or_none()
        assert row is not None
        assert row.is_still_member is False
        assert row.left_at is not None

        # Inviter's total count is NOT reduced
        stats = await InviteJoinRepo.get_user_stats(session, GUILD_ID, 1001)
        assert stats["total_joins"] == 1
        assert stats["former_members_referred"] == 1
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_21_dashboard_api_activity_settings_flow(auth_cookies):
    """21. API test: GET, PUT, RESET, CHANNELS, TEST endpoints."""
    channel = make_channel(2001, name="invites", view=True, send=True, embed=True)
    bot, guild, _ = setup_mock_bot(channel=channel)

    app = create_dashboard_app()
    transport = ASGITransport(app=app)

    with patch("app.runtime_state.get_bot_instance", return_value=bot):
        async with AsyncClient(transport=transport, base_url="http://testserver", cookies=auth_cookies) as client:
            # 1. GET Settings
            res = await client.get("/api/v1/moderation/invites/activity-settings")
            assert res.status_code == 200
            data = res.json()
            assert "enabled" in data
            assert "title_template" in data

            # 2. PUT Settings
            put_res = await client.put(
                "/api/v1/moderation/invites/activity-settings",
                json={
                    "enabled": True,
                    "channel_id": "2001",
                    "title_template": "🔥 CUSTOM TITLE",
                    "description_template": "{inviter} welcomed {member}",
                    "color_hex": "#00FF00",
                },
            )
            assert put_res.status_code == 200
            updated_data = put_res.json()
            assert updated_data["enabled"] is True
            assert updated_data["channel_id"] == "2001"
            assert updated_data["title_template"] == "🔥 CUSTOM TITLE"

            # 3. GET Channels
            ch_res = await client.get("/api/v1/moderation/invites/channels")
            assert ch_res.status_code == 200
            ch_list = ch_res.json()
            assert len(ch_list) >= 1
            assert ch_list[0]["id"] == "2001"
            assert ch_list[0]["status_label"] == "✅ Ready"

            # 4. POST Test Log
            test_res = await client.post("/api/v1/moderation/invites/activity-settings/test")
            assert test_res.status_code == 200
            assert test_res.json()["success"] is True

            # 5. POST Reset Template
            reset_res = await client.post("/api/v1/moderation/invites/activity-settings/reset")
            assert reset_res.status_code == 200
            reset_data = reset_res.json()
            assert reset_data["title_template"] == "🎉 NEW MEMBER INVITED"
            assert reset_data["color_hex"] == "#5865F2"
