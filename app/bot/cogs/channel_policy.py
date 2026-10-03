"""
PB HERO Channel Policy Cog.

Commands for managing channel policies via Discord commands.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.permissions import admin_only, guild_only
from app.config import get_settings

logger = logging.getLogger("pbhero.bot")
settings = get_settings()


class ChannelPolicyCog(commands.Cog, name="Channel Policy"):
    """Channel policy management commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="policy", description="View the policy for a channel")
    @app_commands.describe(channel="The channel to check")
    @guild_only()
    @admin_only()
    async def policy_view(self, interaction: discord.Interaction,
                          channel: discord.TextChannel = None):
        """View channel policy."""
        target_channel = channel or interaction.channel

        from app.database.engine import get_session_direct
        from app.database.repositories import ChannelPolicyRepo

        session = await get_session_direct()
        try:
            policy = await ChannelPolicyRepo.get_for_channel(session, target_channel.id)
            if not policy:
                return await interaction.response.send_message(
                    f"No policy configured for {target_channel.mention}. All content is allowed.",
                    ephemeral=True,
                )

            embed = discord.Embed(
                title=f"📋 Policy for #{target_channel.name}",
                color=0x3498DB,
            )

            def icon(val):
                v = val.value if hasattr(val, 'value') else str(val)
                if v == "allow":
                    return "✅"
                elif v == "deny":
                    return "❌"
                return "↩️"

            embed.add_field(name="Content", value="\n".join([
                f"{icon(policy.allow_text)} Text",
                f"{icon(policy.allow_links)} Links",
                f"{icon(policy.allow_images)} Images",
                f"{icon(policy.allow_videos)} Videos",
                f"{icon(policy.allow_files)} Files",
                f"{icon(policy.allow_stickers)} Stickers",
            ]), inline=True)

            embed.add_field(name="Mentions", value="\n".join([
                f"{icon(policy.allow_everyone)} @everyone",
                f"{icon(policy.allow_here)} @here",
                f"{icon(policy.allow_role_mentions)} Role mentions",
                f"{icon(policy.allow_user_mentions)} User mentions",
            ]), inline=True)

            embed.add_field(
                name="Status",
                value=f"{'🟢 Enabled' if policy.enabled else '🔴 Disabled'}",
                inline=True,
            )

            if policy.preset_name:
                embed.set_footer(text=f"Preset: {policy.preset_name}")

            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            await session.close()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ChannelPolicyCog(bot))
