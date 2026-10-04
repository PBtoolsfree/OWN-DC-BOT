"""
PB HERO Centralized Moderation Styles & Presets.

Defines built-in moderation styles (Light, Balanced, Strict),
custom moderation style validation, ladder step formatting,
preview generation, and atomic style application transactions.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import WarningEscalationRule
from app.database.repositories import (
    AuditLogRepo,
    CustomModerationStyleRepo,
    ServerConfigRepo,
    WarningEscalationRepo,
)

logger = logging.getLogger("pbhero.moderation.styles")

# ─── Built-in Preset Definitions (TASK 2) ────────────────────────────────────

BUILTIN_MODERATION_STYLES: Dict[str, Dict[str, Any]] = {
    "light": {
        "id": "light",
        "name": "Light",
        "description": "Friendly community moderation.",
        "explanation": "More forgiving. Good for friendly communities.",
        "warning_decay_days": 14,
        "allow_warning_expiration": True,
        "warning_mode": "count",
        "is_builtin": True,
        "actions_summary": [
            "1 violation → WARN + DM",
            "2 violations → WARN + DM",
            "3 violations → TIMEOUT 10 minutes + DM",
            "4 violations → TIMEOUT 1 hour + DM",
            "5 violations → KICK + DM",
        ],
        "ladder": [
            {
                "threshold": 1,
                "mode": "count",
                "action": "warn",
                "duration": None,
                "send_dm": True,
                "reason_template": "First warning: message policy violation",
            },
            {
                "threshold": 2,
                "mode": "count",
                "action": "warn",
                "duration": None,
                "send_dm": True,
                "reason_template": "Second warning: repeated policy violation",
            },
            {
                "threshold": 3,
                "mode": "count",
                "action": "timeout",
                "duration": 600,
                "send_dm": True,
                "reason_template": "Third violation: 10 minute timeout",
            },
            {
                "threshold": 4,
                "mode": "count",
                "action": "timeout",
                "duration": 3600,
                "send_dm": True,
                "reason_template": "Fourth violation: 1 hour timeout",
            },
            {
                "threshold": 5,
                "mode": "count",
                "action": "kick",
                "duration": None,
                "send_dm": True,
                "reason_template": "Fifth violation: removed from server",
            },
        ],
    },
    "balanced": {
        "id": "balanced",
        "name": "Balanced (Recommended)",
        "description": "Recommended protection for normal gaming/community servers.",
        "explanation": "Recommended balance between protection and user experience.",
        "warning_decay_days": 30,
        "allow_warning_expiration": True,
        "warning_mode": "count",
        "is_builtin": True,
        "actions_summary": [
            "1 violation → WARN + DM",
            "2 violations → WARN + DM",
            "3 violations → TIMEOUT 10 minutes + DM",
            "4 violations → TIMEOUT 1 hour + DM",
            "5 violations → KICK + DM",
            "10 violations → BAN + DM",
        ],
        "ladder": [
            {
                "threshold": 1,
                "mode": "count",
                "action": "warn",
                "duration": None,
                "send_dm": True,
                "reason_template": "First warning: message policy violation",
            },
            {
                "threshold": 2,
                "mode": "count",
                "action": "warn",
                "duration": None,
                "send_dm": True,
                "reason_template": "Second warning: repeated policy violation",
            },
            {
                "threshold": 3,
                "mode": "count",
                "action": "timeout",
                "duration": 600,
                "send_dm": True,
                "reason_template": "Third violation: 10 minute timeout",
            },
            {
                "threshold": 4,
                "mode": "count",
                "action": "timeout",
                "duration": 3600,
                "send_dm": True,
                "reason_template": "Fourth violation: 1 hour timeout",
            },
            {
                "threshold": 5,
                "mode": "count",
                "action": "kick",
                "duration": None,
                "send_dm": True,
                "reason_template": "Fifth violation: removed from server",
            },
            {
                "threshold": 10,
                "mode": "count",
                "action": "ban",
                "duration": None,
                "send_dm": True,
                "delete_message_history_days": 1,
                "reason_template": "Tenth violation: permanently banned for repeated infractions",
            },
        ],
    },
    "strict": {
        "id": "strict",
        "name": "Strict",
        "description": "Strong moderation for high-spam/high-risk communities.",
        "explanation": "Faster escalation for spam and repeated violations.",
        "warning_decay_days": 60,
        "allow_warning_expiration": True,
        "warning_mode": "count",
        "is_builtin": True,
        "actions_summary": [
            "1 violation → WARN + DM",
            "2 violations → TIMEOUT 10 minutes + DM",
            "3 violations → TIMEOUT 1 hour + DM",
            "4 violations → KICK + DM",
            "5 violations → BAN + DM",
        ],
        "ladder": [
            {
                "threshold": 1,
                "mode": "count",
                "action": "warn",
                "duration": None,
                "send_dm": True,
                "reason_template": "First warning: strict policy violation",
            },
            {
                "threshold": 2,
                "mode": "count",
                "action": "timeout",
                "duration": 600,
                "send_dm": True,
                "reason_template": "Second violation: 10 minute timeout",
            },
            {
                "threshold": 3,
                "mode": "count",
                "action": "timeout",
                "duration": 3600,
                "send_dm": True,
                "reason_template": "Third violation: 1 hour timeout",
            },
            {
                "threshold": 4,
                "mode": "count",
                "action": "kick",
                "duration": None,
                "send_dm": True,
                "reason_template": "Fourth violation: removed from server",
            },
            {
                "threshold": 5,
                "mode": "count",
                "action": "ban",
                "duration": None,
                "send_dm": True,
                "delete_message_history_days": 1,
                "reason_template": "Fifth violation: permanently banned under strict policy",
            },
        ],
    },
}


# ─── Formatting & Validation Helpers ─────────────────────────────────────────

def format_ladder_step_summary(step: Dict[str, Any]) -> str:
    """Format a single escalation ladder step into human-readable text."""
    threshold = step.get("threshold", 1)
    action = str(step.get("action", "warn")).upper()
    duration = step.get("duration")
    send_dm = step.get("send_dm", True)

    unit = "violation" if threshold == 1 else "violations"
    action_str = action
    if action == "TIMEOUT" and duration:
        mins = duration // 60
        if mins >= 60:
            hrs = mins // 60
            action_str = f"TIMEOUT {hrs} hour{'s' if hrs > 1 else ''}"
        else:
            action_str = f"TIMEOUT {mins} minute{'s' if mins > 1 else ''}"

    dm_str = " + DM" if send_dm else ""
    return f"{threshold} {unit} → {action_str}{dm_str}"


def validate_custom_style(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate a custom moderation style configuration before saving.

    Requirements:
    - Name must be non-empty, max 128 chars, and cannot collide with built-in names
    - Warning decay between 1 and 365 days when warning expiration is enabled
    - Thresholds must be positive integers (> 0)
    - Thresholds must be strictly increasing (no duplicate thresholds)
    - Thresholds must not exceed 100
    - At least one step required
    - Valid actions: warn, timeout, kick, ban
    - For timeout action: duration must be > 0
    """
    name = str(data.get("name", "")).strip()
    if not name:
        return False, "Style name is required."
    if len(name) > 128:
        return False, "Style name cannot exceed 128 characters."

    if name.lower() in ("light", "balanced", "strict"):
        return False, f"'{name}' is a protected built-in style name. Please choose a different name."

    allow_expiration = bool(data.get("allow_warning_expiration", True))
    decay_days = data.get("warning_decay_days", 30)
    try:
        decay_days = int(decay_days)
    except (ValueError, TypeError):
        return False, "Warning decay days must be an integer."

    if allow_expiration:
        if decay_days < 1 or decay_days > 365:
            return False, "Warning decay must be between 1 and 365 days when warning expiration is enabled."

    ladder = data.get("ladder")
    if not ladder or not isinstance(ladder, list):
        return False, "At least one escalation step is required."

    if len(ladder) == 0:
        return False, "At least one escalation step is required."

    last_threshold = 0
    for idx, step in enumerate(ladder, start=1):
        if not isinstance(step, dict):
            return False, f"Step {idx} has an invalid configuration format."

        raw_threshold = step.get("threshold")
        try:
            threshold = int(raw_threshold)
        except (ValueError, TypeError):
            return False, f"Step {idx}: Threshold must be a positive integer."

        if threshold <= 0:
            return False, f"Step {idx}: Threshold must be greater than 0."

        if threshold > 100:
            return False, f"Step {idx}: Threshold cannot exceed 100 violations."

        if threshold <= last_threshold:
            if threshold == last_threshold:
                return False, f"Duplicate escalation threshold ({threshold} violations). Thresholds must be strictly increasing."
            return False, f"Step {idx}: Threshold ({threshold}) must be greater than preceding threshold ({last_threshold})."

        last_threshold = threshold

        action = str(step.get("action", "")).lower()
        if action not in ("warn", "timeout", "kick", "ban"):
            return False, f"Step {idx}: Invalid action '{action}'. Must be WARN, TIMEOUT, KICK, or BAN."

        if action == "timeout":
            raw_duration = step.get("duration")
            try:
                duration = int(raw_duration) if raw_duration is not None else 0
            except (ValueError, TypeError):
                return False, f"Step {idx}: Timeout duration must be a positive integer (in seconds)."

            if duration <= 0:
                return False, f"Step {idx}: Timeout action requires a duration greater than 0."

    return True, None


