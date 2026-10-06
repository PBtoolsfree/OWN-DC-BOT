"""
Role management and hierarchy verification for PB HERO Personal Discord Bot.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord.ext import commands

logger = logging.getLogger("pbhero.greetings.roles")


def get_guild_roles(bot: Optional[commands.Bot], guild_id: int) -> List[Dict[str, Any]]:
    """Return roles from the connected guild with assignability telemetry."""
    if not bot or not bot.is_ready():
        return []

    guild = bot.guild
    if not guild or guild.id != guild_id:
        return []

    me = guild.me
    can_manage = bool(me and me.guild_permissions.manage_roles)
    bot_top = me.top_role if me else None

    results = []
    for role in reversed(guild.roles):
        if role.is_default():  # @everyone
            continue

        is_assignable = bool(
            can_manage
            and bot_top
            and bot_top > role
            and not role.managed
        )

        results.append({
            "id": str(role.id),
            "name": role.name,
            "color": str(role.color),
            "position": role.position,
            "member_count": len(role.members),
            "is_assignable": is_assignable,
            "is_managed": role.managed,
        })
    return results


async def assign_auto_role(member: discord.Member, role_id: int) -> Tuple[bool, Optional[str]]:
    """Attempt to assign default member role respecting Discord role hierarchy."""
    guild = member.guild
    role = guild.get_role(role_id)
    if not role:
        msg = f"Selected role {role_id} no longer exists in guild."
        logger.warning(msg)
        return False, msg

    me = guild.me
    if not me or not me.guild_permissions.manage_roles:
        msg = "Bot lacks 'Manage Roles' permission"
        logger.warning("Cannot assign role: %s", msg)
        return False, msg

    is_higher = False
    try:
        bot_pos = getattr(me.top_role, "position", None)
        role_pos = getattr(role, "position", None)
        if isinstance(bot_pos, int) and isinstance(role_pos, int):
            is_higher = bot_pos <= role_pos
        else:
            res = me.top_role <= role
            if not isinstance(res, bool):
                is_higher = False
            else:
                is_higher = res
    except Exception:
        is_higher = False

    if is_higher:
        msg = f"Role '{role.name}' is higher than or equal to PB HERO's highest role"
        logger.warning("Role hierarchy violation: %s", msg)
        return False, msg

    try:
        await member.add_roles(role, reason="Auto Role on Member Join")
        logger.info("Assigned auto role @%s to %s", role.name, member)
        return True, None
    except Exception as e:
        logger.warning("Failed to assign auto role to %s: %s", member, e)
        return False, str(e)
