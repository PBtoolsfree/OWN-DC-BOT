"""
PB HERO Discord Bot Client.

Main bot class for the single-server personal Discord bot.
Uses only required intents and guild-scoped commands.
"""

import logging
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

from app.config import Settings, get_settings
from app.moderation.engine import ModerationEngine
from app.youtube.scheduler import YouTubeScheduler

logger = logging.getLogger("pbhero.bot")


class PBHeroBot(commands.Bot):
    """
    PB HERO Personal Discord Bot.

    Designed for exactly ONE Discord server.
    Guild-scoped commands and single-guild validation.
    """

    def __init__(self, settings: Settings = None):
        self.settings = settings or get_settings()
        self.start_time: Optional[datetime] = None
        self.youtube_scheduler: Optional[YouTubeScheduler] = None
        self.moderation_engine: Optional[ModerationEngine] = None
        self._guild: Optional[discord.Guild] = None

        # Configure intents (minimal required set)
        # Message Content is required for:
        # - URL detection in messages (link blocking)
        # - Mention filtering (@everyone, @here detection in content)
        # - Attachment validation rules
        # - Custom message policy enforcement
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True  # Required for message filtering
        intents.members = True  # Required for member permission checks

        super().__init__(
            command_prefix="!",  # Prefix commands disabled, using slash commands
            intents=intents,
            help_command=None,
        )

    @property
    def guild(self) -> Optional[discord.Guild]:
        """Get the configured guild."""
        if self._guild is None and self.settings.DISCORD_GUILD_ID:
            self._guild = self.get_guild(self.settings.DISCORD_GUILD_ID)
        return self._guild

    @property
    def uptime(self) -> Optional[float]:
        """Get bot uptime in seconds."""
        if self.start_time:
            return (datetime.utcnow() - self.start_time).total_seconds()
        return None

    async def setup_hook(self) -> None:
        """Called when the bot is starting up."""
        logger.info("Setting up PB HERO Bot...")

        # Load cogs
        await self._load_cogs()

        # Sync commands to the configured guild only
        if self.settings.DISCORD_GUILD_ID:
            guild_obj = discord.Object(id=self.settings.DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)
            logger.info("Commands synced to guild %d", self.settings.DISCORD_GUILD_ID)

    async def _load_cogs(self) -> None:
        """Load all bot cogs."""
        cog_modules = [
            "app.bot.cogs.moderation",
            "app.bot.cogs.channel_policy",
            "app.bot.cogs.youtube",
            "app.bot.cogs.admin",
        ]

        for module in cog_modules:
            try:
                await self.load_extension(module)
                logger.info("Loaded cog: %s", module)
            except Exception as e:
                logger.error("Failed to load cog %s: %s", module, str(e))

    async def on_ready(self) -> None:
        """Called when the bot is connected and ready."""
        self.start_time = datetime.utcnow()
        self._guild = self.get_guild(self.settings.DISCORD_GUILD_ID)

        if self._guild:
            logger.info("✅ PB HERO Bot connected to: %s (ID: %d)", self._guild.name, self._guild.id)
        else:
            logger.error("❌ Could not find configured guild: %d", self.settings.DISCORD_GUILD_ID)
            logger.error("Make sure the bot is invited to the server and DISCORD_GUILD_ID is correct")

        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="PB HERO Server"
            ),
            status=discord.Status.online,
        )

        # Initialize moderation engine
        self.moderation_engine = ModerationEngine(self, self.settings.DISCORD_GUILD_ID)
        await self.moderation_engine.refresh_cache()
        logger.info("Moderation engine initialized")

        # Start YouTube scheduler
        self.youtube_scheduler = YouTubeScheduler(self)
        await self.youtube_scheduler.start()
        logger.info("YouTube scheduler started")

        logger.info("PB HERO Bot is ready!")

    async def on_message(self, message: discord.Message) -> None:
        """Process messages for policy enforcement."""
        # Only process messages from the configured guild
        if not message.guild or message.guild.id != self.settings.DISCORD_GUILD_ID:
            return

        # Skip bot messages
        if message.author.bot:
            return

        # Run moderation engine
        if self.moderation_engine:
            violation = await self.moderation_engine.process_message(message)
            if violation:
                await self.moderation_engine.handle_violation(message, violation)
                return  # Don't process commands for violated messages

        # Process commands
        await self.process_commands(message)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Leave any guild that isn't the configured one."""
        if guild.id != self.settings.DISCORD_GUILD_ID:
            logger.warning("Joined unauthorized guild %s (%d), leaving...", guild.name, guild.id)
            await guild.leave()

    async def close(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down PB HERO Bot...")

        if self.youtube_scheduler:
            await self.youtube_scheduler.stop()

        await super().close()
        logger.info("PB HERO Bot shut down complete")
