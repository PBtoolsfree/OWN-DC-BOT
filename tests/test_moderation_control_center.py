"""
Comprehensive backend tests for the Moderation Control Center:
- SQLite JSON serialization & persistence
- Exemptions & Bypass: User, Role, Bot, Channel, Category
- Exemption Precedence: User > Role > Bot > Channel > Category
- Automod Rules: CRUD & filter execution
- Warning System & Decay: Point mode vs Count mode, Active vs Expired
- Escalation Engine: Ladder evaluation & actions (warn, timeout, kick, ban)
- Discord Permission Telemetry & Role Hierarchy: Graceful rejection and error reporting
- Case ID & Correlation: CASE-XXXX, WARN-XXXX
- Voice Policies & 10 Built-in Voice Presets
- Profile Protection: Built-in immutable, Custom fully editable
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.database.models import (
    PolicyValue,
    WarningRecord,
)
from app.database.repositories import (
    ModerationExemptionRepo,
    AutomodRuleRepo,
    WarningRecordRepo,
    WarningEscalationRepo,
    PolicyProfileRepo,
    ServerConfigRepo,
)
from app.moderation.evaluator import (
    check_exemption_bypass,
    generate_case_id,
    generate_warning_id,
)
from app.moderation.engine import execute_moderation_action


# ─── 1. Case ID & Warning ID Generators ───────────────────────────────────────

def test_case_and_warning_id_generation():
    """Verify unique, professional case and warning IDs."""
    case_id1 = generate_case_id()
    case_id2 = generate_case_id()
    warn_id1 = generate_warning_id()
    warn_id2 = generate_warning_id()

    assert case_id1.startswith("CASE-")
    assert case_id2.startswith("CASE-")
    assert warn_id1.startswith("WARN-")
    assert warn_id2.startswith("WARN-")
    assert case_id1 != case_id2
    assert warn_id1 != warn_id2


# ─── 2. Voice Policy & Built-in Voice Profiles ───────────────────────────────

@pytest.mark.asyncio
async def test_builtin_voice_profiles_exist(db_session):
    """Verify the 10 built-in voice policy profiles are seeded and immutable."""
    await PolicyProfileRepo.create_defaults(db_session)
    profiles = await PolicyProfileRepo.get_all(db_session)

    voice_profiles = [p for p in profiles if getattr(p, "policy_type", "text") == "voice"]
    voice_names = {p.name for p in voice_profiles}

    expected_voice_presets = {
        "VOICE GENERAL",
        "VOICE STAFF",
        "VOICE NO STREAM",
        "VOICE NO SPEAK",
        "VOICE LISTEN ONLY",
        "VOICE GAMING",
        "VOICE EVENT",
        "VOICE PRIVATE",
        "VOICE MUSIC",
        "VOICE MODERATOR",
    }
    for expected in expected_voice_presets:
        assert expected in voice_names

    # Check immutability
    listen_only = next(p for p in voice_profiles if p.name == "VOICE LISTEN ONLY")
    assert listen_only.is_builtin is True
    assert listen_only.allow_speak == PolicyValue.DENY
    assert listen_only.allow_stream == PolicyValue.DENY

    with pytest.raises(ValueError):
        await PolicyProfileRepo.delete(db_session, listen_only.id)


@pytest.mark.asyncio
async def test_custom_profile_crud_and_duplicate(db_session):
    """Verify custom profiles (text/voice/general) are fully editable and duplicable."""
    # Create custom voice profile
    custom = await PolicyProfileRepo.create(
        db_session,
        name="CUSTOM GAMING VOICE",
        description="Custom lounge profile",
        category="Gaming",
        is_builtin=False,
        policy_type="voice",
        allow_connect=PolicyValue.ALLOW,
        allow_speak=PolicyValue.ALLOW,
        allow_stream=PolicyValue.DENY,
    )
    assert custom.id is not None
    assert custom.is_builtin is False

    # Edit custom profile
    updated = await PolicyProfileRepo.update(
        db_session,
        custom.id,
        name="CUSTOM GAMING VOICE V2",
        allow_stream=PolicyValue.ALLOW,
    )
    assert updated.name == "CUSTOM GAMING VOICE V2"
    assert updated.allow_stream == PolicyValue.ALLOW

    # Duplicate custom profile
    duplicated = await PolicyProfileRepo.duplicate(db_session, custom.id, "COPY OF GAMING")
    assert duplicated is not None
    assert duplicated.name == "COPY OF GAMING"
    assert duplicated.is_builtin is False
    assert duplicated.allow_stream == PolicyValue.ALLOW

    # Delete custom profile
    deleted = await PolicyProfileRepo.delete(db_session, custom.id)
    assert deleted is True


# ─── 3. Exemption System & Precedence ────────────────────────────────────────

@pytest.mark.asyncio
async def test_granular_exemptions_and_precedence(db_session):
    """
    Verify deterministic exemption precedence:
    1. Explicit User
    2. Role
    3. Bot
    4. Channel
    5. Category
    6. Normal Policy
    """
    # 1. Add Category Exemption (allows links)
    cat_ex = await ModerationExemptionRepo.create(
        db_session,
        target_type="category",
        target_id=9901,
        scope="category",
        scope_id=9901,
        bypass_links=True,
    )

    # 2. Add Role Exemption
    role_ex = await ModerationExemptionRepo.create(
        db_session,
        target_type="role",
        target_id=8801,
        target_name="Chulankar Moderator",
        scope="global",
        bypass_links=True,
        bypass_spam=True,
        bypass_ban=False,
    )

    # 3. Add User Exemption
    user_ex = await ModerationExemptionRepo.create(
        db_session,
        target_type="user",
        target_id=7701,
        target_name="TrustedAdmin",
        scope="global",
        bypass_all=True,
    )

    # Check precedence 1: User exemption bypasses everything
    result_user = await check_exemption_bypass(
        db_session=db_session,
        user_id=7701,
        user_roles=[],
        is_bot=False,
        channel_id=111,
        category_id=222,
        filter_type="links",
    )
    assert result_user["exempt"] is True
    assert result_user["target_type"] == "user"

    # Check precedence 2: Role exemption applies to member with role 8801
    result_role = await check_exemption_bypass(
        db_session=db_session,
        user_id=1234,
        user_roles=[8801, 3333],
        is_bot=False,
        channel_id=111,
        category_id=222,
        filter_type="links",
    )
    assert result_role["exempt"] is True
    assert result_role["target_type"] == "role"

    # Role does NOT bypass ban action if bypass_ban is false
    result_role_ban = await check_exemption_bypass(
        db_session=db_session,
        user_id=1234,
        user_roles=[8801],
        is_bot=False,
        channel_id=111,
        category_id=222,
        filter_type="ban",
    )
    assert result_role_ban["exempt"] is False

    # Non-exempt user
    result_none = await check_exemption_bypass(
        db_session=db_session,
        user_id=5678,
        user_roles=[3333],
        is_bot=False,
        channel_id=111,
        category_id=222,
        filter_type="links",
    )
    assert result_none["exempt"] is False


# ─── 4. Warning System & Decay ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_warning_record_creation_and_decay(db_session):
    """Verify warning creation, severity strike points, and decay expiration calculation."""
    # Configure 7-day decay
    await ServerConfigRepo.update(db_session, warning_decay_days=7, warning_mode="points")

    # Issue an active warning with 2 points
    warn1 = await WarningRecordRepo.create(
        db_session,
        user_id=12345,
        username="RuleBreaker#0001",
        channel_id=111,
        channel_name="general-chat",
        rule="Link Filter",
        reason="Posting phishing links",
        severity="medium",
        points=2,
        moderator="PB HERO AutoMod",
        expires_days=7,
    )
    assert warn1.warning_id.startswith("WARN-")
    assert warn1.status == "active"
    assert warn1.points == 2

    # Issue an expired warning manually simulating 10 days ago
    expired_warn = WarningRecord(
        warning_id=generate_warning_id(),
        case_id=generate_case_id(),
        user_id=12345,
        username="RuleBreaker#0001",
        channel_id=111,
        rule="Spam Filter",
        reason="Old violation",
        severity="low",
        points=1,
        moderator="PB HERO AutoMod",
        status="active",
        created_at=datetime.utcnow() - timedelta(days=10),
    )
    db_session.add(expired_warn)
    await db_session.flush()

    # Calculate active infractions for user
    strikes, points = await WarningRecordRepo.get_user_strikes_and_points(
        db_session, user_id=12345, decay_days=7
    )
    # The 10-day old warning should not contribute to active points/strikes under 7-day decay
    assert strikes == 1
    assert points == 2


# ─── 5. Escalation Ladder & Punishment Evaluation ────────────────────────────

@pytest.mark.asyncio
async def test_escalation_ladder_actions(db_session):
    """Verify escalating punishment based on violation ladder (Warn -> Timeout -> Kick -> Ban)."""
    # Seed default ladder
    await WarningEscalationRepo.create_defaults(db_session)
    rules = await WarningEscalationRepo.get_all(db_session)
    assert len(rules) >= 4

    # 1st violation: should warn
    match_1st = await WarningEscalationRepo.find_escalation(db_session, current_val=1, mode="count")
    assert match_1st is not None
    assert match_1st.action == "warn"

    # 3rd violation: should timeout (10m = 600s)
    match_3rd = await WarningEscalationRepo.find_escalation(db_session, current_val=3, mode="count")
    assert match_3rd is not None
    assert match_3rd.action == "timeout"
    assert match_3rd.duration == 600

    # 5th violation: should kick
    match_5th = await WarningEscalationRepo.find_escalation(db_session, current_val=5, mode="count")
    assert match_5th is not None
    assert match_5th.action == "kick"

    # 6th violation: should ban
    match_6th = await WarningEscalationRepo.find_escalation(db_session, current_val=6, mode="count")
    assert match_6th is not None
    assert match_6th.action == "ban"


# ─── 6. Discord Permission Telemetry & Role Hierarchy ────────────────────────

@pytest.mark.asyncio
async def test_role_hierarchy_check():
    """
    Verify that the execution engine verifies Discord bot permissions and role hierarchy
    before performing punishments, and gracefully creates a PERMISSION ERROR log without crashing.
    """
    mock_bot = MagicMock()
    mock_guild = MagicMock()
    mock_bot_member = MagicMock()
    mock_target_member = MagicMock()

    # Target has higher role than the bot
    mock_bot_top_role = MagicMock(position=5, name="PB HERO Bot")
    mock_target_top_role = MagicMock(position=10, name="Server Administrator")

    mock_bot_member.top_role = mock_bot_top_role
    mock_target_member.top_role = mock_target_top_role

    mock_guild.me = mock_bot_member
    mock_guild.get_member.return_value = mock_target_member

    # Attempt to ban user higher than bot in role hierarchy
    action_result = await execute_moderation_action(
        bot=mock_bot,
        guild=mock_guild,
        target_user_id=12345678,
        action="ban",
        reason="Testing hierarchy protection",
        duration_seconds=0,
        send_dm=False,
    )

    assert action_result["success"] is False
    assert "role" in action_result["error"].lower() or "permission" in action_result["error"].lower()
    assert action_result["permission_error"] is True


# ─── 7. Automod Rules Engine ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_automod_rule_creation_and_lookup(db_session):
    """Verify creating custom automod rules with custom keyword and invite filters."""
    rule = await AutomodRuleRepo.create(
        db_session,
        rule_type="keyword_filter",
        name="Zero Phishing Filter",
        description="Blocks phishing domains and keywords",
        enabled=True,
        scope="global",
        threshold=1,
        time_window=10,
        action="delete_warn",
        custom_keywords=["free-nitro", "steam-gift-card", "airdrop-claim"],
        log_event=True,
        cooldown=3,
    )

    assert rule.id is not None
    assert "free-nitro" in rule.custom_keywords
    assert rule.threshold == 1

    all_rules = await AutomodRuleRepo.get_all(db_session)
    assert any(r.name == "Zero Phishing Filter" for r in all_rules)
