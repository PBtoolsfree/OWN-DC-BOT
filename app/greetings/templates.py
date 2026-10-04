"""
Template constants, variable extractors, and safe rendering for Server Greetings.
"""

import re
from typing import Any, Dict, List, Optional, Set

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
}

GOODBYE_VARIABLES: Set[str] = {
    "username",
    "display_name",
    "user_id",
    "server_name",
    "server_id",
    "member_count",
    "left_at",
    "invite_url",
}

WELCOME_DM_VARIABLES: Set[str] = {
    "username",
    "display_name",
    "user_mention",
    "user_id",
    "server_name",
    "server_id",
    "member_count",
    "joined_at",
    "rules_url",
    "invite_url",
}

GOODBYE_DM_VARIABLES: Set[str] = {
    "username",
    "display_name",
    "user_id",
    "server_name",
    "server_id",
    "member_count",
    "left_at",
    "invite_url",
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

DEFAULT_WELCOME_TITLE = "?? Welcome to {server_name}!"
DEFAULT_WELCOME_DESCRIPTION = "Welcome {user_mention} to **{server_name}**! ??\n\nYou are member **#{member_count}**.\n\nPlease check the rules and enjoy your stay!"
DEFAULT_WELCOME_FOOTER = "PB HERO SERVER"

DEFAULT_GOODBYE_TITLE = "?? Goodbye {display_name}"
DEFAULT_GOODBYE_DESCRIPTION = "**{display_name}** has left **{server_name}**.\n\nWe had **{member_count} members** before the departure."
DEFAULT_GOODBYE_FOOTER = "PB HERO SERVER"

DEFAULT_WELCOME_DM_TITLE = "?? Welcome to {server_name}!"
DEFAULT_WELCOME_DM_DESCRIPTION = "Hi {display_name}! ??\n\nThanks for joining our Discord server.\n\n?? Please read the server rules:\n{rules_url}\n\n?? Server Invite:\n{invite_url}\n\nEnjoy the community!"
DEFAULT_WELCOME_DM_FOOTER = "PB HERO SERVER"

DEFAULT_GOODBYE_DM_TITLE = "?? Goodbye {display_name}"
DEFAULT_GOODBYE_DM_DESCRIPTION = "You have left {server_name}.\n\nWe're sorry to see you go. ??\n\nIf you ever want to come back:\n\n?? Rejoin Server:\n{invite_url}\n\nTake care!"
DEFAULT_GOODBYE_DM_FOOTER = "PB HERO SERVER"

DEFAULT_RULES_TITLE = "?? {server_name} RULES"
DEFAULT_RULES_DESCRIPTION = "1. Respect all members.\n2. No spam or unsolicited promotions.\n3. No offensive or harmful content.\n4. Follow channel guidelines and moderator instructions.\n\nPlease read the full rules before chatting!"
DEFAULT_RULES_FOOTER = "PB HERO SERVER"

VARIABLE_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")


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

    # Ensure fallback markers for special variables if None or empty
    safe_context = dict(context)
    if not safe_context.get("invite_url"):
        safe_context["invite_url"] = "[Invite unavailable]"
    if not safe_context.get("rules_url"):
        safe_context["rules_url"] = "[Rules unavailable]"

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
