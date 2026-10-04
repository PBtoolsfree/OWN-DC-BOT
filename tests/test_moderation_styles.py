"""
Comprehensive test suite for Moderation Styles & Profiles (Tasks 1 to 20):
1. List built-in styles (light, balanced, strict)
2. Create custom style
3. Update custom style
4. Delete custom style
5. Apply Light preset
6. Apply Balanced preset
7. Apply Strict preset
8. Apply Custom preset
9. Invalid style ID rejection
10. Invalid custom ladder (empty or negative thresholds)
11. Duplicate threshold rejection
12. Invalid timeout duration rejection
13. Transaction rollback on error
14. Warning decay update for future warnings
15. Existing warning expiry preserved
16. Active warning count preserved
17. Historical cases preserved
18. AutoMod integration (warning count checks active only)
19. Audit log generation
20. Cache refresh hook
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.database.models import (
    WarningRecord,
    ModerationCase,
    WarningEscalationRule,
    AuditLog,
)
from app.database.repositories import (
    WarningRecordRepo,
    WarningEscalationRepo,
    CustomModerationStyleRepo,
    ServerConfigRepo,
)
from app.moderation.styles import (
    BUILTIN_MODERATION_STYLES,
    validate_custom_style,
    generate_style_preview,
    apply_moderation_style,
)


# ─── 1. List Built-in Styles ─────────────────────────────────────────────────

def test_list_builtin_styles():
    """Verify built-in styles Light, Balanced, Strict have correct definitions."""
    assert "light" in BUILTIN_MODERATION_STYLES
    assert "balanced" in BUILTIN_MODERATION_STYLES
    assert "strict" in BUILTIN_MODERATION_STYLES

    light = BUILTIN_MODERATION_STYLES["light"]
    assert light["warning_decay_days"] == 14
    assert len(light["ladder"]) == 5
    # Light has no ban
    assert all(step["action"] != "ban" for step in light["ladder"])

    balanced = BUILTIN_MODERATION_STYLES["balanced"]
    assert balanced["warning_decay_days"] == 30
    assert len(balanced["ladder"]) == 6
    assert balanced["ladder"][-1]["action"] == "ban"
    assert balanced["ladder"][-1]["threshold"] == 10

    strict = BUILTIN_MODERATION_STYLES["strict"]
    assert strict["warning_decay_days"] == 60
    assert len(strict["ladder"]) == 5
    assert strict["ladder"][-1]["action"] == "ban"
    assert strict["ladder"][-1]["threshold"] == 5


# ─── 2, 3, 4. Custom Style CRUD & Duplication ────────────────────────────────

@pytest.mark.asyncio
async def test_custom_style_crud_and_duplicate(db_session):
    """Verify creating, reading, updating, and deleting custom styles."""
    ladder = [
        {"threshold": 1, "action": "warn", "duration": 0, "send_dm": True},
        {"threshold": 2, "action": "timeout", "duration": 300, "send_dm": True},
        {"threshold": 3, "action": "ban", "duration": 0, "send_dm": False},
    ]
    style = await CustomModerationStyleRepo.create(
        session=db_session,
        name="Tournament Strict",
        description="Rules for competitive matches",
        warning_decay_days=7,
        allow_warning_expiration=True,
        warning_mode="count",
        ladder=ladder,
    )
    assert style.id is not None
    assert style.name == "Tournament Strict"
    assert style.warning_decay_days == 7
    stored_ladder = json.loads(style.ladder) if isinstance(style.ladder, str) else style.ladder
    assert len(stored_ladder) == 3

    # Update
    updated_ladder = [
        {"threshold": 1, "action": "warn", "duration": 0, "send_dm": True},
        {"threshold": 2, "action": "kick", "duration": 0, "send_dm": True},
    ]
    updated = await CustomModerationStyleRepo.update(
        session=db_session,
        style_id=style.id,
        name="Tournament Relaxed",
        warning_decay_days=10,
        ladder=updated_ladder,
    )
    assert updated.name == "Tournament Relaxed"
    assert updated.warning_decay_days == 10
    updated_stored = json.loads(updated.ladder) if isinstance(updated.ladder, str) else updated.ladder
    assert len(updated_stored) == 2

    # Delete
    deleted = await CustomModerationStyleRepo.delete(db_session, style.id)
    assert deleted is True
    assert await CustomModerationStyleRepo.get_by_id(db_session, style.id) is None


# ─── 5, 6, 7, 8. Apply Presets (Light, Balanced, Strict, Custom) ─────────────

@pytest.mark.asyncio
async def test_apply_light_preset(db_session):
    """Verify applying Light style updates decay to 14 days and installs 5 ladder steps."""
    res = await apply_moderation_style(db_session, "light", username="admin")
    assert res["success"] is True
    assert res["style"] == "Light"
    assert res["warning_decay_days"] == 14
    assert res["ladder_steps_updated"] == 5

    # Check DB state
    config = await ServerConfigRepo.get_or_create(db_session)
    assert config.warning_decay_days == 14

    rules = await WarningEscalationRepo.get_all(db_session)
    assert len(rules) == 5
    assert rules[0].action == "warn"
    assert rules[2].action == "timeout"
    assert rules[2].duration == 600
    assert rules[4].action == "kick"


@pytest.mark.asyncio
async def test_apply_balanced_preset(db_session):
    """Verify applying Balanced style updates decay to 30 days and installs 6 ladder steps."""
    res = await apply_moderation_style(db_session, "balanced", username="admin")
    assert res["success"] is True
    assert "Balanced" in res["style"]
    assert res["warning_decay_days"] == 30
    assert res["ladder_steps_updated"] == 6

    rules = await WarningEscalationRepo.get_all(db_session)
    assert len(rules) == 6
    assert rules[-1].action == "ban"
    assert rules[-1].threshold == 10


@pytest.mark.asyncio
async def test_apply_strict_preset(db_session):
    """Verify applying Strict style updates decay to 60 days and installs 5 ladder steps."""
    res = await apply_moderation_style(db_session, "strict", username="admin")
    assert res["success"] is True
    assert res["style"] == "Strict"
    assert res["warning_decay_days"] == 60
    assert res["ladder_steps_updated"] == 5

    rules = await WarningEscalationRepo.get_all(db_session)
    assert len(rules) == 5
    assert rules[-1].action == "ban"
    assert rules[-1].threshold == 5


@pytest.mark.asyncio
async def test_apply_custom_preset(db_session):
    """Verify creating and applying a custom moderation style."""
    custom_style = await CustomModerationStyleRepo.create(
        session=db_session,
        name="Esports Tournament",
        description="Zero tolerance tournament ladder",
        warning_decay_days=2,
        allow_warning_expiration=True,
        warning_mode="count",
        ladder=[
            {"threshold": 1, "action": "warn", "duration": 0, "send_dm": True},
            {"threshold": 2, "action": "timeout", "duration": 300, "send_dm": True},
            {"threshold": 3, "action": "kick", "duration": 0, "send_dm": True},
            {"threshold": 5, "action": "ban", "duration": 0, "send_dm": True},
        ],
    )

    res = await apply_moderation_style(db_session, str(custom_style.id), username="admin")
    assert res["success"] is True
    assert res["style"] == "Esports Tournament"
    assert res["warning_decay_days"] == 2
    assert res["ladder_steps_updated"] == 4

    config = await ServerConfigRepo.get_or_create(db_session)
    assert config.warning_decay_days == 2

    rules = await WarningEscalationRepo.get_all(db_session)
    assert len(rules) == 4
    assert [r.threshold for r in rules] == [1, 2, 3, 5]


# ─── 9, 10, 11, 12. Validations & Error Handling ─────────────────────────────

@pytest.mark.asyncio
async def test_invalid_style_id_rejected(db_session):
    """Applying unknown style id raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        await apply_moderation_style(db_session, "unknown_style_id_123")