def generate_style_preview(style_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate preview metadata for a moderation style."""
    name = style_data.get("name", "Custom")
    description = style_data.get("description", "")
    allow_expiration = bool(style_data.get("allow_warning_expiration", True))
    decay_days = int(style_data.get("warning_decay_days", 30)) if allow_expiration else 0
    ladder = style_data.get("ladder", [])

    actions = [format_ladder_step_summary(step) for step in ladder]
    decay_text = f"{decay_days} days" if allow_expiration and decay_days > 0 else "Never (Disabled)"

    return {
        "name": name,
        "description": description,
        "warning_decay_days": decay_days,
        "allow_warning_expiration": allow_expiration,
        "warning_mode": style_data.get("warning_mode", "count"),
        "decay_text": decay_text,
        "actions": actions,
        "ladder_summary": actions,
        "steps_count": len(ladder),
    }


# ─── Atomic Style Application (TASKS 3, 4, 5, 6, 9, 13, 14) ───────────────────

async def apply_moderation_style(
    session: AsyncSession,
    style_identifier: Any,
    username: str = "Admin",
) -> Dict[str, Any]:
    """
    Atomically apply a moderation style (built-in or custom).

    Flow:
    BEGIN TRANSACTION
    1. Load selected style
    2. Validate preset configuration
    3. Update server config warning decay and active style
    4. Replace/update escalation ladder in warning_escalation_rules
    5. Preserve all unrelated settings, moderation history, cases, active warnings
    6. Record audit log entry
    7. Commit transaction
    8. Invalidate and refresh moderation engine cache
    If ANY step fails, ROLLBACK EVERYTHING.
    """
    identifier_str = str(style_identifier).strip().lower()
    style_info: Optional[Dict[str, Any]] = None

    # 1. Load style definition
    if identifier_str in BUILTIN_MODERATION_STYLES:
        style_info = BUILTIN_MODERATION_STYLES[identifier_str]
        style_name = style_info["name"]
    else:
        # Check custom presets by ID or Name
        custom_preset = None
        if identifier_str.isdigit():
            custom_preset = await CustomModerationStyleRepo.get_by_id(session, int(identifier_str))
        if not custom_preset:
            custom_preset = await CustomModerationStyleRepo.get_by_name(session, str(style_identifier).strip())

        if not custom_preset:
            raise ValueError(f"Moderation style '{style_identifier}' not found.")

        style_name = custom_preset.name
        ladder_data = custom_preset.ladder
        if isinstance(ladder_data, str):
            try:
                ladder_data = json.loads(ladder_data)
            except Exception:
                ladder_data = []

        style_info = {
            "id": str(custom_preset.id),
            "name": custom_preset.name,
            "description": custom_preset.description,
            "warning_decay_days": custom_preset.warning_decay_days,
            "allow_warning_expiration": custom_preset.allow_warning_expiration,
            "warning_mode": custom_preset.warning_mode,
            "is_builtin": False,
            "ladder": ladder_data,
        }

    # 2. Validate preset configuration
    ladder = style_info.get("ladder", [])
    if not ladder:
        raise ValueError(f"Moderation style '{style_name}' contains no escalation steps.")

    try:
        # 3. Load Server Config & Capture Previous State for Audit Log
        config = await ServerConfigRepo.get_or_create(session)
        prev_decay = config.warning_decay_days
        prev_style = getattr(config, "quick_setup_style", "balanced")

        # Update Warning Decay (Task 6: default decay for future warnings; existing warnings unaffected)
        allow_expiration = bool(style_info.get("allow_warning_expiration", True))
        target_decay = int(style_info.get("warning_decay_days", 30)) if allow_expiration else 0
        config.warning_decay_days = target_decay
        config.quick_setup_style = style_info.get("id") or style_name
        config.warning_mode = style_info.get("warning_mode", "count")

        # 4. Replace Escalation Ladder (Task 3: atomic replacement)
        await session.execute(delete(WarningEscalationRule))

        for step in ladder:
            action_name = str(step.get("action", "warn")).lower()
            duration = step.get("duration")
            if action_name != "timeout":
                duration = None

            await WarningEscalationRepo.create(
                session=session,
                threshold=int(step["threshold"]),
                mode=str(step.get("mode", config.warning_mode or "count")),
                action=action_name,
                duration=duration,
                send_dm=bool(step.get("send_dm", True)),
                delete_message_history_days=int(step.get("delete_message_history_days", 1 if action_name == "ban" else 0)),
                reason_template=step.get("reason_template") or f"Threshold reached: {action_name.upper()}",
            )

        # 5. Record Audit Log (Task 14)
        audit_payload = {
            "style": style_name,
            "style_id": style_info.get("id"),
            "is_builtin": style_info.get("is_builtin", False),
            "previous_decay_days": prev_decay,
            "new_decay_days": target_decay,
            "previous_style": prev_style,
            "ladder_steps_count": len(ladder),
        }
        await AuditLogRepo.log(
            session=session,
            actor=username,
            action="MODERATION_STYLE_APPLIED",
            details=json.dumps(audit_payload),
        )

        # 6. Commit Database Transaction
        await session.commit()
        logger.info(
            "Moderation style '%s' applied by '%s'. Decay: %dd, Ladder steps: %d",
            style_name,
            username,
            target_decay,
            len(ladder),
        )
    except Exception:
        await session.rollback()
        raise

    # 7. Refresh Moderation Engine Cache (Task 13)
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    if bot and getattr(bot, "moderation_engine", None):
        try:
            await bot.moderation_engine.refresh_cache()
            logger.info("Moderation engine cache refreshed after style application")
        except Exception as e:
            logger.warning("Error refreshing moderation cache after style apply: %s", e)

    return {
        "success": True,
        "style": style_name,
        "style_id": style_info.get("id"),
        "warning_decay_days": target_decay,
        "ladder_steps_updated": len(ladder),
        "message": f"Successfully applied {style_name} moderation style",
    }
