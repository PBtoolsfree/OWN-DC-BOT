"""
Template constants, variable extractors, presets, security validators,
and safe rendering for Server Greetings (Premium Onboarding 2.0).
"""

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

WELCOME_VARIABLES: Set[str] = {
    "username",
    "display_name",
    "user_mention",
    "user_id",
    "server_name",
    "server_id",
    "member_count",
    "account_created",
    "joined_at",
    "rules_url",
    "invite_url",
    "inviter",
    "inviter_mention",
    "inviter_id",
    "invite_code",
    "invite_channel",
    "total_invites",
    "rank",
}

GOODBYE_VARIABLES: Set[str] = {
    "username",
    "display_name",
    "user_mention",
    "user_id",
    "server_name",
    "server_id",
    "member_count",
    "left_at",
    "invite_url",
    "inviter",
}

WELCOME_DM_VARIABLES: Set[str] = {
    "username",
    "display_name",
    "user_mention",
    "user_id",
    "server_name",
    "server_id",
    "member_count",
    "account_created",
    "joined_at",
    "rules_url",
    "invite_url",
    "inviter",
    "inviter_mention",
    "inviter_id",
    "invite_code",
    "invite_channel",
    "total_invites",
    "rank",
}

GOODBYE_DM_VARIABLES: Set[str] = {
    "username",
    "display_name",
    "user_mention",
    "user_id",
    "server_name",
    "server_id",
    "member_count",
    "left_at",
    "joined_at",
    "rules_url",
    "invite_url",
    "inviter",
}

RULES_VARIABLES: Set[str] = {
    "username",
    "display_name",
    "user_mention",
    "user_id",
    "server_name",
    "server_id",
    "member_count",
    "rules_url",
    "invite_url",
}

# ========================================================
# Defaults
# ========================================================

DEFAULT_WELCOME_TITLE = "✨ WELCOME TO {server_name}"
DEFAULT_WELCOME_DESCRIPTION = (
    "Hey {user_mention} 👋\n\n"
    "We're glad to have you here!\n\n"
    "👥 You are member #{member_count}\n\n"
    "🤝 Invited by: {inviter}\n"
    "🔗 Invite: {invite_code}\n\n"
    "📜 Please read the server rules.\n"
    "🎮 Explore the community and enjoy your stay."
)
DEFAULT_WELCOME_FOOTER = "PB HERO SERVER"

DEFAULT_GOODBYE_TITLE = "💙 {display_name} has left {server_name}"
DEFAULT_GOODBYE_DESCRIPTION = (
    "We hope you enjoyed your time with us.\n\n"
    "👥 We are now {member_count} members.\n\n"
    "Take care and you're always welcome back."
)
DEFAULT_GOODBYE_FOOTER = "PB HERO SERVER"

DEFAULT_WELCOME_DM_TITLE = "👋 Welcome to {server_name}, {display_name}!"
DEFAULT_WELCOME_DM_DESCRIPTION = (
    "Thanks for joining our Discord community ❤️\n\n"
    "👥 You are member #{member_count}\n\n"
    "🤝 Invited by: {inviter}\n\n"
    "Before getting started:\n\n"
    "📜 Rules:\n"
    "{rules_url}\n\n"
    "🔗 Permanent Server Invite:\n"
    "{invite_url}\n\n"
    "Enjoy your stay and have fun!"
)
DEFAULT_WELCOME_DM_FOOTER = "PB HERO SERVER"

DEFAULT_GOODBYE_DM_TITLE = "💙 GOODBYE, {display_name}"
DEFAULT_GOODBYE_DM_DESCRIPTION = (
    "You have left {server_name}.\n\n"
    "We appreciate the time you spent with us.\n\n"
    "🔗 Rejoin Server:\n"
    "{invite_url}\n\n"
    "You're always welcome back. ❤️"
)
DEFAULT_GOODBYE_DM_FOOTER = "PB HERO SERVER"

DEFAULT_RULES_TITLE = "📜 {server_name} RULES"
DEFAULT_RULES_DESCRIPTION = (
    "1. Respect all members.\n"
    "2. No spam or unsolicited promotions.\n"
    "3. No offensive or harmful content.\n"
    "4. Follow channel guidelines and moderator instructions.\n\n"
    "Please read the full rules before chatting!"
)
DEFAULT_RULES_FOOTER = "PB HERO SERVER"

DEFAULT_WELCOME_BUTTONS: List[Dict[str, Any]] = [
    {"id": "rules", "label": "Read Rules", "emoji": "📜", "url": "{rules_url}", "enabled": True},
    {"id": "explore", "label": "Explore Server", "emoji": "🎮", "url": "{invite_url}", "enabled": False},
    {"id": "invite", "label": "Server Invite", "emoji": "🔗", "url": "{invite_url}", "enabled": True},
    {"id": "support", "label": "Support", "emoji": "🆘", "url": "https://discord.gg/pbhero", "enabled": False},
]

# ========================================================
# Theme Presets
# ========================================================