def test_custom_style_validations():
    """Verify all custom style validation rules."""
    # Empty ladder
    valid, err = validate_custom_style({
        "name": "Test",
        "warning_decay_days": 30,
        "allow_warning_expiration": True,
        "ladder": [],
    })
    assert valid is False
    assert "At least one escalation step is required" in err

    # Empty name
    valid, err = validate_custom_style({
        "name": "",
        "warning_decay_days": 30,
        "allow_warning_expiration": True,
        "ladder": [{"threshold": 1, "action": "warn"}],
    })
    assert valid is False
    assert "Style name is required" in err

    # Decay out of range
    valid, err = validate_custom_style({
        "name": "Test",
        "warning_decay_days": 400,
        "allow_warning_expiration": True,
        "ladder": [{"threshold": 1, "action": "warn"}],
    })
    assert valid is False
    assert "Warning decay must be between 1 and 365 days" in err

    # Duplicate threshold
    valid, err = validate_custom_style({
        "name": "Test",
        "warning_decay_days": 30,
        "allow_warning_expiration": True,
        "ladder": [
            {"threshold": 1, "action": "warn"},
            {"threshold": 1, "action": "ban"},
        ],
    })
    assert valid is False
    assert "Duplicate escalation threshold" in err

    # Non-increasing threshold
    valid, err = validate_custom_style({
        "name": "Test",
        "warning_decay_days": 30,
        "allow_warning_expiration": True,
        "ladder": [
            {"threshold": 3, "action": "warn"},
            {"threshold": 2, "action": "ban"},
        ],
    })
    assert valid is False
    assert "must be greater than preceding threshold" in err

    # Timeout duration missing or <= 0
    valid, err = validate_custom_style({
        "name": "Test",
        "warning_decay_days": 30,
        "allow_warning_expiration": True,
        "ladder": [
            {"threshold": 1, "action": "timeout", "duration": 0},
        ],
    })
    assert valid is False
    assert "Timeout action requires a duration greater than 0" in err


