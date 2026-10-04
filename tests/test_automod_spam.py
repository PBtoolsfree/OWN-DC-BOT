"""
Tests for Automod Message Spam, Gateway Reliability, and Enforcement:
- message_spam below threshold
- message_spam at threshold
- messages outside window
- different users do not share counts
- different channels behave according to configured scope
- exempt user bypass
- exempt role bypass
- bot bypass
- delete action
- timeout action
- delete+timeout when timeout permission fails
- gateway reconnect does not duplicate handlers
- message_content intent check
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import discord

from app.bot.client import PBHeroBot
from app.database.models import ModerationAction
from app.moderation.evaluator import (
    SpamTracker,
    evaluate_automod_rules,
    parse_action_string,
)
from app.moderation.engine import ModerationEngine, can_moderate_member


# ─── 1. message_spam below threshold ──────────────────────────────────────────

def test_message_spam_below_threshold():
    tracker = SpamTracker()
    rules = [{
        "rule_type": "message_spam",
        "name": "Message Spam",
        "threshold": 3,
        "time_window": 10,
        "action": "delete_timeout",
        "enabled": True,
    }]

    # 1st message at t=100
    res1 = evaluate_automod_rules(
        rules=rules,
        content="Hello 1",
        guild_id=1,
        channel_id=10,
        user_id=100,
        timestamp=100.0,
        spam_tracker=tracker,
    )
    assert res1 is None

    # 2nd message at t=102
    res2 = evaluate_automod_rules(
        rules=rules,
        content="Hello 2",
        guild_id=1,
        channel_id=10,
        user_id=100,
        timestamp=102.0,
        spam_tracker=tracker,
    )
    assert res2 is None
    assert tracker.check_count(1, 10, 100, timestamp=102.0, window_seconds=10) == 2


# ─── 2. message_spam at threshold ──────────────────────────────────────────────

def test_message_spam_at_threshold():
    tracker = SpamTracker()
    rules = [{
        "rule_type": "message_spam",
        "name": "Message Spam",
        "threshold_count": 3,  # Test threshold_count alias
        "window_seconds": 10,  # Test window_seconds alias
        "action": "delete_timeout",
        "action_duration": 300,
        "enabled": True,
    }]

    evaluate_automod_rules(
        rules=rules, content="msg 1", guild_id=1, channel_id=10, user_id=100,
        timestamp=100.0, spam_tracker=tracker
    )
    evaluate_automod_rules(
        rules=rules, content="msg 2", guild_id=1, channel_id=10, user_id=100,
        timestamp=101.0, spam_tracker=tracker
    )
    res3 = evaluate_automod_rules(
        rules=rules, content="msg 3", guild_id=1, channel_id=10, user_id=100,
        timestamp=102.0, spam_tracker=tracker
    )

    assert res3 is not None
    assert res3["matched"] is True
    assert res3["rule"] == "message_spam"
    assert res3["action"] == "delete_timeout"
    assert res3["timeout_duration"] == 300
    assert res3["count"] == 3


# ─── 3. messages outside window ────────────────────────────────────────────────

def test_messages_outside_window():
    tracker = SpamTracker()
    rules = [{
        "rule_type": "message_spam",
        "threshold": 3,
        "time_window": 5,
        "enabled": True,
    }]

    # Messages at t=0, t=2
    evaluate_automod_rules(
        rules=rules, content="msg 1", guild_id=1, channel_id=10, user_id=100,
        timestamp=0.0, spam_tracker=tracker
    )
    evaluate_automod_rules(
        rules=rules, content="msg 2", guild_id=1, channel_id=10, user_id=100,
        timestamp=2.0, spam_tracker=tracker
    )

    # Message at t=8 (window is 5s, cutoff is 8-5=3s, previous msgs expired)
    res3 = evaluate_automod_rules(
        rules=rules, content="msg 3", guild_id=1, channel_id=10, user_id=100,
        timestamp=8.0, spam_tracker=tracker
    )
    assert res3 is None
    assert tracker.check_count(1, 10, 100, timestamp=8.0, window_seconds=5) == 1


# ─── 4. different users do not share counts ────────────────────────────────────

def test_different_users_do_not_share_counts():
    tracker = SpamTracker()
    rules = [{
        "rule_type": "message_spam",
        "threshold": 3,
        "time_window": 10,
        "enabled": True,
    }]

    # User A sends 2 messages
    evaluate_automod_rules(rules=rules, content="A1", guild_id=1, channel_id=10, user_id=101, timestamp=10.0, spam_tracker=tracker)
    evaluate_automod_rules(rules=rules, content="A2", guild_id=1, channel_id=10, user_id=101, timestamp=11.0, spam_tracker=tracker)

    # User B sends 2 messages
    evaluate_automod_rules(rules=rules, content="B1", guild_id=1, channel_id=10, user_id=102, timestamp=12.0, spam_tracker=tracker)
    evaluate_automod_rules(rules=rules, content="B2", guild_id=1, channel_id=10, user_id=102, timestamp=13.0, spam_tracker=tracker)

    assert tracker.check_count(1, 10, 101, 13.0, 10) == 2
    assert tracker.check_count(1, 10, 102, 13.0, 10) == 2

    # User A sends 3rd message -> triggers only for User A
    resA = evaluate_automod_rules(rules=rules, content="A3", guild_id=1, channel_id=10, user_id=101, timestamp=14.0, spam_tracker=tracker)
    assert resA is not None
    assert resA["count"] == 3

    # User B still has only 2 messages
    assert tracker.check_count(1, 10, 102, 14.0, 10) == 2


# ─── 5. different channels behave according to configured scope ────────────────

def test_different_channels_behave_according_to_scope():
    tracker = SpamTracker()
    # Rule scoped only to channel 999
    scoped_rules = [{
        "rule_type": "message_spam",
        "threshold": 3,
        "time_window": 10,
        "scope": "channels",
        "channels": [999],
        "enabled": True,
    }]

    # User sends 3 messages in channel 888 (out of scope)
    for i in range(3):
        res = evaluate_automod_rules(
            rules=scoped_rules, content=f"msg {i}", guild_id=1, channel_id=888, user_id=100,
            timestamp=10.0 + i, spam_tracker=tracker
        )
        assert res is None

    # User sends 3 messages in channel 999 (in scope)
    res_in_scope = None
    for i in range(3):
        res_in_scope = evaluate_automod_rules(
            rules=scoped_rules, content=f"msg {i}", guild_id=1, channel_id=999, user_id=100,
            timestamp=20.0 + i, spam_tracker=tracker
        )
    assert res_in_scope is not None
    assert res_in_scope["matched"] is True


# ─── 6. exempt user bypass ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exempt_user_bypass():
    engine = ModerationEngine(bot=MagicMock(), guild_id=123)
    engine._cache_valid = True
    engine._automod_rules_cache = [{
        "rule_type": "message_spam",
        "name": "Message Spam",
        "threshold": 3,
        "time_window": 10,
        "action": "delete_warn",
        "enabled": True,
    }]

    # Mock author as exempt user
    mock_guild = MagicMock(id=123)
    mock_member = MagicMock(spec=discord.Member)
    mock_member.id = 999
    mock_member.guild = mock_guild
    mock_member.bot = False
    mock_member.roles = []
    mock_member.guild_permissions.administrator = False

    # Mark user 999 as exempt in engine
    engine._is_exempt = MagicMock(return_value=True)

    mock_msg = MagicMock(spec=discord.Message)
    mock_msg.guild = mock_guild
    mock_msg.channel = MagicMock(id=456)
    mock_msg.author = mock_member
    mock_msg.content = "rapid spam"
    mock_msg.mentions = []
    mock_msg.role_mentions = []
    mock_msg.mention_everyone = False
    mock_msg.attachments = []
    mock_msg.created_at = datetime.utcnow()

    # Sending 5 messages should never trigger violation
    for _ in range(5):
        violation = await engine.process_message(mock_msg)
        assert violation is None


# ─── 7. exempt role bypass ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exempt_role_bypass():
    engine = ModerationEngine(bot=MagicMock(), guild_id=123)
    engine._cache_valid = True
    engine._automod_rules_cache = [{
        "rule_type": "message_spam",
        "name": "Message Spam",
        "threshold": 2,
        "time_window": 10,
        "action": "delete_timeout",
        "enabled": True,
    }]
    engine._server_config_cache = {"moderator_role_ids": [555]}

    mock_guild = MagicMock(id=123)
    mock_role = MagicMock(id=555)
    mock_member = MagicMock(spec=discord.Member)
    mock_member.id = 888
    mock_member.guild = mock_guild
    mock_member.bot = False
    mock_member.roles = [mock_role]
    mock_member.guild_permissions.administrator = False

    mock_msg = MagicMock(spec=discord.Message)
    mock_msg.guild = mock_guild
    mock_msg.channel = MagicMock(id=456)
    mock_msg.author = mock_member
    mock_msg.content = "spam"
    mock_msg.mentions = []
    mock_msg.role_mentions = []
    mock_msg.mention_everyone = False
    mock_msg.attachments = []
    mock_msg.created_at = datetime.utcnow()

    for _ in range(4):
        violation = await engine.process_message(mock_msg)
        assert violation is None


# ─── 8. bot bypass ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bot_bypass():
    engine = ModerationEngine(bot=MagicMock(), guild_id=123)
    engine._cache_valid = True
    engine._automod_rules_cache = [{
        "rule_type": "message_spam",
        "threshold": 2,
        "time_window": 10,
        "enabled": True,
    }]

    mock_guild = MagicMock(id=123)
    mock_bot = MagicMock(spec=discord.Member)
    mock_bot.bot = True

    mock_msg = MagicMock(spec=discord.Message)
    mock_msg.guild = mock_guild
    mock_msg.author = mock_bot

    violation = await engine.process_message(mock_msg)
    assert violation is None


# ─── 9. delete action ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_action():
    engine = ModerationEngine(bot=MagicMock(), guild_id=123)
    engine._server_config_cache = {"mod_log_channel_id": None}

    mock_msg = MagicMock(spec=discord.Message)
    mock_msg.id = 12345
    mock_msg.channel = MagicMock(id=456, name="general")
    mock_msg.guild = MagicMock(id=123)
    mock_msg.author = MagicMock(id=789, bot=False)
    mock_msg.delete = AsyncMock()

    violation = {
        "rule": "message_spam",
        "action": "delete",
        "reason": "Excessive messages",
        "severity": "low",
    }

    with patch("app.moderation.engine.get_session_direct") as mock_session_ctx, \
         patch("app.moderation.engine.ModerationCaseRepo.create", new_callable=AsyncMock):
        mock_sess = AsyncMock()
        mock_session_ctx.return_value = mock_sess
        await engine.handle_violation(mock_msg, violation)

    mock_msg.delete.assert_awaited_once()


# ─── 10. timeout action ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_action():
    engine = ModerationEngine(bot=MagicMock(), guild_id=123)
    engine._server_config_cache = {"mod_log_channel_id": None}

    # Setup role hierarchy: bot role position 10, target role position 2
    bot_member = MagicMock(spec=discord.Member)
    bot_member.id = 1
    bot_member.top_role.position = 10
    bot_member.guild_permissions.moderate_members = True
    bot_member.guild_permissions.manage_messages = True

    target_member = MagicMock(spec=discord.Member)
    target_member.id = 2
    target_member.top_role.position = 2
    target_member.timeout = AsyncMock()

    mock_guild = MagicMock(id=123, owner_id=9999, me=bot_member)
    mock_msg = MagicMock(spec=discord.Message)
    mock_msg.id = 54321
    mock_msg.channel = MagicMock(id=456, name="general")
    mock_msg.channel.send = AsyncMock()
    mock_msg.guild = mock_guild
    mock_msg.author = target_member
    mock_msg.delete = AsyncMock()

    violation = {
        "rule": "message_spam",
        "action": "delete_timeout",
        "timeout_duration": 300,
        "reason": "Rapid spam",
        "severity": "medium",
    }

    with patch("app.moderation.engine.get_session_direct") as mock_session_ctx, \
         patch("app.moderation.engine.ModerationCaseRepo.create", new_callable=AsyncMock):
        mock_sess = AsyncMock()
        mock_session_ctx.return_value = mock_sess
        await engine.handle_violation(mock_msg, violation)

    mock_msg.delete.assert_awaited_once()
    target_member.timeout.assert_awaited_once()


# ─── 11. delete+timeout when timeout permission fails ─────────────────────────

@pytest.mark.asyncio
async def test_delete_and_timeout_when_timeout_fails():
    engine = ModerationEngine(bot=MagicMock(), guild_id=123)
    engine._server_config_cache = {"mod_log_channel_id": None}

    # Hierarchy failure: target role position 10 >= bot role position 5
    bot_member = MagicMock(spec=discord.Member)
    bot_member.id = 1
    bot_member.top_role.position = 5
    bot_member.guild_permissions.moderate_members = True

    target_member = MagicMock(spec=discord.Member)
    target_member.id = 2
    target_member.top_role.position = 10
    target_member.timeout = AsyncMock()

    mock_guild = MagicMock(id=123, owner_id=9999, me=bot_member)
    mock_msg = MagicMock(spec=discord.Message)
    mock_msg.id = 88888
    mock_msg.channel = MagicMock(id=456, name="general")
    mock_msg.channel.send = AsyncMock()
    mock_msg.guild = mock_guild
    mock_msg.author = target_member
    mock_msg.delete = AsyncMock()


    violation = {
        "rule": "message_spam",
        "action": "delete_timeout",
        "timeout_duration": 600,
        "reason": "Rapid spam",
        "severity": "high",
    }

    recorded_case = {}
    async def mock_case_create(session, **kwargs):
        recorded_case.update(kwargs)
        return MagicMock()

    with patch("app.moderation.engine.get_session_direct") as mock_session_ctx, \
         patch("app.moderation.engine.ModerationCaseRepo.create", side_effect=mock_case_create):
        mock_sess = AsyncMock()
        mock_session_ctx.return_value = mock_sess
        await engine.handle_violation(mock_msg, violation)

    # Deletion MUST still succeed
    mock_msg.delete.assert_awaited_once()
    # Timeout MUST NOT be called because hierarchy check failed
    target_member.timeout.assert_not_called()
    # Recorded case reason MUST record the hierarchy/permission failure
    assert "PERMISSION ERROR" in recorded_case.get("reason", "")


# ─── 12. gateway reconnect does not duplicate handlers ────────────────────────

@pytest.mark.asyncio
async def test_gateway_reconnect_does_not_duplicate_handlers():
    bot = PBHeroBot()
    bot.change_presence = AsyncMock()
    bot.get_guild = MagicMock(return_value=MagicMock(name="PB HERO GAMER", id=1102250942021238854))

    # First ready: initializes scheduler and engine
    with patch("app.youtube.scheduler.YouTubeScheduler.start", new_callable=AsyncMock) as mock_yt_start, \
         patch("app.moderation.engine.ModerationEngine.refresh_cache", new_callable=AsyncMock) as mock_cache:
        await bot.on_ready()
        assert bot._ready_initialized is True
        assert mock_yt_start.await_count == 1
        assert mock_cache.await_count == 1

        first_scheduler = bot.youtube_scheduler
        first_engine = bot.moderation_engine

        # Second ready (simulating reconnect): must NOT re-create scheduler or duplicate cogs
        await bot.on_ready()
        assert bot.youtube_scheduler is first_scheduler
        assert bot.moderation_engine is first_engine
        assert mock_yt_start.await_count == 1  # Still 1, not restarted


# ─── 13. message_content intent check ─────────────────────────────────────────

def test_message_content_intent_check():
    bot = PBHeroBot()
    assert bot.intents.message_content is True
    assert bot.intents.messages is True
    assert bot.intents.guilds is True
    assert bot.intents.members is True
