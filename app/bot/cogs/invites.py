"""
PB HERO Invite Tracking & Analytics Cog.

Provides Discord commands (!invites, /invites, !inviteleaderboard, /inviteleaderboard,
!invitedetails, /invitedetails) and event listeners for invite creation & revocation.
"""

from datetime import datetime, timezone
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.permissions import guild_only
from app.config import get_settings
from app.database.engine import get_session_direct
from app.database.repositories import (
    DiscordInviteRepo,
    InviteJoinRepo,
)
from app.invites.tracker import get_invite_tracker

logger = logging.getLogger("pbhero.bot.invites")
settings = get_settings()


class InvitesCog(commands.Cog, name="Invites"):
    """Discord invite tracking cog."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tracker = get_invite_tracker(bot)

    # ========================================================
    # Event Listeners
    # ========================================================

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Called when a server invite is created."""
        try:
            await self.tracker.handle_invite_create(invite)
        except Exception as e:
            logger.error("Error handling on_invite_create for %s: %s", getattr(invite, "code", "?"), e, exc_info=True)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Called when a server invite is deleted or revoked."""
        try:
            await self.tracker.handle_invite_delete(invite)
        except Exception as e:
            logger.error("Error handling on_invite_delete for %s: %s", getattr(invite, "code", "?"), e, exc_info=True)

    # ========================================================
    # Slash Commands
    # ========================================================

    @app_commands.command(name="invites", description="Show personal or another member's invite statistics")
    @app_commands.describe(member="Member to inspect (defaults to yourself)")
    @guild_only()
    async def slash_invites(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """Show member invite stats."""
        target = member or interaction.user
        embed = await self._build_invites_embed(target)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="inviteleaderboard", description="Display the server's top inviters leaderboard")
    @guild_only()
    async def slash_leaderboard(self, interaction: discord.Interaction):
        """Show top inviters."""
        embed = await self._build_leaderboard_embed()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invitedetails", description="Show detailed statistics for a specific invite code")
    @app_commands.describe(code="Invite code (e.g. ABC123)")
    @guild_only()
    async def slash_details(self, interaction: discord.Interaction, code: str):
        """Show specific invite details."""
        embed = await self._build_details_embed(code.strip())
        await interaction.response.send_message(embed=embed)

    # ========================================================
    # Prefix Commands (!invites, !inviteleaderboard, !invitedetails)
    # ========================================================

    @commands.command(name="invites", help="Show personal or another member's invite stats")
    async def prefix_invites(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Prefix command for invites."""
        target = member or ctx.author
        embed = await self._build_invites_embed(target)
        await ctx.send(embed=embed)

    @commands.command(name="inviteleaderboard", aliases=["topinvites", "ileaderboard"], help="Show top inviters")
    async def prefix_leaderboard(self, ctx: commands.Context):
        """Prefix command for invite leaderboard."""
        embed = await self._build_leaderboard_embed()
        await ctx.send(embed=embed)

    @commands.command(name="invitedetails", aliases=["invdetails"], help="Show invite code details")
    async def prefix_details(self, ctx: commands.Context, code: str):
        """Prefix command for invite details."""
        embed = await self._build_details_embed(code.strip())
        await ctx.send(embed=embed)

    # ========================================================
    # Embed Builders
    # ========================================================

    async def _build_invites_embed(self, user: discord.abc.User) -> discord.Embed:
        session = await get_session_direct()
        try:
            stats = await InviteJoinRepo.get_user_stats(session, settings.DISCORD_GUILD_ID, user.id)
        finally:
            await session.close()

        embed = discord.Embed(
            title=f"📨 Invite Profile • {user.display_name}",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        if getattr(user, "display_avatar", None):
            embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="Total Joins", value=f"**{stats['total_joins']}**", inline=True)
        embed.add_field(name="This Month", value=f"**{stats['this_month_joins']}**", inline=True)
        embed.add_field(name="This Week", value=f"**{stats['this_week_joins']}**", inline=True)

        embed.add_field(name="Current Members", value=str(stats.get("current_members_referred", 0)), inline=True)
        embed.add_field(name="Former Members", value=str(stats.get("former_members_referred", 0)), inline=True)
        embed.add_field(
            name="Last Attributed Join",
            value=stats["last_invite_join"][:16].replace("T", " ") if stats["last_invite_join"] else "Never",
            inline=True,
        )

        inv_list = stats.get("invites", [])
        if inv_list:
            lines = []
            for inv in inv_list[:5]:
                status_emoji = "🟢" if inv["status"] == "ACTIVE" else "⚪"
                lines.append(f"{status_emoji} `{inv['invite_code']}` • {inv['uses']} uses (#{inv['channel_name'] or 'chan'})")
            embed.add_field(name=f"Active Codes ({len(inv_list)})", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Active Codes", value="No invites created yet", inline=False)

        embed.set_footer(text="PB HERO Invite Analytics")
        return embed

    async def _build_leaderboard_embed(self) -> discord.Embed:
        session = await get_session_direct()
        try:
            leaderboard = await InviteJoinRepo.get_leaderboard(session, settings.DISCORD_GUILD_ID, limit=10)
        finally:
            await session.close()

        embed = discord.Embed(
            title="🏆 Server Invite Leaderboard",
            description="Top members with the most attributed joins.",
            color=0xF1C40F,
            timestamp=datetime.now(timezone.utc),
        )

        if not leaderboard:
            embed.description = "No attributed member invites recorded yet."
            return embed

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for entry in leaderboard:
            rank = entry["rank"]
            medal = medals.get(rank, f"`#{rank}`")
            user_str = f"<@{entry['user_id']}>"
            lines.append(f"{medal} {user_str} — **{entry['joins']} joins** ({entry['percentage']}%)")

        embed.add_field(name="Top Inviters", value="\n".join(lines), inline=False)
        embed.set_footer(text="PB HERO Invite Analytics")
        return embed

    async def _build_details_embed(self, code: str) -> discord.Embed:
        session = await get_session_direct()
        try:
            inv = await DiscordInviteRepo.get_by_code(session, code)
            joins, total_joins = await InviteJoinRepo.get_joins_for_invite(session, code, limit=5)
        finally:
            await session.close()

        if not inv:
            embed = discord.Embed(
                title="❌ Invite Not Found",
                description=f"Invite code `{code}` is not tracked in the database.",
                color=0xED4245,
            )
            return embed

        embed = discord.Embed(
            title=f"🔎 Invite Details • {inv.invite_code}",
            color=0x2ECC71 if inv.status == "ACTIVE" else 0x95A5A6,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Status", value=f"`{inv.status}`", inline=True)
        embed.add_field(name="Discord Uses", value=str(inv.uses), inline=True)
        embed.add_field(name="Tracked Joins", value=str(total_joins), inline=True)

        inviter_str = f"<@{inv.inviter_id}>" if inv.inviter_id else (inv.inviter_name or "Unknown")
        embed.add_field(name="Inviter", value=inviter_str, inline=True)
        chan_str = f"<#{inv.channel_id}>" if inv.channel_id else (inv.channel_name or "Unknown")
        embed.add_field(name="Target Channel", value=chan_str, inline=True)
        max_uses_str = str(inv.max_uses) if inv.max_uses else "Unlimited"
        embed.add_field(name="Max Uses", value=max_uses_str, inline=True)

        created_str = inv.created_at.strftime("%Y-%m-%d %H:%M") if inv.created_at else "Unknown"
        embed.add_field(name="Created", value=created_str, inline=True)
        last_str = inv.last_seen_at.strftime("%Y-%m-%d %H:%M") if inv.last_seen_at else "Never"
        embed.add_field(name="Last Seen", value=last_str, inline=True)

        if joins:
            join_lines = []
            for j in joins:
                member_str = f"<@{j.member_id}>"
                t_str = j.joined_at.strftime("%b %d, %H:%M") if j.joined_at else "Unknown"
                status_icon = "👤" if j.is_still_member else "💨 (Left)"
                join_lines.append(f"{status_icon} {member_str} • {t_str}")
            embed.add_field(name=f"Recent Joins ({total_joins})", value="\n".join(join_lines), inline=False)
        else:
            embed.add_field(name="Recent Joins", value="No members joined using this invite yet", inline=False)

        embed.set_footer(text="PB HERO Invite Analytics")
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InvitesCog(bot))