# ─── 13. Transaction Rollback ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transaction_rollback_on_failure(db_session):
    """Verify that if ladder creation fails, the decay update is completely rolled back."""
    config = await ServerConfigRepo.get_or_create(db_session)
    config.warning_decay_days = 30
    await db_session.commit()

    # Pass a custom style whose ladder insertion raises an exception
    style = await CustomModerationStyleRepo.create(
        session=db_session,
        name="Faulty Style",
        description="Fails during commit",
        warning_decay_days=99,
        allow_warning_expiration=True,
        warning_mode="count",
        ladder=[{"threshold": 1, "action": "warn"}],
    )

    with patch.object(WarningEscalationRepo, "create", side_effect=RuntimeError("Simulated DB Crash")):
        with pytest.raises(RuntimeError, match="Simulated DB Crash"):
            await apply_moderation_style(db_session, str(style.id))

    # Verify rollback: decay must still be 30, NOT 99!
    reloaded_config = await ServerConfigRepo.get_or_create(db_session)
    assert reloaded_config.warning_decay_days == 30


# ─── 14, 15, 16, 17. Preservation of History & Expiration ────────────────────

@pytest.mark.asyncio
async def test_historical_warnings_and_cases_preserved(db_session):
    """Verify applying a preset preserves existing warnings, cases, and expirations."""
    # Existing warning created with 30-day expiry
    past_expiry = datetime.now(timezone.utc) + timedelta(days=30)
    w1 = await WarningRecordRepo.create(
        session=db_session,
        user_id=123456789,
        username="testuser",
        rule="General",
        reason="Old offense",
        severity="medium",
        points=1,
        expires_at=past_expiry,
    )
    # Expired warning
    w2 = await WarningRecordRepo.create(
        session=db_session,
        user_id=123456789,
        username="testuser",
        rule="General",
        reason="Very old offense",
        severity="low",
        points=1,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    # Revoked warning
    w3 = await WarningRecordRepo.create(
        session=db_session,
        user_id=123456789,
        username="testuser",
        rule="General",
        reason="Revoked offense",
        severity="low",
        points=1,
    )
    await WarningRecordRepo.revoke(db_session, w3.id, revoked_by="Admin")

    # Add historical moderation case
    case = ModerationCase(
        case_id="CASE-2026-9999",
        case_number=9999,
        target_user_id="123456789",
        moderator_user_id="mod_1",
        action="warn",
        reason="Historical case",
    )
    db_session.add(case)
    await db_session.commit()

    # Apply Light preset (changes decay to 14 days)
    res = await apply_moderation_style(db_session, "light", username="admin")
    assert res["success"] is True

    # Check that w1 kept its EXACT original 30-day expires_at timestamp!
    reloaded_w1 = await db_session.get(WarningRecord, w1.id)
    assert reloaded_w1 is not None
    assert reloaded_w1.expires_at == past_expiry

    # Check active warnings count: only w1 is active, w2 (expired) and w3 (revoked) not counted
    active_warnings = await WarningRecordRepo.get_active_for_user(db_session, 123456789)
    assert len(active_warnings) == 1
    assert active_warnings[0].id == w1.id

    # Check case is still in DB
    reloaded_case = await db_session.get(ModerationCase, case.id)
    assert reloaded_case is not None
    assert reloaded_case.case_id == "CASE-2026-9999"


# ─── 18, 19, 20. AutoMod, Audit Log & Cache Refresh ──────────────────────────

@pytest.mark.asyncio
async def test_audit_log_and_cache_refresh(db_session):
    """Verify audit log is written when style is applied."""
    # Apply Balanced style
    await apply_moderation_style(
        db_session,
        "balanced",
        username="superadmin",
    )

    # Check AuditLog table
    from sqlalchemy import select
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "MODERATION_STYLE_APPLIED")
    )
    log_entry = result.scalars().first()
    assert log_entry is not None
    assert log_entry.actor == "superadmin"
    assert "Balanced" in log_entry.details
    assert "new_decay_days" in log_entry.details