THEME_PRESETS: Dict[str, Dict[str, Any]] = {
    "default": {
        "id": "default",
        "name": "Default",
        "welcome_accent_color": "#5865F2",
        "goodbye_accent_color": "#ED4245",
        "welcome_title": "✨ WELCOME TO {server_name}",
        "welcome_description": (
            "Hey {user_mention} 👋\n\n"
            "We're glad to have you here!\n\n"
            "👥 You are member #{member_count}\n\n"
            "🤝 Invited by: {inviter}\n"
            "🔗 Invite: {invite_code}\n\n"
            "📜 Please read the server rules.\n"
            "🎮 Explore the community and enjoy your stay."
        ),
        "goodbye_title": "💙 {display_name} has left {server_name}",
        "goodbye_description": (
            "We hope you enjoyed your time with us.\n\n"
            "👥 We are now {member_count} members.\n\n"
            "Take care and you're always welcome back."
        ),
    },
    "gaming": {
        "id": "gaming",
        "name": "Gaming",
        "welcome_accent_color": "#22C55E",
        "goodbye_accent_color": "#EF4444",
        "welcome_title": "🎮 WELCOME TO {server_name}",
        "welcome_description": (
            "Player {user_mention} has entered the arena! 🚀\n\n"
            "⚔️ Party Member #{member_count}\n"
            "🎯 Recruited by: {inviter}\n"
            "🔗 Portal Key: {invite_code}\n\n"
            "📜 Check our guidelines before queuing up.\n"
            "🕹️ Good luck and have fun!"
        ),
        "goodbye_title": "💀 PLAYER DISCONNECTED: {display_name}",
        "goodbye_description": (
            "{display_name} has left the party.\n\n"
            "👥 Current squad: {member_count} players.\n\n"
            "Respawn anytime — GG!"
        ),
    },
    "minimal": {
        "id": "minimal",
        "name": "Minimal",
        "welcome_accent_color": "#71717A",
        "goodbye_accent_color": "#71717A",
        "welcome_title": "Welcome to {server_name}",
        "welcome_description": (
            "Welcome {user_mention}.\n\n"
            "Member #{member_count} • Invited by {inviter}\n\n"
            "Review the rules and enjoy your stay."
        ),
        "goodbye_title": "Goodbye {display_name}",
        "goodbye_description": (
            "{display_name} has left.\n\n"
            "Current members: {member_count}."
        ),
    },
    "luxury": {
        "id": "luxury",
        "name": "Luxury",
        "welcome_accent_color": "#D97706",
        "goodbye_accent_color": "#B45309",
        "welcome_title": "✨ WELCOME TO {server_name}",
        "welcome_description": (
            "A distinguished welcome to {user_mention} 🥂\n\n"
            "It is our privilege to welcome you as member #{member_count}.\n\n"
            "⚜️ Introduced by: {inviter}\n"
            "🗝️ Registry Code: {invite_code}\n\n"
            "Please observe server etiquette and enjoy your refined stay."
        ),
        "goodbye_title": "✨ FAREWELL, {display_name}",
        "goodbye_description": (
            "{display_name} has departed from {server_name}.\n\n"
            "Our distinguished community now stands at {member_count}.\n\n"
            "Our doors remain open for your return."
        ),
    },
    "neon": {
        "id": "neon",
        "name": "Neon Cyber",
        "welcome_accent_color": "#EC4899",
        "goodbye_accent_color": "#8B5CF6",
        "welcome_title": "⚡ SYSTEM ONLINE • {server_name}",
        "welcome_description": (
            "Neon uplink connected: {user_mention} ⚡\n\n"
            "🌐 Network Node #{member_count}\n"
            "📡 Uplinked by: {inviter}\n"
            "⚡ Frequency: {invite_code}\n\n"
            "Access protocols accepted. Welcome to the grid!"
        ),
        "goodbye_title": "⚡ NODE OFFLINE • {display_name}",
        "goodbye_description": (
            "Node disconnection logged for {display_name}.\n\n"
            "Active network size: {member_count} nodes.\n\n"
            "Reconnection frequency ready."
        ),
    },
}

VARIABLE_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")
DISALLOWED_URL_PREFIXES = ("javascript:", "data:", "file:", "vbscript:", "blob:")


def build_rules_url(guild_id: Optional[int], channel_id: Optional[int]) -> str:
    """Build a direct Discord channel URL to the rules channel."""
    if guild_id and channel_id:
        return f"https://discord.com/channels/{guild_id}/{channel_id}"
    return "[Rules unavailable]"


def extract_variables(text: Optional[str]) -> Set[str]:
    """Extract all variable placeholders in {var_name} format."""
    if not text:
        return set()
    return set(VARIABLE_PATTERN.findall(text))


def validate_variables(text: Optional[str], allowed_vars: Set[str]) -> List[str]:
    """Return a list of unsupported variables in the template."""
    if not text:
        return []
    used = extract_variables(text)
    invalid = [v for v in used if v not in allowed_vars]
    return sorted(invalid)


