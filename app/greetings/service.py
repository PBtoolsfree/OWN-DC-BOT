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
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

import discord
from discord.ext import commands

from app.config import get_settings
from app.database.engine import get_session_direct
from app.database.models import ServerGreetingSettings
from app.database.repositories import (
    InviteJoinRepo,
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
    is_safe_url,
    render_template,
    validate_buttons,
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
            elif (status == "failed" or "unavailable" in status.lower()) and "DM" in event_type.upper():
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
    # Rendering & Component Helpers (Premium Onboarding 2.0)
    # ========================================================

    @staticmethod
    def parse_accent_color(color_hex: Optional[str], default: int = 0x5865F2) -> int:
        if not color_hex:
            return default
        clean = str(color_hex).strip().lstrip("#")
        try:
            return int(clean, 16)
        except Exception:
            return default

    @staticmethod
    def apply_banner(
        embed: discord.Embed,
        mode: Optional[str],
        banner_url: Optional[str],
        guild: Optional[discord.Guild],
    ) -> None:
        try:
            if mode == "server" and guild and getattr(guild, "banner", None) and guild.banner:
                embed.set_image(url=guild.banner.url)
            elif mode == "custom" and banner_url and is_safe_url(banner_url):
                embed.set_image(url=banner_url)
            elif (not mode or mode == "none") and banner_url and is_safe_url(banner_url):
                embed.set_image(url=banner_url)
        except Exception as e:
            logger.warning("Failed to attach banner image to embed: %s", e)

    @staticmethod
    def apply_author(
        embed: discord.Embed,
        author_text: Optional[str],
        author_icon_url: Optional[str],
        context: Dict[str, Any],
        guild: Optional[discord.Guild],
    ) -> None:
        if author_text:
            try:
                rendered = render_template(author_text, context)
                icon_url = None
                if author_icon_url and is_safe_url(author_icon_url):
                    icon_url = author_icon_url
                elif guild and getattr(guild, "icon", None) and guild.icon:
                    icon_url = guild.icon.url
                embed.set_author(name=rendered, icon_url=icon_url)
            except Exception as e:
                logger.warning("Failed to set author on embed: %s", e)

    @staticmethod
    def build_buttons_view(
        buttons_json: Optional[str],
        context: Dict[str, Any],
    ) -> Optional[discord.ui.View]:
        if not buttons_json:
            return None
        try:
            ok, _, buttons = validate_buttons(buttons_json)
            if not ok or not buttons:
                return None
            enabled_buttons = [b for b in buttons if b.get("enabled", True)]
            if not enabled_buttons:
                return None
            view = discord.ui.View(timeout=None)
            for b in enabled_buttons[:5]:
                raw_url = b.get("url") or ""
                rendered_url = render_template(raw_url, context)
                if not is_safe_url(rendered_url) or not rendered_url.startswith("https://"):
                    continue
                label = b.get("label") or "Link"
                emoji = b.get("emoji")
                btn = discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label=label,
                    url=rendered_url,
                    emoji=emoji if emoji else None,
                )
                view.add_item(btn)
            return view if len(view.children) > 0 else None
        except Exception as e:
            logger.warning("Failed to build Discord button view: %s", e)
            return None

    def _build_welcome_context(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        invite_url: Optional[str] = None,
        rules_url: Optional[str] = None,
        attribution: Optional[Any] = None,
        total_invites: Optional[Any] = None,
        rank: Optional[str] = None,
        is_test: bool = False,
    ) -> Dict[str, Any]:
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

        inviter_name = "Unknown"
        inviter_mention = "Unknown"
        inviter_id_str = ""
        invite_code_str = "Unknown"
        invite_channel_str = "Unknown"

        if attribution:
            if isinstance(attribution, dict):
                src = attribution.get("source_type", "NORMAL_INVITE" if "inviter_name" in attribution and not attribution.get("is_vanity") else ("VANITY_URL" if attribution.get("is_vanity") else "UNKNOWN"))
                inv_name = attribution.get("inviter_name")
                inv_id = attribution.get("inviter_id")
                inv_mention = attribution.get("inviter_mention")
                inv_code = attribution.get("invite_code")
                ch_id = attribution.get("channel_id")
                ch_name = attribution.get("invite_channel", attribution.get("channel_name"))
                if total_invites is None and "total_invites" in attribution:
                    total_invites = attribution["total_invites"]
                if rank is None and "rank" in attribution:
                    rank = attribution["rank"]
            else:
                src = getattr(attribution, "source_type", "UNKNOWN")
                inv_name = getattr(attribution, "inviter_name", None)
                inv_id = getattr(attribution, "inviter_id", None)
                inv_mention = getattr(attribution, "inviter_mention", None)
                inv_code = getattr(attribution, "invite_code", None)
                ch_id = getattr(attribution, "channel_id", None)
                ch_name = getattr(attribution, "channel_name", None)

            if src == "NORMAL_INVITE":
                inviter_name = inv_name or "Unknown"
                inviter_mention = inv_mention or (f"<@{inv_id}>" if inv_id else inviter_name)
                inviter_id_str = str(inv_id) if inv_id else ""
                invite_code_str = inv_code or "Unknown"
                invite_channel_str = f"<#{ch_id}>" if ch_id else (f"#{ch_name}" if ch_name else "Unknown")
            elif src == "VANITY_URL":
                inviter_name = "Server Vanity URL"
                inviter_mention = "Server Vanity URL"
                inviter_id_str = ""
                invite_code_str = inv_code or "Server Vanity URL"
                invite_channel_str = "Server Vanity URL"
            else:
                inviter_name = "Unknown"
                inviter_mention = "Unknown"
                inviter_id_str = ""
                invite_code_str = "Unknown"
                invite_channel_str = "Unknown"

        tot_invites_str = str(total_invites if total_invites is not None else ("0" if inviter_name == "Unknown" else "N/A"))
        rank_str = str(rank if rank is not None else "N/A")

        rules_ch_id = getattr(config, "rules_channel_id", None) if config else None

        return {
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
            "rules_url": rules_url or build_rules_url(guild.id, rules_ch_id),
            "inviter": inviter_name,
            "inviter_mention": inviter_mention,
            "inviter_id": inviter_id_str,
            "invite_code": invite_code_str,
            "invite_channel": invite_channel_str,
            "total_invites": tot_invites_str,
            "rank": rank_str,
        }

    def render_welcome_message(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        invite_url: Optional[str] = None,
        rules_url: Optional[str] = None,
        attribution: Optional[Any] = None,
        total_invites: Optional[Any] = None,
        rank: Optional[str] = None,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
        guild = member.guild
        context = self._build_welcome_context(
            config,
            member,
            invite_url=invite_url,
            rules_url=rules_url,
            attribution=attribution,
            total_invites=total_invites,
            rank=rank,
            is_test=is_test,
        )

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

        accent_color = self.parse_accent_color(getattr(config, "welcome_accent_color", None), 0x5865F2)
        embed = discord.Embed(title=title, description=desc, color=accent_color)

        self.apply_author(
            embed,
            getattr(config, "welcome_author_text", None),
            getattr(config, "welcome_author_icon_url", None),
            context,
            guild,
        )

        if config.welcome_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        if config.welcome_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)
        if footer:
            icon_url = guild.icon.url if (config.welcome_show_server_icon and guild.icon) else None
            embed.set_footer(text=footer, icon_url=icon_url)

        self.apply_banner(
            embed,
            getattr(config, "welcome_banner_mode", "none"),
            getattr(config, "welcome_banner_url", None),
            guild,
        )

        content = member.mention if (config.welcome_mention_user and not is_test) else None
        return content, embed, allowed_mentions

    def render_welcome_dm(
        self,
        config: ServerGreetingSettings,
        member: discord.Member,
        invite_url: Optional[str] = None,
        rules_url: Optional[str] = None,
        attribution: Optional[Any] = None,
        total_invites: Optional[Any] = None,
        rank: Optional[str] = None,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
        guild = member.guild
        context = self._build_welcome_context(
            config,
            member,
            invite_url=invite_url,
            rules_url=rules_url,
            attribution=attribution,
            total_invites=total_invites,
            rank=rank,
            is_test=is_test,
        )

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

        accent_color = self.parse_accent_color(getattr(config, "welcome_dm_accent_color", None), 0x57F287)
        embed = discord.Embed(title=title, description=desc, color=accent_color)

        self.apply_author(
            embed,
            getattr(config, "welcome_dm_author_text", None),
            getattr(config, "welcome_dm_author_icon_url", None),
            context,
            guild,
        )

        if config.welcome_dm_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        if config.welcome_dm_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)
        if footer:
            icon_url = guild.icon.url if (config.welcome_dm_show_server_icon and guild.icon) else None
            embed.set_footer(text=footer, icon_url=icon_url)

        self.apply_banner(
            embed,
            getattr(config, "welcome_dm_banner_mode", "none"),
            getattr(config, "welcome_dm_banner_url", None),
            guild,
        )

        return None, embed, allowed_mentions

    def render_goodbye_message(
        self,
        config: ServerGreetingSettings,
        member: Union[discord.Member, discord.User],
        guild: Optional[discord.Guild] = None,
        invite_url: Optional[str] = None,
        is_test: bool = False,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
        if guild is None:
            guild = getattr(member, "guild", None) or (self.bot.get_guild(settings.DISCORD_GUILD_ID) if self.bot else None)

        guild_name = guild.name if guild else "Server"
        guild_id_str = str(guild.id) if guild else str(settings.DISCORD_GUILD_ID)
        member_count_str = str(guild.member_count or 1) if guild else "1"
        username = getattr(member, "name", "User")
        display_name = getattr(member, "display_name", username)
        left_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        context = {
            "username": username,
            "display_name": display_name,
            "user_mention": f"@{username}",
            "user_id": str(member.id),
            "server_name": guild_name,
            "server_id": guild_id_str,
            "member_count": member_count_str,
            "left_at": left_str,
            "invite_url": invite_url or "",
            "inviter": "Server",
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

        accent_color = self.parse_accent_color(getattr(config, "goodbye_accent_color", None), 0xED4245)
        embed = discord.Embed(title=title, description=desc, color=accent_color)

        if guild:
            self.apply_author(
                embed,
                getattr(config, "goodbye_author_text", None),
                getattr(config, "goodbye_author_icon_url", None),
                context,
                guild,
            )

        if config.goodbye_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        if config.goodbye_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)
        if footer:
            icon_url = (guild.icon.url if (guild and guild.icon) else None) if config.goodbye_show_server_icon else None
            embed.set_footer(text=footer, icon_url=icon_url)

        if guild:
            self.apply_banner(
                embed,
                getattr(config, "goodbye_banner_mode", "none"),
                getattr(config, "goodbye_banner_url", None),
                guild,
            )

        content = f"<@{member.id}>" if (config.goodbye_mention_user and not is_test) else None
        return content, embed, allowed_mentions

    def render_goodbye_dm(
        self,
        config: ServerGreetingSettings,
        member: Union[discord.Member, discord.User],
        guild_or_links_or_url: Any = None,
        invite_url: Optional[str] = None,
        is_test: bool = False,
        *,
        guild: Optional[discord.Guild] = None,
    ) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
        actual_invite_url = invite_url
        actual_guild = guild

        if isinstance(guild_or_links_or_url, dict):
            if not actual_invite_url:
                actual_invite_url = guild_or_links_or_url.get("invite_url")
        elif isinstance(guild_or_links_or_url, str):
            if not actual_invite_url:
                actual_invite_url = guild_or_links_or_url
        elif guild_or_links_or_url is not None and not actual_guild:
            actual_guild = guild_or_links_or_url

        if actual_guild is None:
            actual_guild = getattr(member, "guild", None) or (
                self.bot.get_guild(settings.DISCORD_GUILD_ID) if self.bot else None
            )

        if isinstance(actual_guild, dict):
            guild_name = actual_guild.get("name", "Server")
            guild_id_str = str(actual_guild.get("id", settings.DISCORD_GUILD_ID))
            member_count_str = str(actual_guild.get("member_count", 1))
        else:
            guild_name = getattr(actual_guild, "name", "Server") if actual_guild else "Server"
            guild_id_str = str(getattr(actual_guild, "id", settings.DISCORD_GUILD_ID)) if actual_guild else str(settings.DISCORD_GUILD_ID)
            member_count_str = str(getattr(actual_guild, "member_count", 1) or 1) if actual_guild else "1"

        username = getattr(member, "name", "User")
        display_name = getattr(member, "display_name", username)
        left_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        joined_str = (
            member.joined_at.strftime("%Y-%m-%d %H:%M:%S")
            if getattr(member, "joined_at", None)
            else "Unknown"
        )
        rules_channel_id = getattr(config, "rules_channel_id", None)
        rules_url = build_rules_url(int(guild_id_str), rules_channel_id) if rules_channel_id else ""

        context = {
            "username": username,
            "display_name": display_name,
            "user_mention": f"@{username}",
            "user_id": str(member.id),
            "server_name": guild_name,
            "server_id": guild_id_str,
            "member_count": member_count_str,
            "left_at": left_str,
            "joined_at": joined_str,
            "rules_url": rules_url,
            "invite_url": actual_invite_url or "",
            "inviter": "Server",
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

        accent_color = self.parse_accent_color(getattr(config, "goodbye_dm_accent_color", None), 0xFEE75C)
        embed = discord.Embed(title=title, description=desc, color=accent_color)

        if guild:
            self.apply_author(
                embed,
                getattr(config, "goodbye_dm_author_text", None),
                getattr(config, "goodbye_dm_author_icon_url", None),
                context,
                guild,
            )

        if config.goodbye_dm_show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        if config.goodbye_dm_show_avatar and getattr(member, "display_avatar", None):
            embed.set_thumbnail(url=member.display_avatar.url)
        if footer:
            icon_url = (guild.icon.url if (guild and guild.icon) else None) if config.goodbye_dm_show_server_icon else None
            embed.set_footer(text=footer, icon_url=icon_url)

        if guild:
            self.apply_banner(
                embed,
                getattr(config, "goodbye_dm_banner_mode", "none"),
                getattr(config, "goodbye_dm_banner_url", None),
                guild,
            )

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
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
        view: Optional[discord.ui.View] = None,
    ) -> None:
        if not hasattr(channel, "send"):
            raise ValueError(f"Channel {getattr(channel, 'name', channel)} cannot receive messages")

        if allowed_mentions is None:
            allowed_mentions = discord.AllowedMentions.none()

        kwargs = {"content": content, "embed": embed, "allowed_mentions": allowed_mentions}
        if view is not None:
            kwargs["view"] = view

        try:
            await channel.send(**kwargs)
        except Exception as e:
            logger.warning("Primary greeting send failed, attempting resilient fallback: %s", e)
            # Fallback 1: Try without buttons view
            if view is not None:
                kwargs.pop("view", None)
                try:
                    await channel.send(**kwargs)
                    return
                except Exception as e2:
                    logger.warning("Greeting send without view failed: %s", e2)

            # Fallback 2: Try without remote banner image in case Discord CDN rejected URL
            if embed and getattr(embed, "image", None):
                clean_embed = embed.copy()
                clean_embed.set_image(url=None)
                kwargs["embed"] = clean_embed
                try:
                    await channel.send(**kwargs)
                    return
                except Exception as e3:
                    logger.warning("Greeting send without banner failed: %s", e3)

            # Re-raise original error if fallbacks also failed
            raise e

    async def send_dm_safe(
        self,
        user: discord.abc.User,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
        view: Optional[discord.ui.View] = None,
    ) -> None:
        if not hasattr(user, "send"):
            raise ValueError(f"Target user {user} cannot receive direct messages")

        if allowed_mentions is None:
            allowed_mentions = discord.AllowedMentions.none()

        kwargs = {"content": content, "embed": embed, "allowed_mentions": allowed_mentions}
        if view is not None:
            kwargs["view"] = view

        try:
            await user.send(**kwargs)
        except discord.Forbidden:
            raise
        except Exception as e:
            logger.warning("Primary DM send failed, attempting resilient fallback: %s", e)
            if view is not None:
                kwargs.pop("view", None)
                try:
                    await user.send(**kwargs)
                    return
                except discord.Forbidden:
                    raise
                except Exception:
                    pass

            if embed and getattr(embed, "image", None):
                clean_embed = embed.copy()
                clean_embed.set_image(url=None)
                kwargs["embed"] = clean_embed
                try:
                    await user.send(**kwargs)
                    return
                except discord.Forbidden:
                    raise
                except Exception:
                    pass
            raise e

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

        # 0. Invite Attribution Pipeline
        attribution = None
        total_invites = None
        rank_str = None
        try:
            from app.invites.tracker import get_invite_tracker
            tracker = get_invite_tracker(self.bot)
            attribution = await tracker.attribute_member_join(member)

            if attribution and attribution.source_type == "NORMAL_INVITE" and attribution.inviter_id:
                session_inv = await get_session_direct()
                try:
                    stats = await InviteJoinRepo.get_user_stats(session_inv, member.guild.id, attribution.inviter_id)
                    total_invites = stats.get("total_joins", stats.get("total_invites", 0))
                    rank = await InviteJoinRepo.get_user_rank(session_inv, member.guild.id, attribution.inviter_id)
                    rank_str = f"#{rank}" if rank is not None else "N/A"
                except Exception as e:
                    logger.warning("Failed to retrieve inviter stats/rank: %s", e)
                finally:
                    await session_inv.close()

            if attribution and attribution.source_type != "UNKNOWN":
                self.record_activity(
                    event_type="INVITE_ATTRIBUTED",
                    username=str(member),
                    user_id=str(member.id),
                    channel_id=attribution.channel_id,
                    channel_name=attribution.channel_name or "Invite",
                    status="delivered",
                    error_message=f"Invited by: {attribution.inviter_name} (Code: {attribution.invite_code})",
                )
        except Exception as e:
            logger.exception("Invite attribution error for %s: %s", member, e)

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
                        config,
                        member,
                        invite_url=invite_url,
                        rules_url=rules_url,
                        attribution=attribution,
                        total_invites=total_invites,
                        rank=rank_str,
                    )
                    context_vars = self._build_welcome_context(
                        config,
                        member,
                        invite_url=invite_url,
                        rules_url=rules_url,
                        attribution=attribution,
                        total_invites=total_invites,
                        rank=rank_str,
                    )
                    view = self.build_buttons_view(getattr(config, "welcome_buttons_json", None), context_vars)
                    await self.send_greeting(channel, content, embed, mentions, view=view)
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
                    config,
                    member,
                    invite_url=invite_url,
                    rules_url=rules_url,
                    attribution=attribution,
                    total_invites=total_invites,
                    rank=rank_str,
                )
                context_vars = self._build_welcome_context(
                    config,
                    member,
                    invite_url=invite_url,
                    rules_url=rules_url,
                    attribution=attribution,
                    total_invites=total_invites,
                    rank=rank_str,
                )
                view = self.build_buttons_view(getattr(config, "welcome_dm_buttons_json", None), context_vars)
                await self.send_dm_safe(member, content, embed, mentions, view=view)
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
                    status="DM unavailable",
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

    async def handle_raw_member_leave(self, payload: discord.RawMemberRemoveEvent) -> None:
        """Handle on_raw_member_remove gateway event (fallback for uncached departures)."""
        guild_id = getattr(payload, "guild_id", settings.DISCORD_GUILD_ID)
        user = getattr(payload, "user", None)
        await self.handle_member_leave(user, guild_id=guild_id)

    async def handle_member_leave(
        self,
        member_or_user: Union[discord.Member, discord.User],
        guild_id: Optional[int] = None,
    ) -> None:
        """
        Robust Leave Pipeline (Premium Onboarding 2.0).

        Order of operations:
        1. Identify guild & resolve User
        2. Deduplication (guild_id + user_id)
        3. Load goodbye configuration
        4. Build template variables & embed
        5. Attempt Goodbye DM FIRST
        6. Record DM result with structured logs & update counters
        7. Update membership state via tracker
        8. Public goodbye message processing
        """
        # 1. Identify guild_id & user_id
        target_guild_id = (
            guild_id
            or (getattr(member_or_user, "guild", None).id if getattr(member_or_user, "guild", None) else None)
            or settings.DISCORD_GUILD_ID
        )
        if target_guild_id != settings.DISCORD_GUILD_ID:
            return

        user_id = getattr(member_or_user, "id", None)
        if not user_id:
            logger.warning("Leave event received without user ID: %s", member_or_user)
            return

        # 2. Deterministic Deduplication (max 1 public goodbye, max 1 goodbye DM, max 1 audit event)
        if self._is_duplicate_event("goodbye", target_guild_id, user_id, window_seconds=60.0):
            logger.info("Duplicate leave event ignored for user=%s in guild=%s", user_id, target_guild_id)
            return

        logger.info("Goodbye event received: user=%s guild=%s", user_id, target_guild_id)

        # 3. Resolve Discord User safely (Capture before member disappears)
        guild = None
        if isinstance(member_or_user, discord.Member) and getattr(member_or_user, "guild", None):
            guild = member_or_user.guild
        elif self.bot:
            guild = self.bot.get_guild(target_guild_id) or getattr(self.bot, "guild", None)

        user = None
        if isinstance(member_or_user, (discord.User, discord.Member)):
            user = member_or_user

        if user is None and self.bot:
            user = self.bot.get_user(user_id)

        if user is None and self.bot:
            try:
                user = await self.bot.fetch_user(user_id)
            except Exception as e:
                logger.warning("Could not fetch user %s from Discord API: %s", user_id, e)

        # Fallback dummy user if fetch failed so username/display_name exist
        if user is None:
            user = member_or_user

        # 4. Load Goodbye configuration & permanent rejoin invite
        session = await get_session_direct()
        try:
            config = await ServerGreetingSettingsRepo.get_or_create(session, target_guild_id)
            invite_row = await ServerInviteSettingsRepo.get_or_create(session, target_guild_id)
            await session.commit()
        except Exception as e:
            logger.error("Failed to load settings on member leave: %s", e)
            return
        finally:
            await session.close()

        invite_url = invite_row.invite_url if (invite_row and invite_row.is_active) else None

        # 5. GOODBYE DM MUST BE ATTEMPTED FIRST (Before data / state is lost)
        if config.goodbye_dm_enabled:
            if getattr(user, "bot", False):
                logger.info("Skipping Goodbye DM for bot user: %s (%s)", user, user_id)
            else:
                logger.info("Goodbye DM attempt: guild_id=%s user_id=%s", target_guild_id, user_id)
                try:
                    content, embed, mentions = self.render_goodbye_dm(
                        config, user, guild=guild, invite_url=invite_url
                    )

                    # Build buttons view: configured buttons or default rejoin invite
                    dm_view = None
                    if getattr(config, "goodbye_dm_buttons_json", None):
                        context_vars = {
                            "username": getattr(user, "name", "User"),
                            "display_name": getattr(user, "display_name", getattr(user, "name", "User")),
                            "user_id": str(user_id),
                            "server_name": getattr(guild, "name", "Server") if guild else "Server",
                            "server_id": str(target_guild_id),
                            "invite_url": invite_url,
                        }
                        dm_view = self.build_buttons_view(config.goodbye_dm_buttons_json, context_vars)

                    if dm_view is None and invite_url and is_safe_url(invite_url):
                        dm_view = discord.ui.View(timeout=None)
                        dm_view.add_item(
                            discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                label="Rejoin Server",
                                url=invite_url,
                                emoji="🔗",
                            )
                        )

                    await self.send_dm_safe(user, content, embed, mentions, view=dm_view)
                    logger.info("Goodbye DM result: status=DELIVERED")
                    self.record_activity(
                        event_type="GOODBYE_DM_SENT",
                        username=str(user),
                        user_id=str(user_id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="delivered",
                    )
                except discord.Forbidden as e:
                    reason = f"Forbidden (code {getattr(e, 'code', 'unknown')}: {getattr(e, 'text', 'DM unavailable')})"
                    logger.warning("Goodbye DM result: status=DM_UNAVAILABLE reason=%s", reason)
                    self.record_activity(
                        event_type="GOODBYE_DM_FAILED",
                        username=str(user),
                        user_id=str(user_id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="DM unavailable",
                        error_message=reason,
                    )
                except (discord.HTTPException, discord.NotFound, discord.InvalidData, asyncio.TimeoutError) as e:
                    reason = f"{type(e).__name__}: {e}"
                    logger.error("Goodbye DM result: status=FAILED reason=%s", reason)
                    self.record_activity(
                        event_type="GOODBYE_DM_FAILED",
                        username=str(user),
                        user_id=str(user_id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="failed",
                        error_message=reason,
                    )
                except Exception as e:
                    reason = f"Unexpected error: {e}"
                    logger.exception("Goodbye DM result: status=FAILED reason=%s", reason)
                    self.record_activity(
                        event_type="GOODBYE_DM_FAILED",
                        username=str(user),
                        user_id=str(user_id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="failed",
                        error_message=reason,
                    )

        # 6. Update Membership State in Invite Tracker
        try:
            from app.invites.tracker import get_invite_tracker
            tracker = get_invite_tracker(self.bot)
            await tracker.handle_member_leave(member_or_user, guild_id=target_guild_id)
        except Exception as e:
            logger.warning("Invite tracker leave error for user=%s: %s", user_id, e)

        # 7. Public Goodbye Processing
        if config.goodbye_enabled and config.goodbye_channel_id and guild:
            channel = guild.get_channel(config.goodbye_channel_id)
            is_valid, perm_telemetry = self.check_channel_permissions(
                channel, requires_embed=bool(config.goodbye_use_embed)
            )
            if is_valid and channel:
                try:
                    content, embed, mentions = self.render_goodbye_message(
                        config, user, guild=guild, invite_url=invite_url
                    )
                    context_vars = {
                        "username": getattr(user, "name", "User"),
                        "display_name": getattr(user, "display_name", getattr(user, "name", "User")),
                        "user_id": str(user_id),
                        "server_name": guild.name,
                        "server_id": str(guild.id),
                        "member_count": str(guild.member_count or 1),
                        "invite_url": invite_url,
                    }
                    view = self.build_buttons_view(getattr(config, "goodbye_buttons_json", None), context_vars)
                    await self.send_greeting(channel, content, embed, mentions, view=view)
                    self.record_activity(
                        event_type="GOODBYE_SENT",
                        username=str(user),
                        user_id=str(user_id),
                        channel_id=channel.id,
                        channel_name=channel.name,
                        status="delivered",
                    )
                    logger.info("Public goodbye delivered for %s to #%s", user, channel.name)
                except Exception as e:
                    logger.exception("Public goodbye send failed: %s", e)
                    self.record_activity(
                        event_type="GOODBYE_SENT",
                        username=str(user),
                        user_id=str(user_id),
                        channel_id=channel.id,
                        channel_name=channel.name,
                        status="failed",
                        error_message=str(e),
                    )
            else:
                warn = perm_telemetry.get("warning") or "Target channel unavailable"
                self.record_activity(
                    event_type="GOODBYE_SENT",
                    username=str(user),
                    user_id=str(user_id),
                    channel_id=config.goodbye_channel_id,
                    channel_name=perm_telemetry.get("channel_name") or "Channel",
                    status="failed",
                    error_message=warn,
                )

    # ========================================================
    # Test Dispatch (Premium Onboarding 2.0)
    # ========================================================

    async def send_test_message(
        self, greeting_type: str, target_user_id: Optional[int] = None
    ) -> Dict[str, Any]:
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

        class DummyAttribution:
            source_type = "NORMAL_INVITE"
            inviter_id = 999888777
            inviter_name = "TestInviter"
            invite_code = "TEST-INVITE-2026"
            channel_id = 111222333
            channel_name = "welcome"

        dummy = DummyMember(guild)
        dummy_attribution = DummyAttribution()

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
                config,
                dummy,
                invite_url=invite_url,
                rules_url=rules_url,
                attribution=dummy_attribution,
                total_invites=15,
                rank="#3",
                is_test=True,
            )
            context_vars = self._build_welcome_context(
                config,
                dummy,
                invite_url=invite_url,
                rules_url=rules_url,
                attribution=dummy_attribution,
                total_invites=15,
                rank="#3",
                is_test=True,
            )
            view = self.build_buttons_view(getattr(config, "welcome_buttons_json", None), context_vars)
            await self.send_greeting(channel, content, embed, mentions, view=view)
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
                config, dummy, guild=guild, invite_url=invite_url, is_test=True
            )
            context_vars = {
                "username": dummy.name,
                "display_name": dummy.display_name,
                "user_id": str(dummy.id),
                "server_name": guild.name,
                "server_id": str(guild.id),
                "member_count": str(guild.member_count or 1),
                "invite_url": invite_url,
            }
            view = self.build_buttons_view(getattr(config, "goodbye_buttons_json", None), context_vars)
            await self.send_greeting(channel, content, embed, mentions, view=view)
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
            target_user = None
            if target_user_id and self.bot:
                target_user = self.bot.get_user(target_user_id)
                if not target_user:
                    try:
                        target_user = await self.bot.fetch_user(target_user_id)
                    except Exception:
                        pass

            if target_user is None and guild:
                owner_id = getattr(guild, "owner_id", None)
                if owner_id:
                    target_user = guild.get_member(owner_id) or (self.bot.get_user(owner_id) if self.bot else None)
                    if not target_user and self.bot:
                        try:
                            target_user = await self.bot.fetch_user(owner_id)
                        except Exception:
                            pass

            recipient = target_user or dummy

            content, embed, mentions = self.render_welcome_dm(
                config,
                recipient,
                invite_url=invite_url,
                rules_url=rules_url,
                attribution=dummy_attribution,
                total_invites=15,
                rank="#3",
                is_test=True,
            )

            # View
            dm_view = None
            if getattr(config, "welcome_dm_buttons_json", None):
                context_vars = {
                    "username": getattr(recipient, "name", "User"),
                    "display_name": getattr(recipient, "display_name", getattr(recipient, "name", "User")),
                    "user_id": str(getattr(recipient, "id", "")),
                    "server_name": guild.name if guild else "Server",
                    "server_id": str(guild.id if guild else ""),
                    "rules_url": rules_url,
                    "invite_url": invite_url,
                }
                dm_view = self.build_buttons_view(config.welcome_dm_buttons_json, context_vars)

            if target_user and hasattr(target_user, "send"):
                try:
                    await self.send_dm_safe(target_user, content, embed, mentions, view=dm_view)
                    entry = self.record_activity(
                        event_type="WELCOME_DM_SENT",
                        username=str(target_user),
                        user_id=str(target_user.id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="delivered",
                        is_test=True,
                    )
                    return {
                        "status": "ok",
                        "delivery_status": "DELIVERED",
                        "message": f"🧪 Test Welcome DM sent directly to @{target_user.name}",
                        "channel_id": None,
                        "channel_name": "Direct Message",
                        "activity": entry,
                    }
                except discord.Forbidden as e:
                    reason = f"DM unavailable: {getattr(e, 'text', 'User privacy settings block DMs')}"
                    entry = self.record_activity(
                        event_type="WELCOME_DM_FAILED",
                        username=str(target_user),
                        user_id=str(target_user.id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="DM unavailable",
                        error_message=reason,
                        is_test=True,
                    )
                    return {
                        "status": "DM unavailable",
                        "delivery_status": "DM_UNAVAILABLE",
                        "message": f"⚠️ Test Welcome DM failed: {reason}",
                        "channel_id": None,
                        "channel_name": "Direct Message",
                        "activity": entry,
                    }
                except Exception as e:
                    entry = self.record_activity(
                        event_type="WELCOME_DM_FAILED",
                        username=str(target_user),
                        user_id=str(target_user.id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="failed",
                        error_message=str(e),
                        is_test=True,
                    )
                    return {
                        "status": "failed",
                        "delivery_status": "FAILED",
                        "message": f"❌ Test Welcome DM failed: {e}",
                        "channel_id": None,
                        "channel_name": "Direct Message",
                        "activity": entry,
                    }

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
                "delivery_status": "PREVIEW_VERIFIED",
                "message": "🧪 Test Welcome DM verified and preview rendered successfully",
                "channel_id": None,
                "channel_name": "Direct Message",
                "activity": entry,
            }

        elif greeting_type in ("goodbye-dm", "goodbye_dm"):
            target_user = None
            if target_user_id and self.bot:
                target_user = self.bot.get_user(target_user_id)
                if not target_user:
                    try:
                        target_user = await self.bot.fetch_user(target_user_id)
                    except Exception:
                        pass

            if target_user is None and guild:
                owner_id = getattr(guild, "owner_id", None)
                if owner_id:
                    target_user = guild.get_member(owner_id) or (self.bot.get_user(owner_id) if self.bot else None)
                    if not target_user and self.bot:
                        try:
                            target_user = await self.bot.fetch_user(owner_id)
                        except Exception:
                            pass

            recipient = target_user or dummy

            content, embed, mentions = self.render_goodbye_dm(
                config, recipient, guild=guild, invite_url=invite_url, is_test=True
            )

            # View
            dm_view = None
            if getattr(config, "goodbye_dm_buttons_json", None):
                context_vars = {
                    "username": getattr(recipient, "name", "User"),
                    "display_name": getattr(recipient, "display_name", getattr(recipient, "name", "User")),
                    "user_id": str(getattr(recipient, "id", "")),
                    "server_name": guild.name if guild else "Server",
                    "server_id": str(guild.id if guild else ""),
                    "invite_url": invite_url,
                }
                dm_view = self.build_buttons_view(config.goodbye_dm_buttons_json, context_vars)

            if dm_view is None and invite_url and is_safe_url(invite_url):
                dm_view = discord.ui.View(timeout=None)
                dm_view.add_item(
                    discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        label="Rejoin Server",
                        url=invite_url,
                        emoji="🔗",
                    )
                )

            if target_user and hasattr(target_user, "send"):
                try:
                    await self.send_dm_safe(target_user, content, embed, mentions, view=dm_view)
                    entry = self.record_activity(
                        event_type="GOODBYE_DM_SENT",
                        username=str(target_user),
                        user_id=str(target_user.id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="delivered",
                        is_test=True,
                    )
                    return {
                        "status": "ok",
                        "delivery_status": "DELIVERED",
                        "message": f"🧪 Test Goodbye DM sent directly to @{target_user.name}",
                        "channel_id": None,
                        "channel_name": "Direct Message",
                        "activity": entry,
                    }
                except discord.Forbidden as e:
                    reason = f"DM unavailable: {getattr(e, 'text', 'User privacy settings block DMs')}"
                    entry = self.record_activity(
                        event_type="GOODBYE_DM_FAILED",
                        username=str(target_user),
                        user_id=str(target_user.id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="DM unavailable",
                        error_message=reason,
                        is_test=True,
                    )
                    return {
                        "status": "DM unavailable",
                        "delivery_status": "DM_UNAVAILABLE",
                        "message": f"⚠️ Test Goodbye DM failed: {reason}",
                        "channel_id": None,
                        "channel_name": "Direct Message",
                        "activity": entry,
                    }
                except Exception as e:
                    entry = self.record_activity(
                        event_type="GOODBYE_DM_FAILED",
                        username=str(target_user),
                        user_id=str(target_user.id),
                        channel_id=None,
                        channel_name="Direct Message",
                        status="failed",
                        error_message=str(e),
                        is_test=True,
                    )
                    return {
                        "status": "failed",
                        "delivery_status": "FAILED",
                        "message": f"❌ Test Goodbye DM failed: {e}",
                        "channel_id": None,
                        "channel_name": "Direct Message",
                        "activity": entry,
                    }

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
                "delivery_status": "PREVIEW_VERIFIED",
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
