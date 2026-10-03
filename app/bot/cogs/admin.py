"""
PB HERO Admin Cog.

Administrative commands: bot status, reload, system info.
"""

import logging
import platform
import sys
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

import app
from app.bot.permissions import admin_only, guild_only
from app.config import get_settings
from app.database.engine import test_connection

logger = logging.getLogger("pbhero.bot")
settings = get_settings()


class AdminCog(commands.Cog, name="Admin"):
    """Administrative commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="status", description="Show bot status")
    @guild_only()
    @admin_only()
    async def status(self, interaction: discord.Interaction):
        """Show comprehensive bot status."""
        embed = discord.Embed(
            title="🤖 PB HERO Bot Status",
            color=0x2ECC71,
            timestamp=datetime.utcnow(),
        )

        # Bot info
        embed.add_field(name="Version", value=app.__version__, inline=True)
        embed.add_field(name="Python", value=sys.version.split()[0], inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)

        # Connection
        latency = round(self.bot.latency * 1000)
        embed.add_field(name="Latency", value=f"{latency}ms", inline=True)

        # Uptime
        uptime = self.bot.uptime
        if uptime:
            hours, remainder = divmod(int(uptime), 3600)
            minutes, seconds = divmod(remainder, 60)
            embed.add_field(name="Uptime", value=f"{hours}h {minutes}m {seconds}s", inline=True)

        # Database
        db_ok = await test_connection()
        embed.add_field(name="Database", value="🟢 Connected" if db_ok else "🔴 Error", inline=True)

        # YouTube
        scheduler = getattr(self.bot, "youtube_scheduler", None)
        if scheduler:
            yt_status = "🟢 Running" if scheduler.is_running else "🔴 Stopped"
            embed.add_field(name="YouTube", value=yt_status, inline=True)

        # Server
        guild = self.bot.guild
        if guild:
            embed.add_field(name="Server", value=guild.name, inline=True)
            embed.add_field(name="Members", value=str(guild.member_count), inline=True)

        embed.add_field(name="Platform", value=platform.platform(), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reload-policies", description="Reload moderation policies from database")
    @guild_only()
    @admin_only()
    async def reload_policies(self, interaction: discord.Interaction):
        """Reload moderation engine cache."""
        engine = getattr(self.bot, "moderation_engine", None)
        if engine:
            await engine.refresh_cache()
            await interaction.response.send_message("✅ Moderation policies reloaded.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Moderation engine not initialized.", ephemeral=True)

    @app_commands.command(name="ping", description="Check bot latency")
    @guild_only()
    async def ping(self, interaction: discord.Interaction):
        """Simple ping command."""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Latency: {latency}ms")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
