"""
Permanent reusable server invitation manager for PB HERO Personal Discord Bot.
"""

from datetime import datetime
import logging
from typing import Any, Dict, Optional, Tuple

import discord
from discord.ext import commands

from app.database.engine import get_session_direct
from app.database.models import ServerInviteSettings
from app.database.repositories import ServerInviteSettingsRepo

logger = logging.getLogger("pbhero.greetings.invites")


async def get_or_create_server_invite(
    bot: Optional[commands.Bot],
    guild_id: int,
    default_channel_id: Optional[int] = None,
) -> Tuple[Optional[str], Optional[ServerInviteSettings]]:
    """Read existing invite or generate if channel available."""
    session = await get_session_direct()
    try:
        invite_row = await ServerInviteSettingsRepo.get_or_create(session, guild_id)
        await session.commit()
    finally:
        await session.close()

    if invite_row.invite_url and invite_row.is_active:
        return invite_row.invite_url, invite_row

    if bot and bot.is_ready():
        guild = bot.guild
        if guild and (invite_row.invite_channel_id or default_channel_id):
            target_chan_id = invite_row.invite_channel_id or default_channel_id
            try:
                res = await generate_permanent_invite(bot, guild.id, target_chan_id)
                return res.get("invite_url"), invite_row
            except Exception as e:
                logger.warning("Auto invite creation notice: %s", e)

    return invite_row.invite_url, invite_row


async def generate_permanent_invite(
    bot: Optional[commands.Bot],
    guild_id: int,
    channel_id: int,
    unique: bool = False,
) -> Dict[str, Any]:
    """Generate a reusable permanent invite for the selected channel."""
    if not bot or not bot.is_ready():
        raise RuntimeError("Bot is offline. Cannot create Discord invite.")

    guild = bot.guild
    if not guild or guild.id != guild_id:
        raise ValueError(f"Guild {guild_id} not found or bot not connected.")

    channel = guild.get_channel(channel_id)
    if not channel or not hasattr(channel, "create_invite"):
        raise ValueError("Target channel unavailable or does not support invites.")

    me = guild.me
    if not me or not channel.permissions_for(me).create_instant_invite:
        raise PermissionError("Bot lacks 'Create Instant Invite' permission in target channel.")

    try:
        invite = await channel.create_invite(
            max_age=0,
            max_uses=0,
            temporary=False,
            unique=unique,
            reason="PB HERO Server Permanent Invite",
        )
    except Exception as e:
        logger.error("Discord rejected permanent invite creation: %s", e)
        session = await get_session_direct()
        try:
            await ServerInviteSettingsRepo.update(
                session,
                guild_id,
                verification_status="unavailable",
                verification_error=str(e),
            )
            await session.commit()
        finally:
            await session.close()
        raise RuntimeError(f"Discord invite generation failed: {e}")

    is_permanent = (invite.max_age == 0) and (invite.max_uses == 0)
    status = "permanent_active" if is_permanent else "active_expiring"
    error_msg = None if is_permanent else f"Discord assigned expiration: {invite.max_age}s"

    session = await get_session_direct()
    try:
        updated = await ServerInviteSettingsRepo.update(
            session,
            guild_id,
            invite_channel_id=channel.id,
            invite_code=invite.code,
            invite_url=invite.url,
            is_active=True,
            max_age=invite.max_age or 0,
            max_uses=invite.max_uses or 0,
            temporary=bool(invite.temporary),
            verification_status=status,
            verification_error=error_msg,
            last_verified_at=datetime.utcnow(),
        )
        await session.commit()
    finally:
        await session.close()

    return {
        "success": True,
        "invite_code": invite.code,
        "invite_url": invite.url,
        "channel_id": str(channel.id),
        "channel_name": channel.name,
        "is_permanent": is_permanent,
        "verification_status": status,
        "max_age": invite.max_age,
        "max_uses": invite.max_uses,
    }


async def verify_invite(bot: Optional[commands.Bot], guild_id: int) -> Dict[str, Any]:
    """Verify stored invite via Discord API."""
    session = await get_session_direct()
    try:
        invite_row = await ServerInviteSettingsRepo.get_or_create(session, guild_id)
        await session.commit()
    finally:
        await session.close()

    if not invite_row.invite_code:
        return {
            "status": "not_generated",
            "message": "No permanent invite has been generated yet.",
            "is_valid": False,
        }

    if not bot or not bot.is_ready():
        return {
            "status": invite_row.verification_status,
            "message": "Bot is offline; cannot contact Discord to verify invite.",
            "is_valid": False,
        }

    try:
        fetched = await bot.fetch_invite(invite_row.invite_code)
        if not fetched.guild or fetched.guild.id != guild_id:
            raise ValueError("Invite belongs to a different Discord guild.")

        guild_invite = None
        if bot and bot.guild:
            try:
                invites = await bot.guild.invites()
                guild_invite = next((inv for inv in invites if inv.code == invite_row.invite_code), None)
            except Exception:
                guild_invite = None

        if guild_invite is not None:
            is_perm = (guild_invite.max_age == 0) and (guild_invite.max_uses == 0)
            max_age = guild_invite.max_age
            max_uses = guild_invite.max_uses
        else:
            is_perm = (fetched.expires_at is None) and (fetched.max_age in (0, None)) and (fetched.max_uses in (0, None))
            max_age = 0 if is_perm else fetched.max_age
            max_uses = 0 if is_perm else fetched.max_uses

        status = "permanent_active" if is_perm else "active_expiring"
        err = None if is_perm else f"Invite has expiration (expires_at={getattr(fetched, 'expires_at', None)})"

        session = await get_session_direct()
        try:
            await ServerInviteSettingsRepo.update(
                session,
                guild_id,
                verification_status=status,
                verification_error=err,
                last_verified_at=datetime.utcnow(),
                is_active=True,
            )
            await session.commit()
        finally:
            await session.close()

        return {
            "status": status,
            "is_valid": True,
            "is_permanent": is_perm,
            "invite_url": fetched.url,
            "max_age": max_age,
            "max_uses": max_uses,
            "channel_name": getattr(fetched.channel, "name", None),
            "message": "Invite is verified and active." if is_perm else "Invite is active but has expiration.",
        }
    except Exception as e:
        logger.warning("Invite verification failed for %s: %s", invite_row.invite_code, e)
        status = "invalid"
        err_msg = str(e)

        session = await get_session_direct()
        try:
            await ServerInviteSettingsRepo.update(
                session,
                guild_id,
                verification_status=status,
                verification_error=err_msg,
                last_verified_at=datetime.utcnow(),
                is_active=False,
            )
            await session.commit()
        finally:
            await session.close()

        return {
            "status": status,
            "is_valid": False,
            "is_permanent": False,
            "message": f"Invite is invalid or expired: {err_msg}",
        }

