"""
Centralized Greeting Service for PB HERO Personal Discord Bot.

Handles member join and leave events, rules delivery, direct messages (DMs),
auto-role assignment, reusable permanent invite management, permission checking,
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
from app.database.repositories import (
    ServerGreetingSettingsRepo,
    ServerInviteSettingsRepo,
)
from app.greetings.invites import (
    generate_permanent_invite,
    get_or_create_server_invite,
    verify_invite,
)
from app.greetings.roles import assign_auto_role, get_guild_roles
from app.greetings.templates import (
    DEFAULT_GOODBYE_DESCRIPTION,
    DEFAULT_GOODBYE_DM_DESCRIPTION,
    DEFAULT_GOODBYE_DM_FOOTER,
    DEFAULT_GOODBYE_DM_TITLE,
    DEFAULT_GOODBYE_FOOTER,
    DEFAULT_GOODBYE_TITLE,
    DEFAULT_RULES_DESCRIPTION,
    DEFAULT_RULES_FOOTER,
    DEFAULT_RULES_TITLE,
    DEFAULT_WELCOME_DESCRIPTION,
    DEFAULT_WELCOME_DM_DESCRIPTION,
    DEFAULT_WELCOME_DM_FOOTER,
    DEFAULT_WELCOME_DM_TITLE,
    DEFAULT_WELCOME_FOOTER,
    DEFAULT_WELCOME_TITLE,
    build_rules_url,
    render_template,
)

logger = logging.getLogger("pbhero.greetings")
settings = get_settings()


class GreetingService:
    """Service managing welcome, goodbye, rules delivery, DMs, roles, and invites."""

    def __init__(self, bot: Optional[commands.Bot] = None):
        self.bot = bot
        self._recent_events: Dict[str, float] = {}
        self._activities: List[Dict[str, Any]] = []
        self._stats_today: Dict[str, Any] = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "welcome": 0,
            "goodbye": 0,
            "welcome_dm": 0,
            "goodbye_dm": 0,
            "rules": 0,
            "roles": 0,
            "dm_failures": 0,
        }

    def set_bot(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _get_today_counts(self) -> Dict[str, Any]:
        today_str = datetime.now(timezone.utc).date().isoformat()
        if self._stats_today.get("date") != today_str:
            self._stats_today = {
                "date": today_str,
                "welcome": 0,
                "goodbye": 0,
                "welcome_dm": 0,
                "goodbye_dm": 0,
                "rules": 0,
                "roles": 0,
                "dm_failures": 0,
            }
        return self._stats_today

    def get_stats(self) -> Dict[str, int]:
        counts = self._get_today_counts()
        return {
            "welcome_sent_today": counts.get("welcome", 0),
            "goodbye_sent_today": counts.get("goodbye", 0),
            "welcome_dms_today": counts.get("welcome_dm", 0),
            "goodbye_dms_today": counts.get("goodbye_dm", 0),
            "rules_delivered_today": counts.get("rules", 0),
            "roles_assigned_today": counts.get("roles", 0),
            "dm_failures_today": counts.get("dm_failures", 0),
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

        if not is_test:
            counts = self._get_today_counts()
            if status == "delivered":
                if event_type in ("welcome", "WELCOME_SENT"):
                    counts["welcome"] += 1
                elif event_type in ("goodbye", "GOODBYE_SENT"):
                    counts["goodbye"] += 1
                elif event_type in ("welcome_dm", "WELCOME_DM_SENT"):
                    counts["welcome_dm"] += 1
                elif event_type in ("goodbye_dm", "GOODBYE_DM_SENT"):
                    counts["goodbye_dm"] += 1
                elif event_type in ("rules", "RULES_SENT"):
                    counts["rules"] += 1
                elif event_type in ("role", "ROLE_ASSIGNED"):
                    counts["roles"] += 1
            elif status == "failed" and "DM" in event_type.upper():
                counts["dm_failures"] += 1

        return entry

    def get_recent_activity(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._activities[:limit]

    def _is_duplicate_event(
        self, event_type: str, guild_id: int, user_id: int, window_seconds: float = 60.0
    ) -> bool:
        now = time.time()
        key = f"{event_type}:{guild_id}:{user_id}"

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

    async def get_or_create_server_invite(
        self, guild_id: int, default_channel_id: Optional[int] = None
    ) -> Tuple[Optional[str], Optional[Any]]:
        return await get_or_create_server_invite(self.bot, guild_id, default_channel_id)

    async def generate_permanent_invite(
        self, guild_id: int, channel_id: int, unique: bool = False
    ) -> Dict[str, Any]:
        res = await generate_permanent_invite(self.bot, guild_id, channel_id, unique=unique)
        self.record_activity(
            event_type="INVITE_CREATED",
            username="System",
            user_id="0",
            channel_id=channel_id,
            channel_name=res.get("channel_name", "channel"),
            status="delivered",
            error_message=None if res.get("is_permanent") else "Expiring invite created",
        )
        return res

    async def verify_invite(self, guild_id: int) -> Dict[str, Any]:
        res = await verify_invite(self.bot, guild_id)
        if res.get("is_valid"):
            self.record_activity(
                event_type="INVITE_VERIFIED",
                username="System",
                user_id="0",
                channel_id=None,
                channel_name=res.get("channel_name", "Invite Channel"),
                status="delivered",
            )
        else:
            self.record_activity(
                event_type="INVITE_INVALID",
                username="System",
                user_id="0",
                channel_id=None,
                channel_name="Invite Channel",
                status="failed",
                error_message=res.get("message"),
            )
        return res

    def get_guild_roles(self, guild_id: int) -> List[Dict[str, Any]]:
        return get_guild_roles(self.bot, guild_id)

    async def assign_auto_role(self, member: discord.Member, role_id: int) -> bool:
        ok, err = await assign_auto_role(member, role_id)
        guild = member.guild
        role = guild.get_role(role_id) if guild else None
        role_name = role.name if role else str(role_id)
        if ok:
            self.record_activity(
                event_type="ROLE_ASSIGNED",
                username=str(member),
                user_id=str(member.id),
                channel_id=None,
                channel_name=f"@{role_name}",
                status="delivered",
            )
        else:
            self.record_activity(
                event_type="ROLE_ASSIGN_FAILED",
                username=str(member),
                user_id=str(member.id),
                channel_id=None,
                channel_name=f"@{role_name}",
                status="failed",
                error_message=err,
            )
        return ok
    # ========================================================
    # Rendering Helpers
    # ========================================================

    def render_welcome_message(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        invite_url: Optional[str] = None,
        rules_url: Optional[str] = None,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
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
            "invite_url": invite_url,
            "rules_url": rules_url or build_rules_url(guild.id, config.rules_channel_id),
        }

        title_raw = config.welcome_title or DEFAULT_WELCOME_TITLE
        desc_raw = config.welcome_description or DEFAULT_WELCOME_DESCRIPTION
        footer_raw = config.welcome_footer or DEFAULT_WELCOME_FOOTER

        if is_test:
            title_raw = f"🧪 TEST WELCOME • {title_raw}"

        allow_mass = bool(config.allow_mass_mentions)
        title = render_template(title_raw, context, allow_mass)
        desc = render_template(desc_raw, context, allow_mass)
        footer = render_template(footer_raw, context, allow_mass)

        allowed_mentions = discord.AllowedMentions(
            everyone=allow_mass,
            roles=allow_mass,
            users=bool(config.welcome_mention_user and not is_test),
        )

        if not config.welcome_use_embed:
            parts = []
            if config.welcome_mention_user and not is_test:
                parts.append(member.mention)
            if title:
                parts.append(f"**{title}**")
            if desc:
                parts.append(desc)
            if footer:
                parts.append(f"_{footer}_")
            return "\n\n".join(parts), None, allowed_mentions

        embed = discord.Embed(title=title, description=desc, color=0x5865F2)
        if config.welcome_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        if config.welcome_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)
        if footer:
            icon_url = guild.icon.url if (config.welcome_show_server_icon and guild.icon) else None
            embed.set_footer(text=footer, icon_url=icon_url)

        content = member.mention if (config.welcome_mention_user and not is_test) else None
        return content, embed, allowed_mentions

    def render_welcome_dm(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        invite_url: Optional[str] = None,
        rules_url: Optional[str] = None,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
        guild = member.guild
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
            "joined_at": joined_str,
            "invite_url": invite_url,
            "rules_url": rules_url or build_rules_url(guild.id, config.rules_channel_id),
        }

        title_raw = config.welcome_dm_title or DEFAULT_WELCOME_DM_TITLE
        desc_raw = config.welcome_dm_description or DEFAULT_WELCOME_DM_DESCRIPTION
        footer_raw = config.welcome_dm_footer or DEFAULT_WELCOME_DM_FOOTER

        if is_test:
            title_raw = f"🧪 TEST WELCOME DM • {title_raw}"

        allow_mass = bool(config.allow_mass_mentions)
        title = render_template(title_raw, context, allow_mass)
        desc = render_template(desc_raw, context, allow_mass)
        footer = render_template(footer_raw, context, allow_mass)

        allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=bool(not is_test))

        if not config.welcome_dm_use_embed:
            parts = [p for p in (f"**{title}**" if title else "", desc, f"_{footer}_" if footer else "") if p]
            return "\n\n".join(parts), None, allowed_mentions

        embed = discord.Embed(title=title, description=desc, color=0x57F287)
        if config.welcome_dm_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        if config.welcome_dm_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)
        if footer:
            icon_url = guild.icon.url if (config.welcome_dm_show_server_icon and guild.icon) else None
            embed.set_footer(text=footer, icon_url=icon_url)

        return None, embed, allowed_mentions

    def render_goodbye_message(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        invite_url: Optional[str] = None,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
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
            "invite_url": invite_url,
        }

        title_raw = config.goodbye_title or DEFAULT_GOODBYE_TITLE
        desc_raw = config.goodbye_description or DEFAULT_GOODBYE_DESCRIPTION
        footer_raw = config.goodbye_footer or DEFAULT_GOODBYE_FOOTER

        if is_test:
            title_raw = f"🧪 TEST GOODBYE • {title_raw}"

        allow_mass = bool(config.allow_mass_mentions)
        title = render_template(title_raw, context, allow_mass)
        desc = render_template(desc_raw, context, allow_mass)
        footer = render_template(footer_raw, context, allow_mass)

        allowed_mentions = discord.AllowedMentions(
            everyone=allow_mass,
            roles=allow_mass,
            users=bool(config.goodbye_mention_user and not is_test),
        )

        if not config.goodbye_use_embed:
            parts = []
            if config.goodbye_mention_user and not is_test:
                parts.append(f"<@{member.id}>")
            if title:
                parts.append(f"**{title}**")
            if desc:
                parts.append(desc)
            if footer:
                parts.append(f"_{footer}_")
            return "\n\n".join(parts), None, allowed_mentions

        embed = discord.Embed(title=title, description=desc, color=0xED4245)
        if config.goodbye_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        if config.goodbye_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)
        if footer:
            icon_url = guild.icon.url if (config.goodbye_show_server_icon and guild.icon) else None
            embed.set_footer(text=footer, icon_url=icon_url)

        content = f"<@{member.id}>" if (config.goodbye_mention_user and not is_test) else None
        return content, embed, allowed_mentions

    def render_goodbye_dm(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        invite_url: Optional[str] = None,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
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
            "invite_url": invite_url,
        }

        title_raw = config.goodbye_dm_title or DEFAULT_GOODBYE_DM_TITLE
        desc_raw = config.goodbye_dm_description or DEFAULT_GOODBYE_DM_DESCRIPTION
        footer_raw = config.goodbye_dm_footer or DEFAULT_GOODBYE_DM_FOOTER

        if is_test:
            title_raw = f"🧪 TEST GOODBYE DM • {title_raw}"

        allow_mass = bool(config.allow_mass_mentions)
        title = render_template(title_raw, context, allow_mass)
        desc = render_template(desc_raw, context, allow_mass)
        footer = render_template(footer_raw, context, allow_mass)

        allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=bool(not is_test))

        if not config.goodbye_dm_use_embed:
            parts = [p for p in (f"**{title}**" if title else "", desc, f"_{footer}_" if footer else "") if p]
            return "\n\n".join(parts), None, allowed_mentions

        embed = discord.Embed(title=title, description=desc, color=0xFEE75C)
        if config.goodbye_dm_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        if config.goodbye_dm_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)
        if footer:
            icon_url = guild.icon.url if (config.goodbye_dm_show_server_icon and guild.icon) else None
            embed.set_footer(text=footer, icon_url=icon_url)

        return None, embed, allowed_mentions

    def render_rules_message(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        rules_url: Optional[str] = None,
        invite_url: Optional[str] = None,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
        guild = member.guild
        context = {
            "username": member.name,
            "display_name": member.display_name,
            "user_mention": member.mention if not is_test else f"@{member.name}",
            "user_id": str(member.id),
            "server_name": guild.name,
            "server_id": str(guild.id),
            "member_count": str(guild.member_count or 1),
            "rules_url": rules_url or build_rules_url(guild.id, config.rules_channel_id),
            "invite_url": invite_url,
        }

        source = config.rules_source or "rules_channel"
        title_raw = config.rules_title or DEFAULT_RULES_TITLE
        desc_raw = config.rules_description or DEFAULT_RULES_DESCRIPTION
        footer_raw = config.rules_footer or DEFAULT_RULES_FOOTER

        allow_mass = bool(config.allow_mass_mentions)
        title = render_template(title_raw, context, allow_mass)
        desc = render_template(desc_raw, context, allow_mass)
        footer = render_template(footer_raw, context, allow_mass)

        if source == "rules_channel":
            channel_link = context["rules_url"]
            content = f"📜 **SERVER RULES**\n\nPlease read our server rules here:\n{channel_link}"
            return content, None, discord.AllowedMentions.none()

        embed = discord.Embed(title=title, description=desc, color=0xEB459E)
        if source == "both" and context["rules_url"] != "[Rules unavailable]":
            embed.add_field(
                name="Official Rules Channel",
                value=f"Please visit: {context['rules_url']}",
                inline=False,
            )
        if footer:
            embed.set_footer(text=footer)

        return None, embed, discord.AllowedMentions.none()
    # ========================================================
    # Safe Dispatch Mechanisms
    # ========================================================

    async def send_greeting(
        self,
        channel: discord.abc.GuildChannel,
        content: Optional[str],
        embed: Optional[discord.Embed],
        allowed_mentions: discord.AllowedMentions,
    ) -> None:
        if not hasattr(channel, "send"):
            raise ValueError(f"Channel {getattr(channel, 'name', channel)} cannot receive messages")
        await channel.send(content=content, embed=embed, allowed_mentions=allowed_mentions)

    async def send_dm_safe(
        self,
        user: discord.abc.User,
        content: Optional[str],
        embed: Optional[discord.Embed],
        allowed_mentions: discord.AllowedMentions,
    ) -> None:
        if not hasattr(user, "send"):
            raise ValueError(f"Target user {user} cannot receive direct messages")
        await user.send(content=content, embed=embed, allowed_mentions=allowed_mentions)

    # ========================================================
    # Event Handlers (Join & Leave)
    # ========================================================

    async def handle_member_join(self, member: discord.Member) -> None:
        if not member.guild or member.guild.id != settings.DISCORD_GUILD_ID:
            return

        if self._is_duplicate_event("welcome", member.guild.id, member.id):
            logger.warning("Duplicate join event ignored for %s in %s", member, member.guild.id)
            return

        session = await get_session_direct()
        try:
            config = await ServerGreetingSettingsRepo.get_or_create(session, member.guild.id)
            invite_row = await ServerInviteSettingsRepo.get_or_create(session, member.guild.id)
            await session.commit()
        except Exception as e:
            logger.error("Failed to load settings on member join: %s", e)
            return
        finally:
            await session.close()

        invite_url = invite_row.invite_url if (invite_row and invite_row.is_active) else None
        rules_url = build_rules_url(member.guild.id, config.rules_channel_id)

        # 1. Auto Role Assignment
        if config.auto_role_enabled and config.auto_role_id:
            try:
                await self.assign_auto_role(member, config.auto_role_id)
            except Exception as e:
                logger.warning("Auto role assignment error for %s: %s", member, e)

        # 2. Public Welcome Message
        if config.welcome_enabled and config.welcome_channel_id:
            channel = member.guild.get_channel(config.welcome_channel_id)
            is_valid, perm_telemetry = self.check_channel_permissions(
                channel, requires_embed=bool(config.welcome_use_embed)
            )
            if is_valid and channel:
                try:
                    content, embed, mentions = self.render_welcome_message(
                        config, member, invite_url=invite_url, rules_url=rules_url
                    )
                    await self.send_greeting(channel, content, embed, mentions)
                    self.record_activity(
                        event_type="WELCOME_SENT",
                        username=str(member),
                        user_id=str(member.id),
                        channel_id=channel.id,
                        channel_name=channel.name,
                        status="delivered",
                    )
                    logger.info("Public welcome delivered for %s to #%s", member, channel.name)
                except Exception as e:
                    logger.exception("Public welcome send failed: %s", e)
                    self.record_activity(
                        event_type="WELCOME_SENT",
                        username=str(member),
                        user_id=str(member.id),
                        channel_id=channel.id,
                        channel_name=channel.name,
                        status="failed",
                        error_message=str(e),
                    )
            else:
                warn = perm_telemetry.get("warning") or "Target channel unavailable"
                self.record_activity(
                    event_type="WELCOME_SENT",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=config.welcome_channel_id,
                    channel_name=perm_telemetry.get("channel_name") or "Channel",
                    status="failed",
                    error_message=warn,
                )

        # 3. Welcome Direct Message (DM)
        if config.welcome_dm_enabled:
            try:
                content, embed, mentions = self.render_welcome_dm(
                    config, member, invite_url=invite_url, rules_url=rules_url
                )
                await self.send_dm_safe(member, content, embed, mentions)
                self.record_activity(
                    event_type="WELCOME_DM_SENT",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=None,
                    channel_name="Direct Message",
                    status="delivered",
                )
                logger.info("Welcome DM sent to %s", member)
            except discord.Forbidden:
                logger.info("Welcome DM failed for %s: DM unavailable", member)
                self.record_activity(
                    event_type="WELCOME_DM_FAILED",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=None,
                    channel_name="Direct Message",
                    status="failed",
                    error_message="DM unavailable",
                )
            except Exception as e:
                logger.warning("Welcome DM unexpected error for %s: %s", member, e)
                self.record_activity(
                    event_type="WELCOME_DM_FAILED",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=None,
                    channel_name="Direct Message",
                    status="failed",
                    error_message="DM unavailable",
                )

        # 4. Rules Delivery
        if config.rules_delivery_enabled:
            try:
                content, embed, mentions = self.render_rules_message(
                    config, member, rules_url=rules_url, invite_url=invite_url
                )
                await self.send_dm_safe(member, content, embed, mentions)
                self.record_activity(
                    event_type="RULES_SENT",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=None,
                    channel_name="Direct Message",
                    status="delivered",
                )
                logger.info("Rules delivered to %s", member)
            except discord.Forbidden:
                logger.info("Rules DM unavailable for %s", member)
            except Exception as e:
                logger.warning("Rules delivery error for %s: %s", member, e)

    async def handle_member_leave(self, member: discord.Member) -> None:
        if not member.guild or member.guild.id != settings.DISCORD_GUILD_ID:
            return

        if self._is_duplicate_event("goodbye", member.guild.id, member.id):
            logger.warning("Duplicate leave event ignored for %s in %s", member, member.guild.id)
            return

        session = await get_session_direct()
        try:
            config = await ServerGreetingSettingsRepo.get_or_create(session, member.guild.id)
            invite_row = await ServerInviteSettingsRepo.get_or_create(session, member.guild.id)
            await session.commit()
        except Exception as e:
            logger.error("Failed to load settings on member leave: %s", e)
            return
        finally:
            await session.close()

        invite_url = invite_row.invite_url if (invite_row and invite_row.is_active) else None

        # 1. Public Goodbye
        if config.goodbye_enabled and config.goodbye_channel_id:
            channel = member.guild.get_channel(config.goodbye_channel_id)
            is_valid, perm_telemetry = self.check_channel_permissions(
                channel, requires_embed=bool(config.goodbye_use_embed)
            )
            if is_valid and channel:
                try:
                    content, embed, mentions = self.render_goodbye_message(
                        config, member, invite_url=invite_url
                    )
                    await self.send_greeting(channel, content, embed, mentions)
                    self.record_activity(
                        event_type="GOODBYE_SENT",
                        username=str(member),
                        user_id=str(member.id),
                        channel_id=channel.id,
                        channel_name=channel.name,
                        status="delivered",
                    )
                    logger.info("Public goodbye delivered for %s to #%s", member, channel.name)
                except Exception as e:
                    logger.exception("Public goodbye send failed: %s", e)
                    self.record_activity(
                        event_type="GOODBYE_SENT",
                        username=str(member),
                        user_id=str(member.id),
                        channel_id=channel.id,
                        channel_name=channel.name,
                        status="failed",
                        error_message=str(e),
                    )
            else:
                warn = perm_telemetry.get("warning") or "Target channel unavailable"
                self.record_activity(
                    event_type="GOODBYE_SENT",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=config.goodbye_channel_id,
                    channel_name=perm_telemetry.get("channel_name") or "Channel",
                    status="failed",
                    error_message=warn,
                )

        # 2. Goodbye Direct Message (DM)
        if config.goodbye_dm_enabled:
            try:
                content, embed, mentions = self.render_goodbye_dm(
                    config, member, invite_url=invite_url
                )
                await self.send_dm_safe(member, content, embed, mentions)
                self.record_activity(
                    event_type="GOODBYE_DM_SENT",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=None,
                    channel_name="Direct Message",
                    status="delivered",
                )
                logger.info("Goodbye DM sent to %s", member)
            except discord.Forbidden:
                logger.info("Goodbye DM failed for %s: DM unavailable", member)
                self.record_activity(
                    event_type="GOODBYE_DM_FAILED",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=None,
                    channel_name="Direct Message",
                    status="failed",
                    error_message="DM unavailable",
                )
            except Exception as e:
                logger.warning("Goodbye DM unexpected error for %s: %s", member, e)
                self.record_activity(
                    event_type="GOODBYE_DM_FAILED",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=None,
                    channel_name="Direct Message",
                    status="failed",
                    error_message="DM unavailable",
                )

    # ========================================================
    # Test Dispatch
    # ========================================================

    async def send_test_message(self, greeting_type: str) -> Dict[str, Any]:
        if not self.bot or not self.bot.is_ready():
            raise RuntimeError("Bot is currently offline. Cannot send test Discord message.")

        guild = self.bot.guild
        if not guild:
            raise RuntimeError(f"Configured guild {settings.DISCORD_GUILD_ID} not found.")

        session = await get_session_direct()
        try:
            config = await ServerGreetingSettingsRepo.get_or_create(session, guild.id)
            invite_row = await ServerInviteSettingsRepo.get_or_create(session, guild.id)
            await session.commit()
        finally:
            await session.close()

        invite_url = invite_row.invite_url if (invite_row and invite_row.is_active) else None
        rules_url = build_rules_url(guild.id, config.rules_channel_id)

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
                self.joined_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
                self.display_avatar = DummyAvatar()

            async def send(self, *args, **kwargs):
                return True

        dummy = DummyMember(guild)

        if greeting_type == "welcome":
            if not config.welcome_channel_id:
                raise ValueError("No welcome channel configured. Please select a channel first.")
            channel = guild.get_channel(config.welcome_channel_id)
            if not channel:
                raise ValueError("Selected welcome channel is unavailable or was deleted.")
            is_valid, telemetry = self.check_channel_permissions(
                channel, requires_embed=bool(config.welcome_use_embed)
            )
            if not is_valid:
                raise PermissionError(telemetry.get("warning") or "Missing required permissions.")

            content, embed, mentions = self.render_welcome_message(
                config, dummy, invite_url=invite_url, rules_url=rules_url, is_test=True
            )
            await self.send_greeting(channel, content, embed, mentions)
            entry = self.record_activity(
                event_type="WELCOME_SENT",
                username="TestUser (Test)",
                user_id="123456789012345678",
                channel_id=channel.id,
                channel_name=channel.name,
                status="delivered",
                is_test=True,
            )
            return {
                "status": "ok",
                "message": f"🧪 Test welcome message successfully sent to #{channel.name}",
                "channel_id": str(channel.id),
                "channel_name": channel.name,
                "activity": entry,
            }

        elif greeting_type == "goodbye":
            if not config.goodbye_channel_id:
                raise ValueError("No goodbye channel configured. Please select a channel first.")
            channel = guild.get_channel(config.goodbye_channel_id)
            if not channel:
                raise ValueError("Selected goodbye channel is unavailable or was deleted.")
            is_valid, telemetry = self.check_channel_permissions(
                channel, requires_embed=bool(config.goodbye_use_embed)
            )
            if not is_valid:
                raise PermissionError(telemetry.get("warning") or "Missing required permissions.")

            content, embed, mentions = self.render_goodbye_message(
                config, dummy, invite_url=invite_url, is_test=True
            )
            await self.send_greeting(channel, content, embed, mentions)
            entry = self.record_activity(
                event_type="GOODBYE_SENT",
                username="TestUser (Test)",
                user_id="123456789012345678",
                channel_id=channel.id,
                channel_name=channel.name,
                status="delivered",
                is_test=True,
            )
            return {
                "status": "ok",
                "message": f"🧪 Test goodbye message successfully sent to #{channel.name}",
                "channel_id": str(channel.id),
                "channel_name": channel.name,
                "activity": entry,
            }

        elif greeting_type in ("welcome-dm", "welcome_dm"):
            content, embed, mentions = self.render_welcome_dm(
                config, dummy, invite_url=invite_url, rules_url=rules_url, is_test=True
            )
            entry = self.record_activity(
                event_type="WELCOME_DM_SENT",
                username="TestUser (Test Preview)",
                user_id="123456789012345678",
                channel_id=None,
                channel_name="Direct Message",
                status="delivered",
                is_test=True,
            )
            return {
                "status": "ok",
                "message": "🧪 Test Welcome DM verified and preview rendered successfully",
                "channel_id": None,
                "channel_name": "Direct Message",
                "activity": entry,
            }

        elif greeting_type in ("goodbye-dm", "goodbye_dm"):
            content, embed, mentions = self.render_goodbye_dm(
                config, dummy, invite_url=invite_url, is_test=True
            )
            entry = self.record_activity(
                event_type="GOODBYE_DM_SENT",
                username="TestUser (Test Preview)",
                user_id="123456789012345678",
                channel_id=None,
                channel_name="Direct Message",
                status="delivered",
                is_test=True,
            )
            return {
                "status": "ok",
                "message": "🧪 Test Goodbye DM verified and preview rendered successfully",
                "channel_id": None,
                "channel_name": "Direct Message",
                "activity": entry,
            }

        else:
            raise ValueError(f"Unknown test type '{greeting_type}'")


_greeting_service: Optional[GreetingService] = None


def get_greeting_service(bot: Optional[commands.Bot] = None) -> GreetingService:
    global _greeting_service
    if _greeting_service is None:
        _greeting_service = GreetingService(bot)
    elif bot is not None:
        _greeting_service.set_bot(bot)
    return _greeting_service
