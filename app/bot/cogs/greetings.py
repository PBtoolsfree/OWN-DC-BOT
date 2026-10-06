"""
PB HERO Server Greetings Cog.

Listens for member joins and leaves and delegates to GreetingService.
"""

import logging
import discord
from discord.ext import commands
from app.greetings.service import get_greeting_service

logger = logging.getLogger("pbhero.bot.greetings")


class GreetingsCog(commands.Cog, name="Greetings"):
    """Server greetings event handler cog."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = get_greeting_service(bot)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Called when a member joins the guild."""
        try:
            await self.service.handle_member_join(member)
        except Exception as e:
            logger.error("Error handling on_member_join for %s: %s", member, e, exc_info=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Called when a member leaves the guild (cached member event)."""
        guild_id = getattr(member.guild, "id", None) if getattr(member, "guild", None) else None
        user_id = getattr(member, "id", None)
        logger.info("[INFO] Member leave received: user_id=%s guild_id=%s (source=on_member_remove, Goodbye event received)", user_id, guild_id)
        try:
            await self.service.handle_member_leave(member, guild_id=guild_id)
        except Exception:
            logger.exception("Unhandled error in goodbye pipeline for member %s (on_member_remove)", member)

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent):
        """Called when a member leaves the guild (raw gateway event, works even if uncached)."""
        user = payload.user
        guild_id = payload.guild_id
        user_id = getattr(user, "id", "unknown")
        logger.info("[INFO] Member leave received: user_id=%s guild_id=%s (source=on_raw_member_remove, Goodbye event received)", user_id, guild_id)
        try:
            await self.service.handle_raw_member_leave(payload)
        except Exception:
            logger.exception("Unhandled error in goodbye pipeline for user %s (on_raw_member_remove)", getattr(payload, "user", "?"))


async def setup(bot: commands.Bot):
    await bot.add_cog(GreetingsCog(bot))
