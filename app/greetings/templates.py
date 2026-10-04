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
}

GOODBYE_VARIABLES: Set[str] = {
    "username",
    "display_name",
    "user_id",
    "server_name",
    "server_id",
    "member_count",
    "left_at",
}

DEFAULT_WELCOME_TITLE = "?? Welcome to {server_name}!"
DEFAULT_WELCOME_DESCRIPTION = "Welcome {user_mention} to **{server_name}**! ??\n\nYou are member **#{member_count}**.\n\nPlease check the rules and enjoy your stay!"
DEFAULT_WELCOME_FOOTER = "PB HERO SERVER"

DEFAULT_GOODBYE_TITLE = "?? Goodbye {display_name}"
DEFAULT_GOODBYE_DESCRIPTION = "**{display_name}** has left **{server_name}**.\n\nWe had **{member_count} members** before the departure."
DEFAULT_GOODBYE_FOOTER = "PB HERO SERVER"

VARIABLE_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")


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
    Mass mentions (@everyone, @here) are sanitized unless explicitly permitted.
    """
    if not template:
        return ""

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in context:
            val = context[var_name]
            return str(val) if val is not None else ""
        return match.group(0)

    rendered = VARIABLE_PATTERN.sub(_replacer, template)

    if not allow_mass_mentions:
        rendered = rendered.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")

    return rendered
