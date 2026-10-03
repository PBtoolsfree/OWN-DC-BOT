"""
PB HERO Moderation Actions & Case Manager.

Executes moderation actions and creates case records.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import discord

from app.database.engine import get_session_direct
from app.database.models import ModerationAction
from app.database.repositories import ModerationCaseRepo

logger = logging.getLogger("pbhero.moderation")


class CaseManager:
    """Manages moderation cases for the single configured guild."""

    def __init__(self, bot: discord.Client, guild_id: int, mod_log_channel_id: int = None):
        self.bot = bot
        self.guild_id = guild_id
        self.mod_log_channel_id = mod_log_channel_id

    async def create_case(
        self,
        action: ModerationAction,
        target: discord.Member | discord.User,
        moderator: discord.Member | discord.User,
        reason: str = None,
        duration: int = None,
        channel_id: int = None,
        message_id: int = None,
    ) -> int:
        """Create a moderation case and return the case number."""
        session = await get_session_direct()
        try:
            case = await ModerationCaseRepo.create(
                session=session,
                target_user_id=target.id,
                target_username=str(target),
                moderator_user_id=moderator.id,
                moderator_username=str(moderator),
                action=action,
                reason=reason,
                duration=duration,
                channel_id=channel_id,
                message_id=message_id,
            )
            await session.commit()

            # Send to mod log
            await self._send_case_log(case, target, moderator)

            logger.info("Case #%d created: %s %s by %s",
                       case.case_number, action.value, target, moderator)
            return case.case_number
        except Exception as e:
            await session.rollback()
            logger.error("Failed to create case: %s", str(e))
            raise
        finally:
            await session.close()

    async def _send_case_log(self, case, target, moderator) -> None:
        """Send case embed to mod log channel."""
        if not self.mod_log_channel_id:
            return

        channel = self.bot.get_channel(self.mod_log_channel_id)
        if not channel:
            return

        # Action colors
        colors = {
            ModerationAction.WARN: 0xF39C12,
            ModerationAction.TIMEOUT: 0xE67E22,
            ModerationAction.KICK: 0xE74C3C,
            ModerationAction.BAN: 0xC0392B,
            ModerationAction.UNBAN: 0x2ECC71,
            ModerationAction.UNTIMEOUT: 0x2ECC71,
            ModerationAction.CLEAR: 0x3498DB,
            ModerationAction.PURGE: 0x3498DB,
            ModerationAction.LOCK: 0x95A5A6,
            ModerationAction.UNLOCK: 0x2ECC71,
            ModerationAction.SLOWMODE: 0x9B59B6,
        }

        action_emojis = {
            ModerationAction.WARN: "⚠️",
            ModerationAction.TIMEOUT: "⏰",
            ModerationAction.KICK: "👢",
            ModerationAction.BAN: "🔨",
            ModerationAction.UNBAN: "🔓",
            ModerationAction.UNTIMEOUT: "⏰",
            ModerationAction.CLEAR: "🧹",
            ModerationAction.PURGE: "🗑️",
            ModerationAction.LOCK: "🔒",
            ModerationAction.UNLOCK: "🔓",
            ModerationAction.SLOWMODE: "🐌",
        }

        action = case.action if isinstance(case.action, ModerationAction) else ModerationAction(case.action)
        emoji = action_emojis.get(action, "📋")
        color = colors.get(action, 0x95A5A6)

        embed = discord.Embed(
            title=f"{emoji} Case #{case.case_number} — {action.value.upper()}",
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="User", value=f"{target.mention} ({target})", inline=True)
        embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator})", inline=True)

        if case.reason:
            embed.add_field(name="Reason", value=case.reason, inline=False)

        if case.duration:
            if case.duration >= 86400:
                duration_str = f"{case.duration // 86400} day(s)"
            elif case.duration >= 3600:
                duration_str = f"{case.duration // 3600} hour(s)"
            elif case.duration >= 60:
                duration_str = f"{case.duration // 60} minute(s)"
            else:
                duration_str = f"{case.duration} second(s)"
            embed.add_field(name="Duration", value=duration_str, inline=True)

        embed.set_footer(text=f"Case #{case.case_number}")

        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error("Failed to send case log: %s", str(e))


async def execute_warn(
    case_manager: CaseManager,
    interaction: discord.Interaction,
    target: discord.Member,
    reason: str = "No reason provided",
) -> int:
    """Issue a warning."""
    case_number = await case_manager.create_case(
        action=ModerationAction.WARN,
        target=target,
        moderator=interaction.user,
        reason=reason,
    )
    return case_number


async def execute_timeout(
    case_manager: CaseManager,
    interaction: discord.Interaction,
    target: discord.Member,
    duration_seconds: int,
    reason: str = "No reason provided",
) -> int:
    """Apply a timeout to a member."""
    until = discord.utils.utcnow() + timedelta(seconds=duration_seconds)
    await target.timeout(until, reason=reason)

    case_number = await case_manager.create_case(
        action=ModerationAction.TIMEOUT,
        target=target,
        moderator=interaction.user,
        reason=reason,
        duration=duration_seconds,
    )
    return case_number


async def execute_untimeout(
    case_manager: CaseManager,
    interaction: discord.Interaction,
    target: discord.Member,
    reason: str = "Timeout removed",
) -> int:
    """Remove a timeout from a member."""
    await target.timeout(None, reason=reason)

    case_number = await case_manager.create_case(
        action=ModerationAction.UNTIMEOUT,
        target=target,
        moderator=interaction.user,
        reason=reason,
    )
    return case_number


async def execute_kick(
    case_manager: CaseManager,
    interaction: discord.Interaction,
    target: discord.Member,
    reason: str = "No reason provided",
) -> int:
    """Kick a member from the server."""
    await target.kick(reason=reason)

    case_number = await case_manager.create_case(
        action=ModerationAction.KICK,
        target=target,
        moderator=interaction.user,
        reason=reason,
    )
    return case_number


async def execute_ban(
    case_manager: CaseManager,
    interaction: discord.Interaction,
    target: discord.Member | discord.User,
    reason: str = "No reason provided",
    delete_days: int = 0,
) -> int:
    """Ban a user from the server."""
    guild = interaction.guild
    await guild.ban(target, reason=reason, delete_message_days=min(delete_days, 7))

    case_number = await case_manager.create_case(
        action=ModerationAction.BAN,
        target=target,
        moderator=interaction.user,
        reason=reason,
    )
    return case_number


async def execute_unban(
    case_manager: CaseManager,
    interaction: discord.Interaction,
    user: discord.User,
    reason: str = "Unbanned",
) -> int:
    """Unban a user."""
    guild = interaction.guild
    await guild.unban(user, reason=reason)

    case_number = await case_manager.create_case(
        action=ModerationAction.UNBAN,
        target=user,
        moderator=interaction.user,
        reason=reason,
    )
    return case_number
