"""
PB HERO Moderation Cog.

Slash commands for moderation: /warn, /timeout, /kick, /ban, etc.
All commands are guild-scoped to the configured server.
"""

import logging
from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.permissions import guild_only, moderator_only
from app.config import get_settings
from app.database.engine import get_session_direct
from app.database.models import ModerationAction
from app.database.repositories import ModerationCaseRepo
from app.moderation.actions import (
    CaseManager,
    execute_ban,
    execute_kick,
    execute_timeout,
    execute_unban,
    execute_untimeout,
    execute_warn,
)

logger = logging.getLogger("pbhero.bot")
settings = get_settings()


class ModerationCog(commands.Cog, name="Moderation"):
    """Moderation commands for server management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.case_manager = CaseManager(
            bot=bot,
            guild_id=settings.DISCORD_GUILD_ID,
            mod_log_channel_id=settings.MOD_LOG_CHANNEL_ID or None,
        )

    @app_commands.command(name="warn", description="Issue a warning to a member")
    @app_commands.describe(member="The member to warn", reason="Reason for warning")
    @guild_only()
    @moderator_only()
    async def warn(self, interaction: discord.Interaction, member: discord.Member,
                   reason: str = "No reason provided"):
        """Warn a member."""
        if member.bot:
            return await interaction.response.send_message("❌ Cannot warn bots.", ephemeral=True)

        case_number = await execute_warn(self.case_manager, interaction, member, reason)
        await interaction.response.send_message(
            f"⚠️ **{member}** has been warned.\n**Reason:** {reason}\n**Case:** #{case_number}",
            ephemeral=False,
        )

    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="The member to check")
    @guild_only()
    @moderator_only()
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        """View warnings for a member."""
        session = await get_session_direct()
        try:
            cases = await ModerationCaseRepo.get_for_user(session, member.id)
            warns = [c for c in cases if c.action == ModerationAction.WARN or
                     (isinstance(c.action, str) and c.action == "warn")]

            if not warns:
                return await interaction.response.send_message(
                    f"✅ **{member}** has no warnings.", ephemeral=True
                )

            embed = discord.Embed(
                title=f"⚠️ Warnings for {member}",
                color=0xF39C12,
            )
            for w in warns[:25]:  # Max 25 fields
                embed.add_field(
                    name=f"Case #{w.case_number}",
                    value=f"**Reason:** {w.reason or 'No reason'}\n**By:** <@{w.moderator_user_id}>\n**Date:** {w.created_at.strftime('%Y-%m-%d %H:%M')}",
                    inline=False,
                )
            embed.set_footer(text=f"Total warnings: {len(warns)}")

            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            await session.close()

    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.describe(
        member="The member to timeout",
        duration="Duration (e.g., 10m, 1h, 1d)",
        reason="Reason for timeout"
    )
    @guild_only()
    @moderator_only()
    async def timeout(self, interaction: discord.Interaction, member: discord.Member,
                      duration: str, reason: str = "No reason provided"):
        """Timeout a member."""
        seconds = self._parse_duration(duration)
        if not seconds:
            return await interaction.response.send_message(
                "❌ Invalid duration. Use: 10s, 10m, 1h, 1d", ephemeral=True
            )

        case_number = await execute_timeout(self.case_manager, interaction, member, seconds, reason)
        await interaction.response.send_message(
            f"⏰ **{member}** has been timed out for {duration}.\n**Reason:** {reason}\n**Case:** #{case_number}",
        )

    @app_commands.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.describe(member="The member to untimeout", reason="Reason")
    @guild_only()
    @moderator_only()
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member,
                        reason: str = "Timeout removed"):
        """Remove timeout from a member."""
        case_number = await execute_untimeout(self.case_manager, interaction, member, reason)
        await interaction.response.send_message(
            f"⏰ Timeout removed for **{member}**.\n**Case:** #{case_number}",
        )

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="The member to kick", reason="Reason for kick")
    @guild_only()
    @moderator_only()
    async def kick(self, interaction: discord.Interaction, member: discord.Member,
                   reason: str = "No reason provided"):
        """Kick a member."""
        case_number = await execute_kick(self.case_manager, interaction, member, reason)
        await interaction.response.send_message(
            f"👢 **{member}** has been kicked.\n**Reason:** {reason}\n**Case:** #{case_number}",
        )

    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.describe(user="The user to ban", reason="Reason for ban", delete_days="Days of messages to delete")
    @guild_only()
    @moderator_only()
    async def ban(self, interaction: discord.Interaction, user: discord.User,
                  reason: str = "No reason provided", delete_days: int = 0):
        """Ban a user."""
        case_number = await execute_ban(self.case_manager, interaction, user, reason, delete_days)
        await interaction.response.send_message(
            f"🔨 **{user}** has been banned.\n**Reason:** {reason}\n**Case:** #{case_number}",
        )

    @app_commands.command(name="unban", description="Unban a user")
    @app_commands.describe(user_id="The user ID to unban", reason="Reason")
    @guild_only()
    @moderator_only()
    async def unban(self, interaction: discord.Interaction, user_id: str,
                    reason: str = "Unbanned"):
        """Unban a user by ID."""
        try:
            user = await self.bot.fetch_user(int(user_id))
        except (ValueError, discord.NotFound):
            return await interaction.response.send_message("❌ User not found.", ephemeral=True)

        case_number = await execute_unban(self.case_manager, interaction, user, reason)
        await interaction.response.send_message(
            f"🔓 **{user}** has been unbanned.\n**Case:** #{case_number}",
        )

    @app_commands.command(name="purge", description="Delete multiple messages")
    @app_commands.describe(count="Number of messages to delete (1-100)")
    @guild_only()
    @moderator_only()
    async def purge(self, interaction: discord.Interaction, count: int):
        """Purge messages from a channel."""
        if count < 1 or count > 100:
            return await interaction.response.send_message("❌ Count must be 1-100.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=count)

        await self.case_manager.create_case(
            action=ModerationAction.PURGE,
            target=interaction.user,  # Self-targeting for purge
            moderator=interaction.user,
            reason=f"Purged {len(deleted)} messages",
            channel_id=interaction.channel.id,
        )

        await interaction.followup.send(f"🗑️ Deleted {len(deleted)} messages.", ephemeral=True)

    @app_commands.command(name="clear", description="Clear messages from a specific user")
    @app_commands.describe(member="User to clear messages from", count="Number of messages to check")
    @guild_only()
    @moderator_only()
    async def clear(self, interaction: discord.Interaction, member: discord.Member, count: int = 50):
        """Clear messages from a specific user."""
        if count < 1 or count > 100:
            return await interaction.response.send_message("❌ Count must be 1-100.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        def check(m):
            return m.author.id == member.id

        deleted = await interaction.channel.purge(limit=count, check=check)

        await self.case_manager.create_case(
            action=ModerationAction.CLEAR,
            target=member,
            moderator=interaction.user,
            reason=f"Cleared {len(deleted)} messages",
            channel_id=interaction.channel.id,
        )

        await interaction.followup.send(f"🧹 Cleared {len(deleted)} messages from {member}.", ephemeral=True)

    @app_commands.command(name="slowmode", description="Set channel slowmode")
    @app_commands.describe(seconds="Slowmode in seconds (0 to disable)")
    @guild_only()
    @moderator_only()
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        """Set slowmode for a channel."""
        if seconds < 0 or seconds > 21600:
            return await interaction.response.send_message("❌ Slowmode must be 0-21600 seconds.", ephemeral=True)

        await interaction.channel.edit(slowmode_delay=seconds)

        await self.case_manager.create_case(
            action=ModerationAction.SLOWMODE,
            target=interaction.user,
            moderator=interaction.user,
            reason=f"Slowmode set to {seconds}s in #{interaction.channel.name}",
            channel_id=interaction.channel.id,
        )

        if seconds == 0:
            await interaction.response.send_message("🐌 Slowmode disabled.")
        else:
            await interaction.response.send_message(f"🐌 Slowmode set to {seconds} seconds.")

    @app_commands.command(name="lock", description="Lock a channel (prevent members from sending)")
    @guild_only()
    @moderator_only()
    async def lock(self, interaction: discord.Interaction):
        """Lock a channel."""
        channel = interaction.channel
        # Preserve staff access
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        await self.case_manager.create_case(
            action=ModerationAction.LOCK,
            target=interaction.user,
            moderator=interaction.user,
            reason=f"Channel #{channel.name} locked",
            channel_id=channel.id,
        )

        await interaction.response.send_message("🔒 Channel locked. Members cannot send messages.")

    @app_commands.command(name="unlock", description="Unlock a channel")
    @guild_only()
    @moderator_only()
    async def unlock(self, interaction: discord.Interaction):
        """Unlock a channel."""
        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None  # Reset to inherit
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        await self.case_manager.create_case(
            action=ModerationAction.UNLOCK,
            target=interaction.user,
            moderator=interaction.user,
            reason=f"Channel #{channel.name} unlocked",
            channel_id=channel.id,
        )

        await interaction.response.send_message("🔓 Channel unlocked.")

    @app_commands.command(name="userinfo", description="View information about a user")
    @app_commands.describe(member="The member to inspect")
    @guild_only()
    @moderator_only()
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member):
        """Show user information."""
        embed = discord.Embed(title=f"User Info: {member}", color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M") if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)

        roles = [r.mention for r in member.roles[1:]]  # Skip @everyone
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles[:20]) or "None", inline=False)

        # Get moderation cases
        session = await get_session_direct()
        try:
            cases = await ModerationCaseRepo.get_for_user(session, member.id)
            if cases:
                embed.add_field(name="Moderation Cases", value=str(len(cases)), inline=True)
        finally:
            await session.close()

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="modlogs", description="View moderation logs")
    @app_commands.describe(count="Number of entries to show")
    @guild_only()
    @moderator_only()
    async def modlogs(self, interaction: discord.Interaction, count: int = 10):
        """View recent moderation logs."""
        session = await get_session_direct()
        try:
            cases = await ModerationCaseRepo.get_recent(session, limit=min(count, 25))

            if not cases:
                return await interaction.response.send_message("No moderation cases found.", ephemeral=True)

            embed = discord.Embed(title="📋 Recent Moderation Logs", color=0x3498DB)
            for case in cases:
                action_val = case.action.value if isinstance(case.action, ModerationAction) else str(case.action)
                embed.add_field(
                    name=f"Case #{case.case_number} — {action_val.upper()}",
                    value=f"**User:** <@{case.target_user_id}>\n**Mod:** <@{case.moderator_user_id}>\n**Reason:** {case.reason or 'None'}\n**Date:** {case.created_at.strftime('%Y-%m-%d %H:%M')}",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            await session.close()

    @app_commands.command(name="case", description="View a specific moderation case")
    @app_commands.describe(number="Case number")
    @guild_only()
    @moderator_only()
    async def case(self, interaction: discord.Interaction, number: int):
        """View a specific moderation case."""
        session = await get_session_direct()
        try:
            case = await ModerationCaseRepo.get_by_case_number(session, number)
            if not case:
                return await interaction.response.send_message(f"❌ Case #{number} not found.", ephemeral=True)

            action_val = case.action.value if isinstance(case.action, ModerationAction) else str(case.action)
            embed = discord.Embed(
                title=f"📋 Case #{case.case_number}",
                color=0x3498DB,
                timestamp=case.created_at,
            )
            embed.add_field(name="Action", value=action_val.upper(), inline=True)
            embed.add_field(name="User", value=f"<@{case.target_user_id}> ({case.target_username})", inline=True)
            embed.add_field(name="Moderator", value=f"<@{case.moderator_user_id}> ({case.moderator_username})", inline=True)
            embed.add_field(name="Reason", value=case.reason or "No reason", inline=False)

            if case.duration:
                embed.add_field(name="Duration", value=f"{case.duration}s", inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            await session.close()

    @staticmethod
    def _parse_duration(duration_str: str) -> Optional[int]:
        """Parse a duration string (10s, 10m, 1h, 1d) to seconds."""
        duration_str = duration_str.strip().lower()
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}

        if not duration_str:
            return None

        unit = duration_str[-1]
        if unit in multipliers:
            try:
                value = int(duration_str[:-1])
                return value * multipliers[unit]
            except ValueError:
                return None

        try:
            return int(duration_str)  # Assume seconds
        except ValueError:
            return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))
