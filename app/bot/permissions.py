"""
PB HERO Bot Permission Checks.

Guild-scoped permission verification for the single-server architecture.
"""

import json
import logging
from functools import wraps
from typing import Optional

import discord
from discord import app_commands

from app.config import get_settings
from app.database.engine import get_session_direct
from app.database.repositories import ServerConfigRepo

logger = logging.getLogger("pbhero.bot")

settings = get_settings()


def guild_only():
    """Decorator to ensure command runs only in the configured guild."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return False
        if interaction.guild.id != settings.DISCORD_GUILD_ID:
            await interaction.response.send_message("❌ This bot is not configured for this server.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


def moderator_only():
    """Decorator to ensure user has moderator permissions."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or interaction.guild.id != settings.DISCORD_GUILD_ID:
            await interaction.response.send_message("❌ Not available here.", ephemeral=True)
            return False

        member = interaction.user
        if isinstance(member, discord.Member):
            # Server owner
            if member.guild.owner_id == member.id:
                return True
            # Administrator permission
            if member.guild_permissions.administrator:
                return True
            # Check configured moderator roles
            session = await get_session_direct()
            try:
                mod_roles = await ServerConfigRepo.get_moderator_role_ids(session)
                admin_roles = await ServerConfigRepo.get_admin_role_ids(session)
                allowed_roles = set(mod_roles + admin_roles)

                for role in member.roles:
                    if role.id in allowed_roles:
                        return True
            finally:
                await session.close()

        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return False
    return app_commands.check(predicate)


def admin_only():
    """Decorator to ensure user has admin permissions."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or interaction.guild.id != settings.DISCORD_GUILD_ID:
            await interaction.response.send_message("❌ Not available here.", ephemeral=True)
            return False

        member = interaction.user
        if isinstance(member, discord.Member):
            if member.guild.owner_id == member.id:
                return True
            if member.guild_permissions.administrator:
                return True
            session = await get_session_direct()
            try:
                admin_roles = await ServerConfigRepo.get_admin_role_ids(session)
                for role in member.roles:
                    if role.id in set(admin_roles):
                        return True
            finally:
                await session.close()

        await interaction.response.send_message("❌ Admin access required.", ephemeral=True)
        return False
    return app_commands.check(predicate)


# Required bot permissions documentation
REQUIRED_PERMISSIONS = discord.Permissions(
    send_messages=True,
    embed_links=True,
    attach_files=True,
    read_message_history=True,
    manage_messages=True,  # For deleting policy violations
    moderate_members=True,  # For timeouts
    kick_members=True,
    ban_members=True,
    manage_channels=True,  # For channel locks/slowmode
    view_channel=True,
    add_reactions=True,
    use_external_emojis=True,
    manage_roles=True,  # For channel permission overrides
)


def get_invite_url(client_id: int) -> str:
    """Generate bot invite URL with required permissions."""
    return discord.utils.oauth_url(
        client_id,
        permissions=REQUIRED_PERMISSIONS,
        scopes=["bot", "applications.commands"],
    )
