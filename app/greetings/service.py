"""
Centralized Greeting Service for PB HERO Personal Discord Bot.

Handles member join and leave events, safe rendering, permission checking,
deduplication, error handling, and test dispatch.
"""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

import discord
from discord.ext import commands

from app.config import get_settings
from app.database.engine import get_session_direct
from app.database.models import ServerGreetingSettings
from app.database.repositories import ServerGreetingSettingsRepo
from app.greetings.templates import (
    DEFAULT_GOODBYE_DESCRIPTION,
    DEFAULT_GOODBYE_FOOTER,
    DEFAULT_GOODBYE_TITLE,
    DEFAULT_WELCOME_DESCRIPTION,
    DEFAULT_WELCOME_FOOTER,
    DEFAULT_WELCOME_TITLE,
    render_template,
)

logger = logging.getLogger("pbhero.greetings")
settings = get_settings()


class GreetingService:
    """Service managing welcome and goodbye notifications."""

    def __init__(self, bot: Optional[commands.Bot] = None):
        self.bot = bot
        self._recent_events: Dict[str, float] = {}  # key -> timestamp
        self._activities: List[Dict[str, Any]] = []
        self._stats_today: Dict[str, Any] = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "welcome": 0,
            "goodbye": 0,
        }

    def set_bot(self, bot: commands.Bot) -> None:
        """Update bot reference."""
        self.bot = bot

    def _get_today_counts(self) -> Dict[str, Any]:
        """Return and refresh daily greeting counters."""
        today_str = datetime.now(timezone.utc).date().isoformat()
        if self._stats_today.get("date") != today_str:
            self._stats_today = {
                "date": today_str,
                "welcome": 0,
                "goodbye": 0,
            }
        return self._stats_today

    def get_stats(self) -> Dict[str, int]:
        """Get greeting counts for current UTC day."""
        counts = self._get_today_counts()
        return {
            "welcome_sent_today": counts.get("welcome", 0),
            "goodbye_sent_today": counts.get("goodbye", 0),
        }

    def record_activity(
        self,
        event_type: str,
        username: str,
        user_id: str,
        channel_id: Optional[int],
        channel_name: str,
        status: str,
        error_message: Optional[str] = None,
        is_test: bool = False,
    ) -> Dict[str, Any]:
        """Record an activity log item in the ring buffer."""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "username": username,
            "user_id": str(user_id),
            "channel_id": str(channel_id) if channel_id else None,
            "channel_name": channel_name,
            "status": status,
            "error_message": error_message,
            "is_test": is_test,
        }
        self._activities.insert(0, entry)
        if len(self._activities) > 50:
            self._activities.pop()

        if status == "delivered" and not is_test:
            counts = self._get_today_counts()
            if event_type in counts:
                counts[event_type] += 1

        return entry

    def get_recent_activity(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent greeting delivery activities."""
        return self._activities[:limit]

    def _is_duplicate_event(
        self, event_type: str, guild_id: int, user_id: int, window_seconds: float = 60.0
    ) -> bool:
        """Check and record event deduplication key."""
        now = time.time()
        key = f"{event_type}:{guild_id}:{user_id}"

        # Clean up events older than 5 minutes
        stale_keys = [k for k, ts in self._recent_events.items() if now - ts > 300]
        for k in stale_keys:
            del self._recent_events[k]

        last_time = self._recent_events.get(key)
        if last_time and (now - last_time) < window_seconds:
            return True

        self._recent_events[key] = now
        return False

    def check_channel_permissions(
        self, channel: Optional[discord.abc.GuildChannel], requires_embed: bool = True
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate channel availability and bot permissions."""
        if not channel:
            return False, {
                "status": "missing_channel",
                "can_view": False,
                "can_send": False,
                "can_embed": False,
                "warning": "Selected channel is unavailable.",
            }

        guild = channel.guild
        me = guild.me if guild else None
        if not me:
            return False, {
                "status": "error",
                "can_view": False,
                "can_send": False,
                "can_embed": False,
                "warning": "Bot member object unavailable.",
            }

        perms = channel.permissions_for(me)
        can_view = bool(perms.view_channel)
        can_send = bool(perms.send_messages)
        can_embed = bool(perms.embed_links)

        warnings = []
        if not can_view:
            warnings.append("Missing 'View Channel' permission")
        if not can_send:
            warnings.append("Missing 'Send Messages' permission")
        if requires_embed and not can_embed:
            warnings.append("Missing 'Embed Links' permission")

        warning_str = "; ".join(warnings) if warnings else None
        is_valid = can_view and can_send and (not requires_embed or can_embed)

        return is_valid, {
            "status": "ok" if is_valid else "permission_denied",
            "channel_name": getattr(channel, "name", str(channel.id)),
            "can_view": can_view,
            "can_send": can_send,
            "can_embed": can_embed,
            "warning": warning_str,
        }

    def render_welcome_message(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
        """Render welcome message content, embed, and allowed mentions."""
        guild = member.guild
        created_str = (
            member.created_at.strftime("%Y-%m-%d")
            if getattr(member, "created_at", None)
            else "Unknown"
        )
        joined_str = (
            member.joined_at.strftime("%Y-%m-%d %H:%M:%S")
            if getattr(member, "joined_at", None)
            else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        )

        context = {
            "username": member.name,
            "display_name": member.display_name,
            "user_mention": member.mention if not is_test else f"@{member.name}",
            "user_id": str(member.id),
            "server_name": guild.name,
            "server_id": str(guild.id),
            "member_count": str(guild.member_count or 1),
            "account_created": created_str,
            "joined_at": joined_str,
        }

        title_raw = config.welcome_title or DEFAULT_WELCOME_TITLE
        desc_raw = config.welcome_description or DEFAULT_WELCOME_DESCRIPTION
        footer_raw = config.welcome_footer or DEFAULT_WELCOME_FOOTER

        if is_test:
            title_raw = f"?? TEST WELCOME ? {title_raw}"

        allow_mass = bool(config.allow_mass_mentions)
        title = render_template(title_raw, context, allow_mass)
        desc = render_template(desc_raw, context, allow_mass)
        footer = render_template(footer_raw, context, allow_mass)

        # Mentions safety: never ping @everyone unless mass mentions enabled
        # If test message, never ping real users
        allowed_mentions = discord.AllowedMentions(
            everyone=allow_mass,
            roles=allow_mass,
            users=bool(config.welcome_mention_user and not is_test),
        )

        if not config.welcome_use_embed:
            # Plain text message
            content_parts = []
            if config.welcome_mention_user and not is_test:
                content_parts.append(member.mention)
            if title:
                content_parts.append(f"**{title}**")
            if desc:
                content_parts.append(desc)
            if footer:
                content_parts.append(f"_{footer}_")
            return "\n\n".join(content_parts), None, allowed_mentions

        embed = discord.Embed(
            title=title,
            description=desc,
            color=0x5865F2,
        )

        if config.welcome_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)

        if config.welcome_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)

        if footer:
            icon_url = guild.icon.url if (config.welcome_show_server_icon and guild.icon) else None
            embed.set_footer(text=footer, icon_url=icon_url)

        content = member.mention if (config.welcome_mention_user and not is_test) else None
        return content, embed, allowed_mentions

    def render_goodbye_message(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
        """Render goodbye message content, embed, and allowed mentions."""
        guild = member.guild
        left_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        context = {
            "username": member.name,
            "display_name": member.display_name,
            "user_id": str(member.id),
            "server_name": guild.name,
            "server_id": str(guild.id),
            "member_count": str(guild.member_count or 1),
            "left_at": left_str,
        }

        title_raw = config.goodbye_title or DEFAULT_GOODBYE_TITLE
        desc_raw = config.goodbye_description or DEFAULT_GOODBYE_DESCRIPTION
        footer_raw = config.goodbye_footer or DEFAULT_GOODBYE_FOOTER

        if is_test:
            title_raw = f"?? TEST GOODBYE ? {title_raw}"

        allow_mass = bool(config.allow_mass_mentions)
        title = render_template(title_raw, context, allow_mass)
        desc = render_template(desc_raw, context, allow_mass)
        footer = render_template(footer_raw, context, allow_mass)

        # For Goodbye: do not ping @everyone. User mention optional.
        allowed_mentions = discord.AllowedMentions(
            everyone=allow_mass,
            roles=allow_mass,
            users=bool(config.goodbye_mention_user and not is_test),
        )

        if not config.goodbye_use_embed:
            content_parts = []
            if config.goodbye_mention_user and not is_test:
                content_parts.append(f"<@{member.id}>")
            if title:
                content_parts.append(f"**{title}**")
            if desc:
                content_parts.append(desc)
            if footer:
                content_parts.append(f"_{footer}_")
            return "\n\n".join(content_parts), None, allowed_mentions

        embed = discord.Embed(
            title=title,
            description=desc,
            color=0xED4245,
        )

        if config.goodbye_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)

        if config.goodbye_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)

        if footer:
            icon_url = guild.icon.url if (config.goodbye_show_server_icon and guild.icon) else None
            embed.set_footer(text=footer, icon_url=icon_url)

        content = f"<@{member.id}>" if (config.goodbye_mention_user and not is_test) else None
        return content, embed, allowed_mentions

    async def send_greeting(
        self,
        channel: discord.abc.GuildChannel,
        content: Optional[str],
        embed: Optional[discord.Embed],
        allowed_mentions: discord.AllowedMentions,
    ) -> None:
        """Send greeting message safely to Discord channel."""
        if not hasattr(channel, "send"):
            raise ValueError(f"Channel {getattr(channel, 'name', channel)} cannot receive messages")

        await channel.send(
            content=content,
            embed=embed,
            allowed_mentions=allowed_mentions,
        )

    async def handle_member_join(self, member: discord.Member) -> None:
        """Handle member join event."""
        # 1. Enforce configured single server
        if not member.guild or member.guild.id != settings.DISCORD_GUILD_ID:
            return

        # 2. Duplicate protection
        if self._is_duplicate_event("welcome", member.guild.id, member.id):
            logger.warning(
                "Duplicate join event ignored for %s (%s) in guild %s",
                member,
                member.id,
                member.guild.id,
            )
            return

        # 3. Read configuration from database
        session = await get_session_direct()
        try:
            config = await ServerGreetingSettingsRepo.get_or_create(session, member.guild.id)
            await session.commit()
        except Exception as e:
            logger.error("Failed to read greeting settings: %s", e)
            return
        finally:
            await session.close()

        # 4. Check if welcome system is enabled
        if not config.welcome_enabled:
            return

        if not config.welcome_channel_id:
            logger.warning("Welcome enabled but no channel configured for guild %s", member.guild.id)
            return

        # 5. Resolve channel and validate permissions
        channel = member.guild.get_channel(config.welcome_channel_id)
        is_valid, perm_telemetry = self.check_channel_permissions(
            channel, requires_embed=bool(config.welcome_use_embed)
        )
        if not is_valid:
            warn = perm_telemetry.get("warning") or "Invalid channel or permissions"
            logger.error("Cannot send welcome message: %s", warn)
            self.record_activity(
                event_type="welcome",
                username=str(member),
                user_id=str(member.id),
                channel_id=config.welcome_channel_id,
                channel_name=perm_telemetry.get("channel_name") or "Unknown Channel",
                status="failed",
                error_message=warn,
            )
            return

        # 6. Render and send message
        try:
            content, embed, allowed_mentions = self.render_welcome_message(config, member)
            await self.send_greeting(channel, content, embed, allowed_mentions)
            self.record_activity(
                event_type="welcome",
                username=str(member),
                user_id=str(member.id),
                channel_id=channel.id,
                channel_name=channel.name,
                status="delivered",
            )
            logger.info("Sent welcome message for %s to #%s", member, channel.name)
        except Exception as e:
            logger.exception("Failed to send welcome message to Discord: %s", e)
            self.record_activity(
                event_type="welcome",
                username=str(member),
                user_id=str(member.id),
                channel_id=channel.id,
                channel_name=channel.name,
                status="failed",
                error_message=str(e),
            )

    async def handle_member_leave(self, member: discord.Member) -> None:
        """Handle member leave / remove event."""
        # 1. Enforce configured single server
        if not member.guild or member.guild.id != settings.DISCORD_GUILD_ID:
            return

        # 2. Duplicate protection
        if self._is_duplicate_event("goodbye", member.guild.id, member.id):
            logger.warning(
                "Duplicate leave event ignored for %s (%s) in guild %s",
                member,
                member.id,
                member.guild.id,
            )
            return

        # 3. Read configuration from database
        session = await get_session_direct()
        try:
            config = await ServerGreetingSettingsRepo.get_or_create(session, member.guild.id)
            await session.commit()
        except Exception as e:
            logger.error("Failed to read greeting settings: %s", e)
            return
        finally:
            await session.close()

        # 4. Check if goodbye system is enabled
        if not config.goodbye_enabled:
            return

        if not config.goodbye_channel_id:
            logger.warning("Goodbye enabled but no channel configured for guild %s", member.guild.id)
            return

        # 5. Resolve channel and validate permissions
        channel = member.guild.get_channel(config.goodbye_channel_id)
        is_valid, perm_telemetry = self.check_channel_permissions(
            channel, requires_embed=bool(config.goodbye_use_embed)
        )
        if not is_valid:
            warn = perm_telemetry.get("warning") or "Invalid channel or permissions"
            logger.error("Cannot send goodbye message: %s", warn)
            self.record_activity(
                event_type="goodbye",
                username=str(member),
                user_id=str(member.id),
                channel_id=config.goodbye_channel_id,
                channel_name=perm_telemetry.get("channel_name") or "Unknown Channel",
                status="failed",
                error_message=warn,
            )
            return

        # 6. Render and send message
        try:
            content, embed, allowed_mentions = self.render_goodbye_message(config, member)
            await self.send_greeting(channel, content, embed, allowed_mentions)
            self.record_activity(
                event_type="goodbye",
                username=str(member),
                user_id=str(member.id),
                channel_id=channel.id,
                channel_name=channel.name,
                status="delivered",
            )
            logger.info("Sent goodbye message for %s to #%s", member, channel.name)
        except Exception as e:
            logger.exception("Failed to send goodbye message to Discord: %s", e)
            self.record_activity(
                event_type="goodbye",
                username=str(member),
                user_id=str(member.id),
                channel_id=channel.id,
                channel_name=channel.name,
                status="failed",
                error_message=str(e),
            )

    async def send_test_message(self, greeting_type: str) -> Dict[str, Any]:
        """Dispatch a test welcome or goodbye message to the configured channel."""
        if not self.bot or not self.bot.is_ready():
            raise RuntimeError("Bot is currently offline. Cannot send test Discord message.")

        guild = self.bot.guild
        if not guild:
            raise RuntimeError(f"Configured guild {settings.DISCORD_GUILD_ID} not found.")

        session = await get_session_direct()
        try:
            config = await ServerGreetingSettingsRepo.get_or_create(session, guild.id)
            await session.commit()
        finally:
            await session.close()

        channel_id = (
            config.welcome_channel_id if greeting_type == "welcome" else config.goodbye_channel_id
        )
        if not channel_id:
            raise ValueError(f"No {greeting_type} channel configured. Please select a channel first.")

        channel = guild.get_channel(channel_id)
        if not channel:
            raise ValueError(
                f"Selected {greeting_type} channel is unavailable or was deleted from Discord."
            )

        requires_embed = (
            bool(config.welcome_use_embed)
            if greeting_type == "welcome"
            else bool(config.goodbye_use_embed)
        )
        is_valid, telemetry = self.check_channel_permissions(channel, requires_embed=requires_embed)
        if not is_valid:
            warn = telemetry.get("warning") or "Missing required permissions in target channel."
            raise PermissionError(warn)

        # Mock dummy member object for testing
        class DummyAvatar:
            url = (
                "https://cdn.discordapp.com/embed/avatars/0.png"
                if not (self.bot.user and self.bot.user.display_avatar)
                else self.bot.user.display_avatar.url
            )

        class DummyMember:
            def __init__(self, g):
                self.id = 123456789012345678
                self.name = "TestUser"
                self.display_name = "Test User"
                self.mention = "@TestUser"
                self.guild = g
                self.created_at = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
                self.joined_at = datetime.now(timezone.utc)
                self.display_avatar = DummyAvatar()

        dummy = DummyMember(guild)

        if greeting_type == "welcome":
            content, embed, allowed_mentions = self.render_welcome_message(
                config, dummy, is_test=True
            )
        else:
            content, embed, allowed_mentions = self.render_goodbye_message(
                config, dummy, is_test=True
            )

        await self.send_greeting(channel, content, embed, allowed_mentions)

        activity = self.record_activity(
            event_type=greeting_type,
            username="TestUser (Test)",
            user_id="123456789012345678",
            channel_id=channel.id,
            channel_name=channel.name,
            status="delivered",
            is_test=True,
        )

        return {
            "status": "ok",
            "message": f"?? Test {greeting_type} message successfully sent to #{channel.name}",
            "channel_id": str(channel.id),
            "channel_name": channel.name,
            "activity": activity,
        }


# Global singleton
_greeting_service: Optional[GreetingService] = None


def get_greeting_service(bot: Optional[commands.Bot] = None) -> GreetingService:
    """Get or initialize singleton GreetingService."""
    global _greeting_service
    if _greeting_service is None:
        _greeting_service = GreetingService(bot)
    elif bot is not None and _greeting_service.bot != bot:
        _greeting_service.set_bot(bot)
    return _greeting_service
