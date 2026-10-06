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
        try:
            guild_id = getattr(member.guild, "id", None) if getattr(member, "guild", None) else None
            logger.info("Goodbye event received: on_member_remove user=%s guild=%s", member.id, guild_id)
            await self.service.handle_member_leave(member, guild_id=guild_id)
        except Exception as e:
            logger.error("Error handling on_member_remove for %s: %s", member, e, exc_info=True)

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent):
        """Called when a member leaves the guild (raw gateway event, works even if uncached)."""
        try:
            user = payload.user
            guild_id = payload.guild_id
            user_id = getattr(user, "id", "unknown")
            logger.info("Goodbye event received: on_raw_member_remove user=%s guild=%s", user_id, guild_id)
            await self.service.handle_raw_member_leave(payload)
        except Exception as e:
            logger.error("Error handling on_raw_member_remove for user=%s: %s", getattr(payload, "user", "?"), e, exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GreetingsCog(bot))
