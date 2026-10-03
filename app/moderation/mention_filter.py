"""
PB HERO Mention Filter.

Detects and filters @everyone, @here, role mentions, and user mentions.
"""

import logging
from typing import Optional

import discord

logger = logging.getLogger("pbhero.moderation")


def check_mentions(message: discord.Message, policy: dict) -> Optional[dict]:
    """
    Check a message for mention policy violations.

    Args:
        message: Discord message to check
        policy: Dict with allow_everyone, allow_here, allow_role_mentions, allow_user_mentions

    Returns:
        Violation dict if blocked, None if allowed
    """
    # Check @everyone
    if message.mention_everyone:
        if policy.get("allow_everyone") == "deny":
            return {
                "reason": "@everyone mentions are not allowed in this channel",
                "rule": "everyone_denied",
                "mention_type": "everyone",
            }
        if policy.get("allow_here") == "deny":
            # Discord's mention_everyone covers both @everyone and @here
            return {
                "reason": "@here mentions are not allowed in this channel",
                "rule": "here_denied",
                "mention_type": "here",
            }

    # Check @here in content (even if mention_everyone is False, check raw content)
    if "@here" in message.content:
        if policy.get("allow_here") == "deny":
            return {
                "reason": "@here mentions are not allowed in this channel",
                "rule": "here_denied",
                "mention_type": "here",
            }

    if "@everyone" in message.content:
        if policy.get("allow_everyone") == "deny":
            return {
                "reason": "@everyone mentions are not allowed in this channel",
                "rule": "everyone_denied",
                "mention_type": "everyone",
            }

    # Check role mentions
    if message.role_mentions and policy.get("allow_role_mentions") == "deny":
        return {
            "reason": "Role mentions are not allowed in this channel",
            "rule": "role_mentions_denied",
            "mention_type": "role",
        }

    # Check user mentions
    if message.mentions and policy.get("allow_user_mentions") == "deny":
        # Don't block replies (which create mentions)
        if not message.reference:
            return {
                "reason": "User mentions are not allowed in this channel",
                "rule": "user_mentions_denied",
                "mention_type": "user",
            }

    return None