def is_safe_url(url: Optional[str]) -> bool:
    """Verify that an external URL only uses HTTPS and safe schemes."""
    if not url:
        return False
    clean = url.strip()
    if clean in ("{rules_url}", "{invite_url}"):
        return True
    lower = clean.lower()
    for bad in DISALLOWED_URL_PREFIXES:
        if lower.startswith(bad):
            return False
    if any(c in clean for c in ("\n", "\r", "\t")):
        return False
    return lower.startswith("https://")


def validate_buttons(buttons: Any) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
    """Validate message buttons for Discord limits and URL security."""
    if buttons is None:
        return True, None, []
    if isinstance(buttons, str):
        if not buttons.strip():
            return True, None, []
        try:
            buttons = json.loads(buttons)
        except Exception:
            return False, "Buttons data must be valid JSON", []
    if not isinstance(buttons, list):
        return False, "Buttons must be a list of button objects", []
    if len(buttons) > 5:
        return False, "A maximum of 5 buttons are allowed per Discord action row", []

    cleaned: List[Dict[str, Any]] = []
    for idx, btn in enumerate(buttons):
        if not isinstance(btn, dict):
            return False, f"Button #{idx+1} is invalid", []
        btn_id = str(btn.get("id") or f"btn_{idx}")
        label = str(btn.get("label") or "").strip()
        emoji = str(btn.get("emoji") or "").strip() if btn.get("emoji") else None
        url = str(btn.get("url") or "").strip()
        enabled = bool(btn.get("enabled", True))

        if enabled:
            if not label and not emoji:
                return False, f"Button #{idx+1} must have a label or emoji", []
            if len(label) > 80:
                return False, f"Button label cannot exceed 80 characters (button: '{label[:20]}...')", []
            if url and not is_safe_url(url):
                return False, f"Button '{label or btn_id}' URL must be a valid HTTPS URL", []

        cleaned.append({
            "id": btn_id,
            "label": label,
            "emoji": emoji,
            "url": url,
            "enabled": enabled,
            "style": btn.get("style", "link"),
        })
    return True, None, cleaned


def validate_discord_limits(data: Dict[str, Any]) -> List[str]:
    """
    Validate Discord character limits:
    - title <= 256
    - description <= 4096
    - footer <= 2048
    - author <= 256
    """
    errors: List[str] = []
    field_limits = [
        ("welcome_title", 256, "Welcome Title"),
        ("welcome_description", 4096, "Welcome Description"),
        ("welcome_footer", 2048, "Welcome Footer"),
        ("welcome_author_text", 256, "Welcome Author Text"),
        ("goodbye_title", 256, "Goodbye Title"),
        ("goodbye_description", 4096, "Goodbye Description"),
        ("goodbye_footer", 2048, "Goodbye Footer"),
        ("goodbye_author_text", 256, "Goodbye Author Text"),
        ("welcome_dm_title", 256, "Welcome DM Title"),
        ("welcome_dm_description", 4096, "Welcome DM Description"),
        ("welcome_dm_footer", 2048, "Welcome DM Footer"),
        ("welcome_dm_author_text", 256, "Welcome DM Author Text"),
        ("goodbye_dm_title", 256, "Goodbye DM Title"),
        ("goodbye_dm_description", 4096, "Goodbye DM Description"),
        ("goodbye_dm_footer", 2048, "Goodbye DM Footer"),
        ("goodbye_dm_author_text", 256, "Goodbye DM Author Text"),
        ("rules_title", 256, "Rules Title"),
        ("rules_description", 4096, "Rules Description"),
        ("rules_footer", 2048, "Rules Footer"),
    ]
    for key, limit, name in field_limits:
        val = data.get(key)
        if val and len(str(val)) > limit:
            errors.append(f"{name} exceeds Discord limit of {limit} characters (currently {len(str(val))})")
    return errors


def render_template(
    template: Optional[str],
    context: Dict[str, Any],
    allow_mass_mentions: bool = False,
) -> str:
    """
    Safely render template string with context variables.
    Unknown variables are preserved rather than crashing.
    Special links ({invite_url}, {rules_url}) fallback to safe markers if missing.
    Mass mentions (@everyone, @here) are sanitized unless explicitly permitted.
    """
    if not template:
        return ""

    safe_context = dict(context)
    if not safe_context.get("invite_url"):
        safe_context["invite_url"] = "[Invite unavailable]"
    if not safe_context.get("rules_url"):
        safe_context["rules_url"] = "[Rules unavailable]"
    if not safe_context.get("inviter"):
        safe_context["inviter"] = "Unknown"
    if not safe_context.get("invite_code"):
        safe_context["invite_code"] = "Unknown"
    if not safe_context.get("inviter_mention"):
        safe_context["inviter_mention"] = safe_context["inviter"]

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in safe_context:
            val = safe_context[var_name]
            return str(val) if val is not None else ""
        return match.group(0)

    rendered = VARIABLE_PATTERN.sub(_replacer, template)

    if not allow_mass_mentions:
        rendered = rendered.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")

    return rendered
