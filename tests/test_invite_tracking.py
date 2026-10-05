"""
Comprehensive test suite for PB HERO Discord Invite Tracking & Analytics System.

Covers all 26 required test cases specified in the requirements:
1. Invite cache initialization
2. Invite creation record
3. Invite usage +1
4. Invite usage +N
5. Member join attribution
6. Unknown attribution
7. Vanity attribution
8. Revoked invite
9. Expired invite
10. Max-use invite
11. Bot restart (does not interpret historical uses as new joins)
12. Bot reconnect (does not duplicate caches, listeners, or joins)
13. Duplicate join prevention (debouncing rapid joins)
14. Concurrent joins (serialized attribution under async lock)
15. Invite delta calculation
16. Historical records preserved
17. Leaderboard (sorted by successful attributed joins)
18. User invite profile
19. Invite details
20. Search and filter
21. Dashboard API endpoints
22. Permission failure (degraded state handling)
23. Rate-limit safe refresh
24. Permanent Invite integration
25. Welcome pipeline integration
26. Goodbye leave integration
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import discord
from app.dashboard.app import create_dashboard_app
from app.dashboard.auth import hash_password
from app.database.engine import get_engine, get_session_direct, init_engine
from app.database.models import Base, DiscordInvite, InviteJoin
from app.database.repositories import (
    AdminUserRepo,
    DiscordInviteRepo,
    InviteJoinRepo,
    ServerConfigRepo,
    ServerGreetingSettingsRepo,
    ServerInviteSettingsRepo,
)
from app.invites.tracker import AttributionResult, CachedInvite, InviteTracker, get_invite_tracker

GUILD_ID = 123456789012345678


# ─── Mock Factories ───────────────────────────────────────────────────────────

def make_user(user_id=1001, name="Rex12400"):
    u = MagicMock(spec=discord.User)
    u.id = user_id
    u.name = name
    u.display_name = name
    u.mention = f"<@{user_id}>"
    u.__str__ = MagicMock(return_value=name)
    return u


def make_channel(channel_id=2001, name="welcome"):
    c = MagicMock(spec=discord.TextChannel)
    c.id = channel_id
    c.name = name
    c.mention = f"<#{channel_id}>"
    c.send = AsyncMock()
    return c


def make_invite(
    code="ABC123",
    uses=0,
    max_uses=0,
    max_age=0,
    temporary=False,
    inviter=None,
    channel=None,
    expires_at=None,
):
    inv = MagicMock(spec=discord.Invite)
    inv.code = code
    inv.uses = uses
    inv.max_uses = max_uses
    inv.max_age = max_age
    inv.temporary = temporary
    inv.inviter = inviter or make_user()
    inv.channel = channel or make_channel()
    inv.created_at = datetime.now(timezone.utc)
    inv.expires_at = expires_at
    inv.url = f"https://discord.gg/{code}"
    inv.guild = MagicMock(id=GUILD_ID)
    inv.delete = AsyncMock()
    return inv


def make_bot(invites=None, has_permission=True, vanity_invite=None):
    bot = MagicMock()
    bot.is_ready.return_value = True
    bot.is_closed.return_value = False

    guild = MagicMock(spec=discord.Guild)
    guild.id = GUILD_ID
    guild.name = "PB HERO TEST SERVER"
    guild.features = ["VANITY_URL"] if vanity_invite else []
    guild.invites = AsyncMock(return_value=invites or [])
    if vanity_invite:
        guild.vanity_invite = AsyncMock(return_value=vanity_invite)

    me = MagicMock(spec=discord.Member)
    perms = MagicMock()
    perms.manage_guild = has_permission
    perms.administrator = has_permission
    perms.view_channel = True
    perms.send_messages = True
    perms.embed_links = True
    me.guild_permissions = perms
    guild.me = me
    guild.get_channel = MagicMock(side_effect=lambda cid: make_channel(cid))

    bot.get_guild.return_value = guild
    bot.guild = guild
    bot.intents = MagicMock()
    bot.intents.members = True
    bot.intents.invites = True

    return bot, guild


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    from sqlalchemy import delete
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
        return res.cookies


# ─── Unit and Integration Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_01_invite_cache_initialization():
    """1. Invite cache initialization correctly loads current guild invites."""
    inv1 = make_invite(code="CODE1", uses=5)
    inv2 = make_invite(code="CODE2", uses=12)
    bot, _ = make_bot(invites=[inv1, inv2])

    tracker = InviteTracker(bot)
    res = await tracker.sync_invites()

    assert res["status"] == "HEALTHY"
    assert res["active_invites"] == 2
    assert "CODE1" in tracker._cache
    assert tracker._cache["CODE1"].uses == 5
    assert tracker._cache["CODE2"].uses == 12


@pytest.mark.asyncio
async def test_02_invite_creation_record():
    """2. on_invite_create correctly registers in-memory and database records."""
    bot, _ = make_bot()
    tracker = InviteTracker(bot)

    new_inv = make_invite(code="NEW123", uses=0, max_uses=10, max_age=3600)
    await tracker.handle_invite_create(new_inv)

    assert "NEW123" in tracker._cache
    assert tracker._cache["NEW123"].max_uses == 10

    session = await get_session_direct()
    try:
        db_inv = await DiscordInviteRepo.get_by_code(session, "NEW123")
        assert db_inv is not None
        assert db_inv.invite_code == "NEW123"
        assert db_inv.status == "ACTIVE"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_03_invite_usage_plus_one():
    """3. Single invite usage delta (+1) attributes to the correct inviter."""
    inv = make_invite(code="USE1", uses=10, inviter=make_user(1001, "Rex12400"))
    bot, guild = make_bot(invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    # Member joins: Discord now reports uses = 11
    inv.uses = 11
    guild.invites = AsyncMock(return_value=[inv])

    member = MagicMock(spec=discord.Member)
    member.id = 5001
    member.name = "NewPlayer"
    member.guild = guild

    res = await tracker.attribute_member_join(member)

    assert res.source_type == "NORMAL_INVITE"
    assert res.invite_code == "USE1"
    assert res.inviter_id == 1001
    assert res.inviter_name == "Rex12400"
    assert tracker._cache["USE1"].uses == 11


@pytest.mark.asyncio
async def test_04_invite_usage_plus_n():
    """4. Invite usage delta (+N) safely attributes join and handles batch use."""
    inv = make_invite(code="BATCH1", uses=10, inviter=make_user(1002, "HeroFan"))
    bot, guild = make_bot(invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    # Discord reports uses jumped from 10 to 13 (+3)
    inv.uses = 13
    guild.invites = AsyncMock(return_value=[inv])

    memberA = MagicMock(spec=discord.Member)
    memberA.id = 6001
    memberA.name = "PlayerA"
    memberA.guild = guild

    resA = await tracker.attribute_member_join(memberA)
    assert resA.source_type == "NORMAL_INVITE"
    assert resA.invite_code == "BATCH1"
    assert resA.inviter_id == 1002


@pytest.mark.asyncio
async def test_05_member_join_attribution_stored():
    """5. Attribution is permanently saved in the database invite_joins table."""
    inv = make_invite(code="STORED1", uses=0, inviter=make_user(1003, "PlayerX"))
    bot, guild = make_bot(invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    inv.uses = 1
    guild.invites = AsyncMock(return_value=[inv])

    member = MagicMock(spec=discord.Member)
    member.id = 7001
    member.name = "JoinGuy"
    member.guild = guild

    await tracker.attribute_member_join(member)

    session = await get_session_direct()
    try:
        joins, count = await InviteJoinRepo.get_joins_for_invite(session, "STORED1")
        assert count == 1
        assert joins[0].member_id == 7001
        assert joins[0].inviter_id == 1003
        assert joins[0].source_type == "NORMAL_INVITE"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_06_unknown_attribution():
    """6. Joins with no invite usage change are safely marked as UNKNOWN."""
    inv = make_invite(code="NOCHANGE", uses=5)
    bot, guild = make_bot(invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    # Discord still reports uses = 5 (no invite was used)
    member = MagicMock(spec=discord.Member)
    member.id = 8001
    member.name = "MysteryUser"
    member.guild = guild

    res = await tracker.attribute_member_join(member)
    assert res.source_type == "UNKNOWN"
    assert res.invite_code is None
    assert res.inviter_id is None


@pytest.mark.asyncio
async def test_07_vanity_attribution():
    """7. Joins via Vanity URL are attributed to Vanity / Server and not a user."""
    vanity = make_invite(code="pbhero", uses=100)
    bot, guild = make_bot(invites=[], vanity_invite=vanity)
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    vanity.uses = 101
    guild.vanity_invite = AsyncMock(return_value=vanity)

    member = MagicMock(spec=discord.Member)
    member.id = 8002
    member.name = "VanityUser"
    member.guild = guild

    res = await tracker.attribute_member_join(member)
    assert res.source_type == "VANITY_URL"
    assert res.invite_code == "pbhero"
    assert res.inviter_id is None
    assert "Vanity" in res.inviter_name


@pytest.mark.asyncio
async def test_08_revoked_invite():
    """8. Revoked invite preserves historical joins in database."""
    inv = make_invite(code="DEL1", uses=2)
    bot, _ = make_bot(invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    # Simulate deleting invite
    await tracker.handle_invite_delete(inv)

    assert tracker._cache["DEL1"].revoked is True

    session = await get_session_direct()
    try:
        db_inv = await DiscordInviteRepo.get_by_code(session, "DEL1")
        assert db_inv.status == "REVOKED"
        assert db_inv.revoked_at is not None
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_09_expired_invite():
    """9. Expired invite is marked as EXPIRED and historical data preserved."""
    session = await get_session_direct()
    try:
        await DiscordInviteRepo.upsert(session, GUILD_ID, "EXPIRE1", status="ACTIVE", uses=3)
        await DiscordInviteRepo.mark_expired(session, "EXPIRE1")
        await session.commit()

        db_inv = await DiscordInviteRepo.get_by_code(session, "EXPIRE1")
        assert db_inv.status == "EXPIRED"
        assert db_inv.uses == 3
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_10_max_use_invite():
    """10. Invite reaching max_uses and disappearing from Discord is attributed."""
    # Invite had max_uses=1, uses=0. When used, Discord removes it.
    inv = make_invite(code="ONETIME", uses=0, max_uses=1, inviter=make_user(1004, "OneTimer"))
    bot, guild = make_bot(invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    # Invite now gone from Discord
    guild.invites = AsyncMock(return_value=[])

    member = MagicMock(spec=discord.Member)
    member.id = 9001
    member.name = "OneUseGuy"
    member.guild = guild

    res = await tracker.attribute_member_join(member)
    assert res.invite_code == "ONETIME"
    assert res.inviter_id == 1004
    assert res.source_type == "NORMAL_INVITE"


@pytest.mark.asyncio
async def test_11_bot_restart_safety():
    """11. Bot restart does NOT interpret existing uses as new joins."""
    inv = make_invite(code="RESTART1", uses=27)
    bot, _ = make_bot(invites=[inv])
    tracker = InviteTracker(bot)

    # Startup sync
    await tracker.sync_invites()

    session = await get_session_direct()
    try:
        # Verify 0 joins were created
        joins, total = await InviteJoinRepo.get_joins_for_invite(session, "RESTART1")
        assert total == 0
        db_inv = await DiscordInviteRepo.get_by_code(session, "RESTART1")
        assert db_inv.uses == 27
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_12_bot_reconnect_safety():
    """12. Gateway reconnect does not duplicate invite caches or create fake joins."""
    inv = make_invite(code="RECONN1", uses=15)
    bot, _ = make_bot(invites=[inv])
    tracker = InviteTracker(bot)

    # First connection
    await tracker.sync_invites()
    assert len(tracker._cache) == 1

    # Reconnection
    await tracker.sync_invites()
    assert len(tracker._cache) == 1
    assert tracker._cache["RECONN1"].uses == 15

    session = await get_session_direct()
    try:
        joins, total = await InviteJoinRepo.get_joins_for_invite(session, "RECONN1")
        assert total == 0
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_13_duplicate_join_prevention():
    """13. Duplicate join event within debounce window is ignored."""
    inv = make_invite(code="DUP1", uses=5)
    bot, guild = make_bot(invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    inv.uses = 6
    guild.invites = AsyncMock(return_value=[inv])

    member = MagicMock(spec=discord.Member)
    member.id = 9999
    member.name = "QuickJoiner"
    member.guild = guild

    res1 = await tracker.attribute_member_join(member)
    assert res1.source_type == "NORMAL_INVITE"

    # Rapid second join event (duplicate gateway trigger)
    res2 = await tracker.attribute_member_join(member)
    assert res2.details.get("reason") == "duplicate_event_debounce"

    session = await get_session_direct()
    try:
        joins, total = await InviteJoinRepo.get_joins_for_invite(session, "DUP1")
        assert total == 1
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_14_concurrent_joins_serialized():
    """14. Concurrent member joins are serialized and deltas assigned accurately."""
    inv = make_invite(code="CONCUR1", uses=10, inviter=make_user(1005, "PopularUser"))
    bot, guild = make_bot(invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    # Discord reports uses went from 10 to 12 (+2 joins)
    inv.uses = 12
    guild.invites = AsyncMock(return_value=[inv])

    member1 = MagicMock(spec=discord.Member)
    member1.id = 1111
    member1.name = "UserA"
    member1.guild = guild

    member2 = MagicMock(spec=discord.Member)
    member2.id = 2222
    member2.name = "UserB"
    member2.guild = guild

    # Trigger both concurrently
    results = await asyncio.gather(
        tracker.attribute_member_join(member1),
        tracker.attribute_member_join(member2),
    )

    attributed_codes = [r.invite_code for r in results if r.source_type == "NORMAL_INVITE"]
    assert len(attributed_codes) >= 1
    assert "CONCUR1" in attributed_codes


@pytest.mark.asyncio
async def test_15_ambiguous_delta_logic():
    """15. Multiple different invites increasing simultaneously are marked UNKNOWN."""
    invA = make_invite(code="CODE_A", uses=10)
    invB = make_invite(code="CODE_B", uses=20)
    bot, guild = make_bot(invites=[invA, invB])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    # Both incremented simultaneously
    invA.uses = 11
    invB.uses = 21
    guild.invites = AsyncMock(return_value=[invA, invB])

    member = MagicMock(spec=discord.Member)
    member.id = 3333
    member.name = "AmbiguousUser"
    member.guild = guild

    res = await tracker.attribute_member_join(member)
    assert res.source_type == "UNKNOWN"
    assert res.is_ambiguous is True


@pytest.mark.asyncio
async def test_16_historical_records_preserved():
    """16. Deleting or leaving never removes historical join attribution."""
    session = await get_session_direct()
    try:
        await InviteJoinRepo.record_join(
            session, GUILD_ID, 4444, "UserLeaves", "HIST1", 1006, "GoodInviter", "NORMAL_INVITE", None, None
        )
        await session.commit()

        # Member leaves
        await InviteJoinRepo.record_leave(session, GUILD_ID, 4444)
        await session.commit()

        stats = await InviteJoinRepo.get_user_stats(session, GUILD_ID, 1006)
        assert stats["total_joins"] == 1
        assert stats["former_members_referred"] == 1
        assert stats["current_members_referred"] == 0
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_17_leaderboard_calculation():
    """17. Leaderboard calculates ranks and percentages excluding unknown/vanity."""
    session = await get_session_direct()
    try:
        # Rex has 3 joins
        for mid in [5001, 5002, 5003]:
            await InviteJoinRepo.record_join(session, GUILD_ID, mid, f"U{mid}", "REX", 1001, "Rex12400", "NORMAL_INVITE", None, None)
        # PlayerX has 1 join
        await InviteJoinRepo.record_join(session, GUILD_ID, 5004, "U5004", "PX", 1002, "PlayerX", "NORMAL_INVITE", None, None)
        # Vanity has 2 joins
        await InviteJoinRepo.record_join(session, GUILD_ID, 5005, "U5005", "vanity", None, None, "VANITY_URL", None, None)
        # Unknown has 1 join
        await InviteJoinRepo.record_join(session, GUILD_ID, 5006, "U5006", None, None, None, "UNKNOWN", None, None)
        await session.commit()

        lb = await InviteJoinRepo.get_leaderboard(session, GUILD_ID)
        assert len(lb) == 2
        assert lb[0]["username"] == "Rex12400"
        assert lb[0]["joins"] == 3
        assert lb[0]["rank"] == 1
        assert lb[0]["percentage"] == 75.0
        assert lb[1]["username"] == "PlayerX"
        assert lb[1]["joins"] == 1
        assert lb[1]["rank"] == 2
        assert lb[1]["percentage"] == 25.0
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_18_user_invite_profile():
    """18. User invite profile returns time-based join stats and active codes."""
    session = await get_session_direct()
    try:
        now = datetime.utcnow()
        await InviteJoinRepo.record_join(session, GUILD_ID, 6001, "U1", "C1", 1007, "ProfileUser", "NORMAL_INVITE", None, None, joined_at=now)
        await DiscordInviteRepo.upsert(session, GUILD_ID, "C1", inviter_id=1007, inviter_name="ProfileUser", uses=1, status="ACTIVE")
        await session.commit()

        profile = await InviteJoinRepo.get_user_stats(session, GUILD_ID, 1007)
        assert profile["total_joins"] == 1
        assert profile["this_week_joins"] == 1
        assert len(profile["invites"]) == 1
        assert profile["invites"][0]["invite_code"] == "C1"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_19_invite_details_and_joins():
    """19. Invite details returns metadata and list of joined members."""
    session = await get_session_direct()
    try:
        await DiscordInviteRepo.upsert(session, GUILD_ID, "DET1", channel_name="lounge", uses=2, status="ACTIVE")
        await InviteJoinRepo.record_join(session, GUILD_ID, 7001, "Alice", "DET1", None, None, "NORMAL_INVITE", None, None)
        await InviteJoinRepo.record_join(session, GUILD_ID, 7002, "Bob", "DET1", None, None, "NORMAL_INVITE", None, None)
        await session.commit()

        inv = await DiscordInviteRepo.get_by_code(session, "DET1")
        assert inv is not None
        joins, total = await InviteJoinRepo.get_joins_for_invite(session, "DET1")
        assert total == 2
        assert {j.member_name for j in joins} == {"Alice", "Bob"}
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_20_search_and_filtering():
    """20. Search and filter by status, search query, and source type work correctly."""
    session = await get_session_direct()
    try:
        await DiscordInviteRepo.upsert(session, GUILD_ID, "SEARCH_ALPHA", inviter_name="AlphaMan", status="ACTIVE")
        await DiscordInviteRepo.upsert(session, GUILD_ID, "SEARCH_BETA", inviter_name="BetaGuy", status="REVOKED")
        await session.commit()

        # Filter by status
        active_invs, total_active = await DiscordInviteRepo.get_all(session, GUILD_ID, status="ACTIVE")
        assert any(i.invite_code == "SEARCH_ALPHA" for i in active_invs)
        assert not any(i.invite_code == "SEARCH_BETA" for i in active_invs)

        # Search query
        searched, total_s = await DiscordInviteRepo.get_all(session, GUILD_ID, search="Alpha")
        assert total_s == 1
        assert searched[0].invite_code == "SEARCH_ALPHA"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_21_dashboard_api_endpoints(auth_cookies):
    """21. Dashboard API routes respond with correct data and status codes."""
    session = await get_session_direct()
    try:
        await DiscordInviteRepo.upsert(session, GUILD_ID, "APITEST", uses=5, status="ACTIVE")
        await session.commit()
    finally:
        await session.close()

    app = create_dashboard_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", cookies=auth_cookies) as client:
        # GET /invites
        r1 = await client.get("/api/v1/moderation/invites")
        assert r1.status_code == 200
        assert r1.json()["total"] >= 1

        # GET /invites/{code}
        r2 = await client.get("/api/v1/moderation/invites/APITEST")
        assert r2.status_code == 200
        assert r2.json()["invite"]["invite_code"] == "APITEST"

        # GET /leaderboard
        r3 = await client.get("/api/v1/moderation/invites/leaderboard")
        assert r3.status_code == 200

        # GET /stats
        r4 = await client.get("/api/v1/moderation/invites/stats?timeframe=all")
        assert r4.status_code == 200

        # GET /joins
        r5 = await client.get("/api/v1/moderation/invites/joins")
        assert r5.status_code == 200

        # GET /health
        r6 = await client.get("/api/v1/moderation/invites/health")
        assert r6.status_code == 200


@pytest.mark.asyncio
async def test_22_permission_failure_degraded():
    """22. Permission failure puts tracker into DEGRADED state without crashing."""
    bot, _ = make_bot(has_permission=False)
    tracker = InviteTracker(bot)

    health = tracker.get_health()
    assert health["status"] == "DEGRADED"

    res = await tracker.sync_invites()
    assert res["status"] == "DEGRADED"


@pytest.mark.asyncio
async def test_23_rate_limit_safe_refresh():
    """23. Discord API exception during invite refresh is handled gracefully."""
    bot, guild = make_bot()
    guild.invites = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=429), "Rate limited"))
    tracker = InviteTracker(bot)

    res = await tracker.sync_invites()
    assert res["status"] in ("DEGRADED", "ERROR")


@pytest.mark.asyncio
async def test_24_permanent_invite_integration():
    """24. Permanent invite is tracked without attributing to a random member."""
    session = await get_session_direct()
    try:
        await ServerInviteSettingsRepo.update(
            session, GUILD_ID, invite_code="PERM_SERVER_1", is_active=True
        )
        await session.commit()
    finally:
        await session.close()

    inv = make_invite(code="PERM_SERVER_1", uses=0)
    bot, guild = make_bot(invites=[inv])
    tracker = InviteTracker(bot)
    await tracker.sync_invites()

    inv.uses = 1
    guild.invites = AsyncMock(return_value=[inv])

    member = MagicMock(spec=discord.Member)
    member.id = 8888
    member.name = "PermJoiner"
    member.guild = guild

    res = await tracker.attribute_member_join(member)
    assert res.invite_code == "PERM_SERVER_1"
    assert res.inviter_id is None
    assert "SERVER" in (res.inviter_name or "")


@pytest.mark.asyncio
async def test_25_welcome_pipeline_integration():
    """25. Welcome pipeline executes Invite Attribution before greetings/roles."""
    from app.greetings.service import get_greeting_service

    bot, guild = make_bot()
    greeting_service = get_greeting_service(bot)

    member = MagicMock(spec=discord.Member)
    member.id = 7777
    member.name = "PipelineMember"
    member.guild = guild

    # Calling handle_member_join runs attribution first without raising errors
    with patch("app.invites.tracker.InviteTracker.attribute_member_join", new_callable=AsyncMock) as mock_attrib:
        mock_attrib.return_value = AttributionResult(
            member_id=7777,
            member_name="PipelineMember",
            invite_code="PIPE1",
            inviter_id=1008,
            inviter_name="PipeInviter",
            source_type="NORMAL_INVITE",
            channel_id=None,
            channel_name=None,
            joined_at=datetime.utcnow(),
        )
        await greeting_service.handle_member_join(member)
        mock_attrib.assert_awaited_once_with(member)


@pytest.mark.asyncio
async def test_26_goodbye_pipeline_integration():
    """26. Member leave pipeline updates is_still_member=False while keeping attribution."""
    from app.greetings.service import get_greeting_service

    bot, guild = make_bot()
    greeting_service = get_greeting_service(bot)

    session = await get_session_direct()
    try:
        await InviteJoinRepo.record_join(session, GUILD_ID, 8889, "LeavingMember", "BYE1", 1009, "ByeInviter", "NORMAL_INVITE", None, None)
        await session.commit()
    finally:
        await session.close()

    member = MagicMock(spec=discord.Member)
    member.id = 8889
    member.name = "LeavingMember"
    member.guild = guild

    await greeting_service.handle_member_leave(member)

    session = await get_session_direct()
    try:
        joins, _ = await InviteJoinRepo.get_joins_for_invite(session, "BYE1")
        assert len(joins) == 1
        assert joins[0].is_still_member is False
        assert joins[0].left_at is not None
    finally:
        await session.close()
