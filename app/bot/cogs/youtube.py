"""
PB HERO YouTube Cog.

Discord commands for managing YouTube channel monitoring.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.permissions import admin_only, guild_only
from app.config import get_settings

logger = logging.getLogger("pbhero.bot")
settings = get_settings()


class YouTubeCog(commands.Cog, name="YouTube"):
    """YouTube monitoring commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="yt-status", description="Check YouTube monitor status")
    @guild_only()
    @admin_only()
    async def yt_status(self, interaction: discord.Interaction):
        """Show YouTube monitor status."""
        scheduler = getattr(self.bot, "youtube_scheduler", None)

        embed = discord.Embed(title="📺 YouTube Monitor Status", color=0xFF0000)

        if scheduler:
            embed.add_field(name="Status", value="🟢 Running" if scheduler.is_running else "🔴 Stopped", inline=True)
            embed.add_field(name="Health", value="🟢 Healthy" if scheduler.is_healthy else "🟡 Warning", inline=True)
            if scheduler.last_check:
                embed.add_field(name="Last Check", value=scheduler.last_check.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        else:
            embed.add_field(name="Status", value="🔴 Not initialized", inline=True)

        from app.database.engine import get_session_direct
        from app.database.repositories import YouTubeChannelRepo

        session = await get_session_direct()
        try:
            total = await YouTubeChannelRepo.count(session)
            enabled = await YouTubeChannelRepo.count_enabled(session)
            embed.add_field(name="Channels", value=f"{enabled}/{total} enabled", inline=True)
            embed.add_field(name="Poll Interval", value=f"{settings.YOUTUBE_POLL_INTERVAL}s", inline=True)
            embed.add_field(name="Live Check", value=f"{settings.YOUTUBE_LIVE_CHECK_INTERVAL}s", inline=True)
        finally:
            await session.close()

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="yt-check", description="Force check a YouTube channel now")
    @app_commands.describe(channel_id="YouTube channel ID to check (or 'all')")
    @guild_only()
    @admin_only()
    async def yt_check(self, interaction: discord.Interaction, channel_id: str = "all"):
        """Force immediate feed check."""
        scheduler = getattr(self.bot, "youtube_scheduler", None)
        if not scheduler:
            return await interaction.response.send_message("❌ YouTube scheduler not running.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        check_id = None if channel_id == "all" else channel_id
        result = await scheduler.force_check(check_id)

        if result["success"]:
            await interaction.followup.send(f"✅ {result['message']}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ {result['message']}", ephemeral=True)

    @app_commands.command(name="yt-list", description="List monitored YouTube channels")
    @guild_only()
    @admin_only()
    async def yt_list(self, interaction: discord.Interaction):
        """List all monitored YouTube channels."""
        from app.database.engine import get_session_direct
        from app.database.repositories import YouTubeChannelRepo

        session = await get_session_direct()
        try:
            channels = await YouTubeChannelRepo.get_all(session)

            if not channels:
                return await interaction.response.send_message("No YouTube channels configured.", ephemeral=True)

            embed = discord.Embed(title="📺 Monitored YouTube Channels", color=0xFF0000)

            for ch in channels[:25]:
                status = "🟢" if ch.enabled else "🔴"
                error_text = f"\n⚠️ {ch.last_error[:50]}" if ch.last_error else ""
                last_check = ch.last_checked_at.strftime("%H:%M:%S") if ch.last_checked_at else "Never"
                embed.add_field(
                    name=f"{status} {ch.channel_name}",
                    value=f"ID: `{ch.youtube_channel_id}`\nHandle: {ch.handle or 'N/A'}\nLast check: {last_check}{error_text}",
                    inline=True,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            await session.close()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(YouTubeCog(bot))
