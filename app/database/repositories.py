"""
PB HERO Database Repositories - Data access layer.

All repositories operate within the single configured Guild context.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AdminUser,
    AppConfig,
    AuditLog,
    AutomodRule,
    BlockedMessage,
    ChannelPolicy,
    CustomModerationStyle,
    EventStatus,
    EventType,
    ExemptionRule,
    ModerationAction,
    ModerationCase,
    ModerationExemption,
    PolicyProfile,
    PolicyValue,
    RoleOverride,
    ServerConfig,
    ServerGreetingSettings,
    ServerInviteSettings,
    WarningEscalationRule,
    WarningRecord,
    YouTubeChannel,
    YouTubeDestination,
    YouTubeEvent,
    YouTubeNotificationTemplate,
)

logger = logging.getLogger("pbhero.database")


# ─── Admin Users ──────────────────────────────────────────────────────────────

class AdminUserRepo:
    """Repository for admin user management."""

    @staticmethod
    async def get_by_username(session: AsyncSession, username: str) -> Optional[AdminUser]:
        result = await session.execute(select(AdminUser).where(AdminUser.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, username: str, password_hash: str) -> AdminUser:
        user = AdminUser(username=username, password_hash=password_hash)
        session.add(user)
        await session.flush()
        return user

    @staticmethod
    async def update_password(session: AsyncSession, username: str, new_hash: str) -> bool:
        result = await session.execute(
            update(AdminUser)
            .where(AdminUser.username == username)
            .values(password_hash=new_hash, updated_at=datetime.utcnow())
        )
        return result.rowcount > 0

    @staticmethod
    async def count(session: AsyncSession) -> int:
        result = await session.execute(select(func.count(AdminUser.id)))
        return result.scalar() or 0


# ─── YouTube Channels ────────────────────────────────────────────────────────

class YouTubeChannelRepo:
    """Repository for YouTube channel management."""

    @staticmethod
    async def get_all(session: AsyncSession, enabled_only: bool = False) -> list[YouTubeChannel]:
        query = select(YouTubeChannel)
        if enabled_only:
            query = query.where(YouTubeChannel.enabled.is_(True))
        result = await session.execute(query.order_by(YouTubeChannel.channel_name))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_channel_id(session: AsyncSession, youtube_channel_id: str) -> Optional[YouTubeChannel]:
        result = await session.execute(
            select(YouTubeChannel).where(YouTubeChannel.youtube_channel_id == youtube_channel_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, channel_db_id: int) -> Optional[YouTubeChannel]:
        result = await session.execute(select(YouTubeChannel).where(YouTubeChannel.id == channel_db_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, youtube_channel_id: str, channel_name: str,
                     handle: str = None, feed_url: str = None) -> YouTubeChannel:
        if not feed_url:
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={youtube_channel_id}"
        channel = YouTubeChannel(
            youtube_channel_id=youtube_channel_id,
            channel_name=channel_name,
            handle=handle,
            feed_url=feed_url,
        )
        session.add(channel)
        await session.flush()
        return channel

    @staticmethod
    async def update_check_status(session: AsyncSession, youtube_channel_id: str,
                                   success: bool, error: str = None) -> None:
        values = {"last_checked_at": datetime.utcnow()}
        if success:
            values["last_success_at"] = datetime.utcnow()
            values["last_error"] = None
        else:
            values["last_error"] = error
        await session.execute(
            update(YouTubeChannel)
            .where(YouTubeChannel.youtube_channel_id == youtube_channel_id)
            .values(**values)
        )

    @staticmethod
    async def toggle_enabled(session: AsyncSession, youtube_channel_id: str, enabled: bool) -> None:
        await session.execute(
            update(YouTubeChannel)
            .where(YouTubeChannel.youtube_channel_id == youtube_channel_id)
            .values(enabled=enabled, updated_at=datetime.utcnow())
        )

    @staticmethod
    async def delete_channel(session: AsyncSession, youtube_channel_id: str) -> bool:
        result = await session.execute(
            delete(YouTubeChannel).where(YouTubeChannel.youtube_channel_id == youtube_channel_id)
        )
        return result.rowcount > 0

    @staticmethod
    async def count(session: AsyncSession) -> int:
        result = await session.execute(select(func.count(YouTubeChannel.id)))
        return result.scalar() or 0

    @staticmethod
    async def count_enabled(session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count(YouTubeChannel.id)).where(YouTubeChannel.enabled.is_(True))
        )
        return result.scalar() or 0


# ─── YouTube Destinations ────────────────────────────────────────────────────

class YouTubeDestinationRepo:
    """Repository for YouTube notification destinations."""

    @staticmethod
    async def get_for_channel(session: AsyncSession, youtube_channel_id: str) -> list[YouTubeDestination]:
        result = await session.execute(
            select(YouTubeDestination).where(YouTubeDestination.youtube_channel_id == youtube_channel_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(session: AsyncSession, youtube_channel_id: str, discord_channel_id: int,
                     notification_role_id: int = None, **kwargs) -> YouTubeDestination:
        dest = YouTubeDestination(
            youtube_channel_id=youtube_channel_id,
            discord_channel_id=discord_channel_id,
            notification_role_id=notification_role_id,
            **kwargs,
        )
        session.add(dest)
        await session.flush()
        return dest

    @staticmethod
    async def delete_for_channel(session: AsyncSession, youtube_channel_id: str) -> None:
        await session.execute(
            delete(YouTubeDestination).where(YouTubeDestination.youtube_channel_id == youtube_channel_id)
        )


# ─── YouTube Events (Deduplication) ──────────────────────────────────────────

class YouTubeEventRepo:
    """Repository for YouTube event tracking and deduplication."""

    @staticmethod
    async def exists(session: AsyncSession, youtube_channel_id: str, video_id: str,
                     event_type: EventType) -> bool:
        result = await session.execute(
            select(func.count(YouTubeEvent.id)).where(
                YouTubeEvent.youtube_channel_id == youtube_channel_id,
                YouTubeEvent.video_id == video_id,
                YouTubeEvent.event_type == event_type,
            )
        )
        return (result.scalar() or 0) > 0

    @staticmethod
    async def create(session: AsyncSession, youtube_channel_id: str, video_id: str,
                     event_type: EventType, title: str = None, video_url: str = None,
                     published_at: datetime = None, status: EventStatus = EventStatus.DETECTED,
                     live_state=None) -> YouTubeEvent:
        event = YouTubeEvent(
            youtube_channel_id=youtube_channel_id,
            video_id=video_id,
            event_type=event_type,
            title=title,
            video_url=video_url,
            published_at=published_at,
            status=status,
            live_state=live_state,
        )
        session.add(event)
        await session.flush()
        return event

    @staticmethod
    async def mark_notified(session: AsyncSession, event_id: int) -> None:
        await session.execute(
            update(YouTubeEvent)
            .where(YouTubeEvent.id == event_id)
            .values(status=EventStatus.NOTIFIED, notified_at=datetime.utcnow())
        )

    @staticmethod
    async def get_recent(session: AsyncSession, youtube_channel_id: str = None,
                         limit: int = 50) -> list[YouTubeEvent]:
        query = select(YouTubeEvent).order_by(YouTubeEvent.detected_at.desc()).limit(limit)
        if youtube_channel_id:
            query = query.where(YouTubeEvent.youtube_channel_id == youtube_channel_id)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count_today(session: AsyncSession) -> int:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count(YouTubeEvent.id)).where(
                YouTubeEvent.notified_at >= today_start,
                YouTubeEvent.status == EventStatus.NOTIFIED,
            )
        )
        return result.scalar() or 0


# ─── YouTube Notification Templates ──────────────────────────────────────────

class YouTubeTemplateRepo:
    """Repository for event-specific YouTube notification templates."""

    DEFAULTS = {
        EventType.UPLOAD: {
            "title_template": "🎬 NEW VIDEO — {channel_name}",
            "description_template": "**{video_title}**\n\nA new video is now available on YouTube.",
            "mention_role": None,
            "footer_text": "PB HERO Personal Discord Bot",
            "show_thumbnail": True,
            "show_timestamp": True,
            "enable_button": True,
        },
        EventType.SCHEDULED_LIVE: {
            "title_template": "⏰ LIVE SCHEDULED — {channel_name}",
            "description_template": "**{video_title}**\n\nThe livestream is scheduled to start soon.",
            "mention_role": None,
            "footer_text": "PB HERO Personal Discord Bot",
            "show_thumbnail": True,
            "show_timestamp": True,
            "enable_button": True,
        },
        EventType.LIVE_STARTED: {
            "title_template": "🔴 {channel_name} IS NOW LIVE!",
            "description_template": "**{video_title}**\n\nJoin the stream now on YouTube.",
            "mention_role": None,
            "footer_text": "PB HERO Personal Discord Bot",
            "show_thumbnail": True,
            "show_timestamp": True,
            "enable_button": True,
        },
        EventType.PREMIERE: {
            "title_template": "🎬 PREMIERE — {channel_name}",
            "description_template": "**{video_title}**\n\nA new YouTube Premiere is scheduled.",
            "mention_role": None,
            "footer_text": "PB HERO Personal Discord Bot",
            "show_thumbnail": True,
            "show_timestamp": True,
            "enable_button": True,
        },
    }

    @classmethod
    async def create_defaults(cls, session: AsyncSession) -> None:
        """Ensure default templates exist for all four event types."""
        for event_type, data in cls.DEFAULTS.items():
            result = await session.execute(
                select(YouTubeNotificationTemplate).where(YouTubeNotificationTemplate.event_type == event_type)
            )
            if not result.scalar_one_or_none():
                tpl = YouTubeNotificationTemplate(event_type=event_type, **data)
                session.add(tpl)
        await session.flush()

    @classmethod
    async def get_all(cls, session: AsyncSession) -> list[YouTubeNotificationTemplate]:
        """Get all event templates, auto-creating defaults if any are missing."""
        await cls.create_defaults(session)
        result = await session.execute(
            select(YouTubeNotificationTemplate).order_by(YouTubeNotificationTemplate.id)
        )
        return list(result.scalars().all())

    @classmethod
    async def get_by_event_type(cls, session: AsyncSession, event_type: EventType) -> YouTubeNotificationTemplate:
        """Get template for a specific event type, auto-creating default if missing."""
        result = await session.execute(
            select(YouTubeNotificationTemplate).where(YouTubeNotificationTemplate.event_type == event_type)
        )
        tpl = result.scalar_one_or_none()
        if not tpl:
            defaults = cls.DEFAULTS.get(event_type)
            if not defaults:
                raise ValueError(f"Unknown event type: {event_type}")
            tpl = YouTubeNotificationTemplate(event_type=event_type, **defaults)
            session.add(tpl)
            await session.flush()
        return tpl

    @classmethod
    async def update(cls, session: AsyncSession, event_type: EventType, **kwargs) -> YouTubeNotificationTemplate:
        """Update an event template."""
        tpl = await cls.get_by_event_type(session, event_type)
        for key, val in kwargs.items():
            if hasattr(tpl, key) and key not in ("id", "event_type", "created_at"):
                setattr(tpl, key, val)
        tpl.updated_at = datetime.utcnow()
        await session.flush()
        return tpl

    @classmethod
    async def reset(cls, session: AsyncSession, event_type: EventType) -> YouTubeNotificationTemplate:
        """Reset an event template to its factory default values."""
        defaults = cls.DEFAULTS.get(event_type)
        if not defaults:
            raise ValueError(f"Unknown event type: {event_type}")
        return await cls.update(session, event_type, **defaults)


# ─── Channel Policies ────────────────────────────────────────────────────────

class ChannelPolicyRepo:
    """Repository for channel moderation policies."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[ChannelPolicy]:
        result = await session.execute(select(ChannelPolicy).order_by(ChannelPolicy.category_name, ChannelPolicy.channel_name))
        return list(result.scalars().all())

    @staticmethod
    async def get_for_channel(session: AsyncSession, channel_id: int) -> Optional[ChannelPolicy]:
        result = await session.execute(
            select(ChannelPolicy).where(ChannelPolicy.discord_channel_id == channel_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(session: AsyncSession, channel_id: Optional[int] = None, **kwargs) -> ChannelPolicy:
        from app.database.serializers import normalize_domain_list, serialize_json_field

        if channel_id is None:
            channel_id = kwargs.pop("discord_channel_id", None)
        if channel_id is None:
            raise ValueError("channel_id or discord_channel_id is required for policy upsert")
        channel_id = int(channel_id)

        if "allowed_domains" in kwargs:
            kwargs["allowed_domains"] = serialize_json_field(normalize_domain_list(kwargs["allowed_domains"]))

        existing = await ChannelPolicyRepo.get_for_channel(session, channel_id)
        if existing:
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            await session.flush()
            return existing
        else:
            policy = ChannelPolicy(discord_channel_id=channel_id, **kwargs)
            session.add(policy)
            await session.flush()
            return policy

    @staticmethod
    async def delete_policy(session: AsyncSession, channel_id: int) -> bool:
        result = await session.execute(
            delete(ChannelPolicy).where(ChannelPolicy.discord_channel_id == channel_id)
        )
        return result.rowcount > 0

    @staticmethod
    async def count_active(session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count(ChannelPolicy.id)).where(ChannelPolicy.enabled.is_(True))
        )
        return result.scalar() or 0


# ─── Policy Profiles ─────────────────────────────────────────────────────────

class PolicyProfileRepo:
    """Repository for policy presets/profiles."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[PolicyProfile]:
        result = await session.execute(
            select(PolicyProfile).order_by(PolicyProfile.is_builtin.desc(), PolicyProfile.name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(session: AsyncSession, profile_id: int) -> Optional[PolicyProfile]:
        result = await session.execute(select(PolicyProfile).where(PolicyProfile.id == profile_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(session: AsyncSession, name: str) -> Optional[PolicyProfile]:
        result = await session.execute(select(PolicyProfile).where(PolicyProfile.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, name: str, **kwargs) -> PolicyProfile:
        from app.database.serializers import normalize_domain_list, serialize_json_field

        if "allowed_domains" in kwargs:
            kwargs["allowed_domains"] = serialize_json_field(normalize_domain_list(kwargs["allowed_domains"]))

        profile = PolicyProfile(name=name, **kwargs)
        session.add(profile)
        await session.flush()
        return profile

    @staticmethod
    async def update(session: AsyncSession, profile_id: int, **kwargs) -> Optional[PolicyProfile]:
        from app.database.serializers import normalize_domain_list, serialize_json_field

        profile = await PolicyProfileRepo.get_by_id(session, profile_id)
        if not profile:
            return None
        if profile.is_builtin:
            raise ValueError("Built-in policy presets cannot be modified.")

        if "allowed_domains" in kwargs:
            kwargs["allowed_domains"] = serialize_json_field(normalize_domain_list(kwargs["allowed_domains"]))

        for key, value in kwargs.items():
            if hasattr(profile, key) and key not in ("id", "is_builtin", "created_at"):
                setattr(profile, key, value)

        profile.updated_at = datetime.utcnow()
        await session.flush()
        return profile

    @staticmethod
    async def delete(session: AsyncSession, profile_id: int) -> bool:
        profile = await PolicyProfileRepo.get_by_id(session, profile_id)
        if not profile:
            return False
        if profile.is_builtin:
            raise ValueError("Built-in policy presets cannot be deleted.")

        await session.delete(profile)
        await session.flush()
        return True

    @staticmethod
    async def duplicate(session: AsyncSession, profile_id: int, new_name: Optional[str] = None) -> Optional[PolicyProfile]:
        source = await PolicyProfileRepo.get_by_id(session, profile_id)
        if not source:
            return None

        if not new_name:
            base_name = f"{source.name}_CUSTOM"
            candidate = base_name
            idx = 1
            while await PolicyProfileRepo.get_by_name(session, candidate):
                candidate = f"{base_name}_{idx}"
                idx += 1
            new_name = candidate

        clone = PolicyProfile(
            name=new_name,
            description=f"Custom copy of {source.name}. {source.description or ''}".strip(),
            category=source.category or "Custom",
            policy_type=getattr(source, "policy_type", "text"),
            allow_text=source.allow_text,
            allow_links=source.allow_links,
            allow_images=source.allow_images,
            allow_videos=source.allow_videos,
            allow_files=source.allow_files,
            allow_stickers=source.allow_stickers,
            allow_everyone=source.allow_everyone,
            allow_here=source.allow_here,
            allow_role_mentions=source.allow_role_mentions,
            allow_user_mentions=source.allow_user_mentions,
            allow_connect=getattr(source, "allow_connect", PolicyValue.ALLOW),
            allow_speak=getattr(source, "allow_speak", PolicyValue.ALLOW),
            allow_video=getattr(source, "allow_video", PolicyValue.ALLOW),
            allow_stream=getattr(source, "allow_stream", PolicyValue.ALLOW),
            allow_soundboard=getattr(source, "allow_soundboard", PolicyValue.ALLOW),
            allow_voice_activity=getattr(source, "allow_voice_activity", PolicyValue.ALLOW),
            allow_priority_speaker=getattr(source, "allow_priority_speaker", PolicyValue.DENY),
            allow_mute_members=getattr(source, "allow_mute_members", PolicyValue.DENY),
            allow_deafen_members=getattr(source, "allow_deafen_members", PolicyValue.DENY),
            allow_move_members=getattr(source, "allow_move_members", PolicyValue.DENY),
            allowed_domains=source.allowed_domains,
            delete_violations=source.delete_violations if hasattr(source, "delete_violations") else True,
            warn_on_violation=source.warn_on_violation if hasattr(source, "warn_on_violation") else True,
            log_violations=source.log_violations if hasattr(source, "log_violations") else True,
            send_dm_warning=source.send_dm_warning if hasattr(source, "send_dm_warning") else False,
            warning_message=source.warning_message if hasattr(source, "warning_message") else None,
            is_builtin=False,
        )
        session.add(clone)
        await session.flush()
        return clone

    @staticmethod
    async def create_defaults(session: AsyncSession) -> None:
        """Create or update all 15 professional built-in policy presets."""
        defaults = [
            # 1 - Announcements
            {
                "name": "ANNOUNCEMENTS",
                "category": "Announcements",
                "description": "Official announcement channels. Members cannot post; only moderators/admins may post.",
                "allow_text": PolicyValue.DENY, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.DENY, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 2 - General Chat
            {
                "name": "GENERAL CHAT",
                "category": "General",
                "description": "Standard community chat: text, links, images, files allowed. @everyone/@here blocked.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.ALLOW,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.ALLOW,
                "allow_files": PolicyValue.ALLOW, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.ALLOW, "allow_user_mentions": PolicyValue.ALLOW,
                "is_builtin": True,
            },
            # 3 - Image Only
            {
                "name": "IMAGE ONLY",
                "category": "Media",
                "description": "Only images allowed. No text, links, videos, files, or mentions.",
                "allow_text": PolicyValue.DENY, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 4 - Media
            {
                "name": "MEDIA",
                "category": "Media",
                "description": "Media sharing: text, images, videos allowed. Links configurable / inherit.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.INHERIT,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.ALLOW,
                "allow_files": PolicyValue.ALLOW, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 5 - No Link Chat
            {
                "name": "NO LINK CHAT",
                "category": "Moderation",
                "description": "Chat without links: text, images, and stickers allowed. No external URLs or mentions.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 6 - Support
            {
                "name": "SUPPORT",
                "category": "Support",
                "description": "Support channels: text, links, images, and files allowed. Videos and mass pings blocked.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.ALLOW,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.ALLOW, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.ALLOW, "allow_user_mentions": PolicyValue.ALLOW,
                "is_builtin": True,
            },
            # 7 - Bot Commands
            {
                "name": "BOT COMMANDS",
                "category": "Bots",
                "description": "Commands / bot interaction channels. Text commands allowed, attachments and links blocked.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.DENY, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 8 - Read Only
            {
                "name": "READ ONLY",
                "category": "Other",
                "description": "Information/archive channels. Normal members cannot post text, media, or mentions.",
                "allow_text": PolicyValue.DENY, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.DENY, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 9 - Links Only
            {
                "name": "LINKS ONLY",
                "category": "Community",
                "description": "Resource and link-sharing channel. Text and URLs allowed; files and mass mentions blocked.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.ALLOW,
                "allow_images": PolicyValue.INHERIT, "allow_videos": PolicyValue.INHERIT,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.ALLOW, "allow_user_mentions": PolicyValue.ALLOW,
                "is_builtin": True,
            },
            # 10 - Giveaway
            {
                "name": "GIVEAWAY",
                "category": "Community",
                "description": "Giveaway channels: text, images, and stickers allowed. External links and role mentions blocked.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.ALLOW,
                "is_builtin": True,
            },
            # 11 - Clips / Showcase
            {
                "name": "CLIPS / SHOWCASE",
                "category": "Media",
                "description": "Community clips and screenshots. Media and files allowed, mass pings blocked.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.INHERIT,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.ALLOW,
                "allow_files": PolicyValue.ALLOW, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.ALLOW,
                "is_builtin": True,
            },
            # 12 - Verification
            {
                "name": "VERIFICATION",
                "category": "Other",
                "description": "Verification / onboarding channel. Text allowed for captcha/commands, links and media blocked.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.DENY, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 13 - Strict Chat
            {
                "name": "STRICT CHAT",
                "category": "General",
                "description": "Strict text-only discussion. Links, attachments, stickers, and role pings strictly blocked.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.DENY, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 14 - Free Discussion
            {
                "name": "FREE DISCUSSION",
                "category": "General",
                "description": "Open community discussion. Text, links, media, files, and member mentions fully allowed.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.ALLOW,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.ALLOW,
                "allow_files": PolicyValue.ALLOW, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.ALLOW, "allow_user_mentions": PolicyValue.ALLOW,
                "is_builtin": True,
            },
            # 15 - Moderator Only
            {
                "name": "MODERATOR ONLY",
                "category": "Moderation",
                "policy_type": "text",
                "description": "Staff only channel. All non-staff member posting blocked.",
                "allow_text": PolicyValue.DENY, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.DENY, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 16 - Voice General
            {
                "name": "VOICE GENERAL",
                "category": "General",
                "policy_type": "voice",
                "description": "Standard voice chat: members can connect, speak, stream video and screen, and use soundboard.",
                "allow_connect": PolicyValue.ALLOW, "allow_speak": PolicyValue.ALLOW,
                "allow_video": PolicyValue.ALLOW, "allow_stream": PolicyValue.ALLOW,
                "allow_soundboard": PolicyValue.ALLOW, "allow_voice_activity": PolicyValue.ALLOW,
                "allow_priority_speaker": PolicyValue.DENY, "allow_mute_members": PolicyValue.DENY,
                "allow_deafen_members": PolicyValue.DENY, "allow_move_members": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 17 - Voice Staff
            {
                "name": "VOICE STAFF",
                "category": "Moderation",
                "policy_type": "voice",
                "description": "Staff voice lounge: full permissions including Priority Speaker, Member Muting, and Member Moving.",
                "allow_connect": PolicyValue.ALLOW, "allow_speak": PolicyValue.ALLOW,
                "allow_video": PolicyValue.ALLOW, "allow_stream": PolicyValue.ALLOW,
                "allow_soundboard": PolicyValue.ALLOW, "allow_voice_activity": PolicyValue.ALLOW,
                "allow_priority_speaker": PolicyValue.ALLOW, "allow_mute_members": PolicyValue.ALLOW,
                "allow_deafen_members": PolicyValue.ALLOW, "allow_move_members": PolicyValue.ALLOW,
                "is_builtin": True,
            },
            # 18 - Voice No Stream
            {
                "name": "VOICE NO STREAM",
                "category": "Media",
                "policy_type": "voice",
                "description": "Voice only: connect and speak allowed. Video camera, screen sharing, and soundboard denied.",
                "allow_connect": PolicyValue.ALLOW, "allow_speak": PolicyValue.ALLOW,
                "allow_video": PolicyValue.DENY, "allow_stream": PolicyValue.DENY,
                "allow_soundboard": PolicyValue.DENY, "allow_voice_activity": PolicyValue.ALLOW,
                "allow_priority_speaker": PolicyValue.DENY, "allow_mute_members": PolicyValue.DENY,
                "allow_deafen_members": PolicyValue.DENY, "allow_move_members": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 19 - Voice No Speak
            {
                "name": "VOICE NO SPEAK",
                "category": "Moderation",
                "policy_type": "voice",
                "description": "Muted room: members can connect to listen, but cannot speak, transmit video, or stream.",
                "allow_connect": PolicyValue.ALLOW, "allow_speak": PolicyValue.DENY,
                "allow_video": PolicyValue.DENY, "allow_stream": PolicyValue.DENY,
                "allow_soundboard": PolicyValue.DENY, "allow_voice_activity": PolicyValue.DENY,
                "allow_priority_speaker": PolicyValue.DENY, "allow_mute_members": PolicyValue.DENY,
                "allow_deafen_members": PolicyValue.DENY, "allow_move_members": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 20 - Voice Listen Only
            {
                "name": "VOICE LISTEN ONLY",
                "category": "Events",
                "policy_type": "voice",
                "description": "Podcast / auditorium style: connect allowed, speak and streaming denied. Strict listen-only channel.",
                "allow_connect": PolicyValue.ALLOW, "allow_speak": PolicyValue.DENY,
                "allow_video": PolicyValue.DENY, "allow_stream": PolicyValue.DENY,
                "allow_soundboard": PolicyValue.DENY, "allow_voice_activity": PolicyValue.DENY,
                "allow_priority_speaker": PolicyValue.DENY, "allow_mute_members": PolicyValue.DENY,
                "allow_deafen_members": PolicyValue.DENY, "allow_move_members": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 21 - Voice Gaming
            {
                "name": "VOICE GAMING",
                "category": "Community",
                "policy_type": "voice",
                "description": "Gaming session voice: open voice, screen share, video, and soundboard enabled for team gameplay.",
                "allow_connect": PolicyValue.ALLOW, "allow_speak": PolicyValue.ALLOW,
                "allow_video": PolicyValue.ALLOW, "allow_stream": PolicyValue.ALLOW,
                "allow_soundboard": PolicyValue.ALLOW, "allow_voice_activity": PolicyValue.ALLOW,
                "allow_priority_speaker": PolicyValue.DENY, "allow_mute_members": PolicyValue.DENY,
                "allow_deafen_members": PolicyValue.DENY, "allow_move_members": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 22 - Voice Event
            {
                "name": "VOICE EVENT",
                "category": "Events",
                "policy_type": "voice",
                "description": "Community stage / event voice: audience can connect; stage hosts have Priority Speaker; regular speaking blocked.",
                "allow_connect": PolicyValue.ALLOW, "allow_speak": PolicyValue.DENY,
                "allow_video": PolicyValue.DENY, "allow_stream": PolicyValue.DENY,
                "allow_soundboard": PolicyValue.DENY, "allow_voice_activity": PolicyValue.DENY,
                "allow_priority_speaker": PolicyValue.ALLOW, "allow_mute_members": PolicyValue.DENY,
                "allow_deafen_members": PolicyValue.DENY, "allow_move_members": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 23 - Voice Private
            {
                "name": "VOICE PRIVATE",
                "category": "Private",
                "policy_type": "voice",
                "description": "Private / locked room: non-whitelisted members cannot connect or speak.",
                "allow_connect": PolicyValue.DENY, "allow_speak": PolicyValue.DENY,
                "allow_video": PolicyValue.DENY, "allow_stream": PolicyValue.DENY,
                "allow_soundboard": PolicyValue.DENY, "allow_voice_activity": PolicyValue.DENY,
                "allow_priority_speaker": PolicyValue.DENY, "allow_mute_members": PolicyValue.DENY,
                "allow_deafen_members": PolicyValue.DENY, "allow_move_members": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 24 - Voice Music
            {
                "name": "VOICE MUSIC",
                "category": "Community",
                "policy_type": "voice",
                "description": "Music bot listening room: connect and stream allowed; member mic speaking and soundboards disabled.",
                "allow_connect": PolicyValue.ALLOW, "allow_speak": PolicyValue.DENY,
                "allow_video": PolicyValue.DENY, "allow_stream": PolicyValue.ALLOW,
                "allow_soundboard": PolicyValue.DENY, "allow_voice_activity": PolicyValue.DENY,
                "allow_priority_speaker": PolicyValue.DENY, "allow_mute_members": PolicyValue.DENY,
                "allow_deafen_members": PolicyValue.DENY, "allow_move_members": PolicyValue.DENY,
                "is_builtin": True,
            },
            # 25 - Voice Moderator
            {
                "name": "VOICE MODERATOR",
                "category": "Moderation",
                "policy_type": "voice",
                "description": "Moderator only voice room: strictly denied to normal members, reserved for server moderators.",
                "allow_connect": PolicyValue.DENY, "allow_speak": PolicyValue.DENY,
                "allow_video": PolicyValue.DENY, "allow_stream": PolicyValue.DENY,
                "allow_soundboard": PolicyValue.DENY, "allow_voice_activity": PolicyValue.DENY,
                "allow_priority_speaker": PolicyValue.DENY, "allow_mute_members": PolicyValue.DENY,
                "allow_deafen_members": PolicyValue.DENY, "allow_move_members": PolicyValue.DENY,
                "is_builtin": True,
            },
        ]

        for preset in defaults:
            existing = await PolicyProfileRepo.get_by_name(session, preset["name"])
            if not existing:
                # Also check old underscore name (e.g. GENERAL_CHAT -> GENERAL CHAT)
                alt_name = preset["name"].replace(" / ", "_").replace(" ", "_").strip()
                old = await PolicyProfileRepo.get_by_name(session, alt_name)
                if old:
                    old.name = preset["name"]
                    old.category = preset["category"]
                    old.description = preset["description"]
                    old.is_builtin = True
                    continue
                await PolicyProfileRepo.create(session, **preset)
            else:
                if hasattr(existing, "category") and not existing.category:
                    existing.category = preset["category"]
                existing.is_builtin = True


# ─── Moderation Cases ────────────────────────────────────────────────────────

class ModerationCaseRepo:
    """Repository for moderation case management."""

    @staticmethod
    async def get_next_case_number(session: AsyncSession) -> int:
        result = await session.execute(select(func.max(ModerationCase.case_number)))
        max_num = result.scalar()
        return (max_num or 0) + 1

    @staticmethod
    async def create(session: AsyncSession, target_user_id: int, moderator_user_id: int,
                     action: ModerationAction, reason: str = None, duration: int = None,
                     channel_id: int = None, message_id: int = None,
                     target_username: str = None, moderator_username: str = None,
                     case_id: str = None, rule: str = None, policy_name: str = None,
                     channel_name: str = None, warning_id: str = None, severity: str = None,
                     dm_status: str = None, discord_log_status: str = None,
                     executor: str = "PB HERO AutoMod") -> ModerationCase:
        case_number = await ModerationCaseRepo.get_next_case_number(session)
        if not case_id:
            case_id = f"CASE-{case_number:04d}"
        case = ModerationCase(
            case_number=case_number,
            case_id=case_id,
            target_user_id=target_user_id,
            target_username=target_username,
            moderator_user_id=moderator_user_id,
            moderator_username=moderator_username,
            action=action,
            reason=reason,
            duration=duration,
            channel_id=channel_id,
            channel_name=channel_name,
            message_id=message_id,
            rule=rule,
            policy_name=policy_name,
            warning_id=warning_id,
            severity=severity,
            dm_status=dm_status,
            discord_log_status=discord_log_status,
            executor=executor,
        )
        session.add(case)
        await session.flush()
        return case

    @staticmethod
    async def get_by_case_number(session: AsyncSession, case_number: int) -> Optional[ModerationCase]:
        result = await session.execute(
            select(ModerationCase).where(ModerationCase.case_number == case_number)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_case_id(session: AsyncSession, case_id: str) -> Optional[ModerationCase]:
        result = await session.execute(
            select(ModerationCase).where(ModerationCase.case_id == case_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_for_user(session: AsyncSession, user_id: int, limit: int = 50) -> list[ModerationCase]:
        result = await session.execute(
            select(ModerationCase)
            .where(ModerationCase.target_user_id == user_id)
            .order_by(ModerationCase.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_recent(session: AsyncSession, limit: int = 50) -> list[ModerationCase]:
        result = await session.execute(
            select(ModerationCase).order_by(ModerationCase.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_today(session: AsyncSession) -> int:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count(ModerationCase.id)).where(ModerationCase.created_at >= today_start)
        )
        return result.scalar() or 0

    @staticmethod
    async def count_action_today(session: AsyncSession, action: ModerationAction) -> int:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count(ModerationCase.id)).where(
                ModerationCase.action == action,
                ModerationCase.created_at >= today_start,
            )
        )
        return result.scalar() or 0

    @staticmethod
    async def get_top_violations(session: AsyncSession, limit: int = 5) -> list[dict]:
        """Aggregate top violation reasons/rules."""
        result = await session.execute(
            select(ModerationCase.reason, func.count(ModerationCase.id).label("count"))
            .where(ModerationCase.reason.is_not(None))
            .group_by(ModerationCase.reason)
            .order_by(func.count(ModerationCase.id).desc())
            .limit(limit)
        )
        return [{"reason": row[0], "count": row[1]} for row in result.all()]


# ─── Blocked Messages ────────────────────────────────────────────────────────

class BlockedMessageRepo:
    """Repository for blocked message logging."""

    @staticmethod
    async def create(session: AsyncSession, channel_id: int, user_id: int,
                     reason: str, rule: str, message_id: int = None,
                     username: str = None, content_preview: str = None) -> BlockedMessage:
        blocked = BlockedMessage(
            channel_id=channel_id,
            user_id=user_id,
            username=username,
            message_id=message_id,
            content_preview=content_preview[:200] if content_preview else None,
            reason=reason,
            rule=rule,
        )
        session.add(blocked)
        await session.flush()
        return blocked

    @staticmethod
    async def count_today(session: AsyncSession) -> int:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count(BlockedMessage.id)).where(BlockedMessage.created_at >= today_start)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_recent(session: AsyncSession, limit: int = 100) -> list[BlockedMessage]:
        result = await session.execute(
            select(BlockedMessage).order_by(BlockedMessage.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


# ─── Audit Logs ───────────────────────────────────────────────────────────────

class AuditLogRepo:
    """Repository for dashboard audit trail."""

    @staticmethod
    async def log(session: AsyncSession, actor: str, action: str,
                  target: str = None, details: str = None, ip_address: str = None) -> AuditLog:
        entry = AuditLog(actor=actor, action=action, target=target, details=details, ip_address=ip_address)
        session.add(entry)
        await session.flush()
        return entry

    @staticmethod
    async def get_recent(session: AsyncSession, limit: int = 100) -> list[AuditLog]:
        result = await session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


# ─── Exemption Rules ─────────────────────────────────────────────────────────

class ExemptionRuleRepo:
    """Repository for moderation exemption rules."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[ExemptionRule]:
        result = await session.execute(select(ExemptionRule))
        return list(result.scalars().all())

    @staticmethod
    async def is_exempt(session: AsyncSession, rule_type: str, target_id: int,
                        check_for: str = "all") -> bool:
        result = await session.execute(
            select(func.count(ExemptionRule.id)).where(
                ExemptionRule.rule_type == rule_type,
                ExemptionRule.target_id == target_id,
                ExemptionRule.exempt_from.in_([check_for, "all"]),
            )
        )
        return (result.scalar() or 0) > 0

    @staticmethod
    async def add(session: AsyncSession, rule_type: str, target_id: int,
                  target_name: str = None, exempt_from: str = "all") -> ExemptionRule:
        rule = ExemptionRule(rule_type=rule_type, target_id=target_id,
                            target_name=target_name, exempt_from=exempt_from)
        session.add(rule)
        await session.flush()
        return rule

    @staticmethod
    async def remove(session: AsyncSession, rule_id: int) -> bool:
        result = await session.execute(delete(ExemptionRule).where(ExemptionRule.id == rule_id))
        return result.rowcount > 0


# ─── Server Config ───────────────────────────────────────────────────────────

class ServerConfigRepo:
    """Repository for single-server configuration."""

    @staticmethod
    async def get(session: AsyncSession) -> Optional[ServerConfig]:
        result = await session.execute(select(ServerConfig).limit(1))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create(session: AsyncSession) -> ServerConfig:
        config = await ServerConfigRepo.get(session)
        if not config:
            config = ServerConfig()
            session.add(config)
            await session.flush()
        return config

    @staticmethod
    async def update(session: AsyncSession, **kwargs) -> ServerConfig:
        from app.database.serializers import normalize_domain_list, serialize_json_field

        json_fields = ["admin_role_ids", "moderator_role_ids", "global_allowed_domains", "mod_log_events"]
        for jf in json_fields:
            if jf in kwargs:
                if jf == "global_allowed_domains":
                    kwargs[jf] = serialize_json_field(normalize_domain_list(kwargs[jf]))
                else:
                    kwargs[jf] = serialize_json_field(kwargs[jf])

        config = await ServerConfigRepo.get_or_create(session)
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        config.updated_at = datetime.utcnow()
        await session.flush()
        return config

    @staticmethod
    async def get_moderator_role_ids(session: AsyncSession) -> list[int]:
        config = await ServerConfigRepo.get(session)
        if config and config.moderator_role_ids:
            try:
                return json.loads(config.moderator_role_ids)
            except json.JSONDecodeError:
                return []
        return []

    @staticmethod
    async def get_admin_role_ids(session: AsyncSession) -> list[int]:
        config = await ServerConfigRepo.get(session)
        if config and config.admin_role_ids:
            try:
                return json.loads(config.admin_role_ids)
            except json.JSONDecodeError:
                return []
        return []


# ─── Moderation Exemptions (Granular Bypass) ───────────────────────────────────

class ModerationExemptionRepo:
    """Repository for granular moderation bypass rules."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[ModerationExemption]:
        result = await session.execute(
            select(ModerationExemption).order_by(ModerationExemption.target_type, ModerationExemption.target_name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(session: AsyncSession, exemption_id: int) -> Optional[ModerationExemption]:
        result = await session.execute(
            select(ModerationExemption).where(ModerationExemption.id == exemption_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, target_type: str, target_id: int, **kwargs) -> ModerationExemption:
        exemption = ModerationExemption(
            target_type=target_type.lower(),
            target_id=int(target_id),
            **kwargs,
        )
        session.add(exemption)
        await session.flush()
        return exemption

    @staticmethod
    async def update(session: AsyncSession, exemption_id: int, **kwargs) -> Optional[ModerationExemption]:
        exemption = await ModerationExemptionRepo.get_by_id(session, exemption_id)
        if not exemption:
            return None
        for key, value in kwargs.items():
            if hasattr(exemption, key) and key not in ("id", "created_at"):
                setattr(exemption, key, value)
        exemption.updated_at = datetime.utcnow()
        await session.flush()
        return exemption

    @staticmethod
    async def delete(session: AsyncSession, exemption_id: int) -> bool:
        result = await session.execute(
            delete(ModerationExemption).where(ModerationExemption.id == exemption_id)
        )
        return result.rowcount > 0

    @staticmethod
    async def check_exemption(
        session: AsyncSession,
        user_id: int,
        role_ids: list[int],
        is_bot: bool,
        channel_id: int,
        category_name: Optional[str] = None,
        channel_type: str = "text",
        rule_name: str = "all",
    ) -> tuple[bool, Optional[ModerationExemption]]:
        """
        Check if user/role/bot/channel is exempt from a specific moderation rule.

        Deterministic Precedence:
        1. Explicit user exemption
        2. Role exemption (highest priority role)
        3. Bot exemption
        4. Channel exemption
        5. Category exemption
        """
        exemptions = await ModerationExemptionRepo.get_all(session)
        if not exemptions:
            return False, None

        # Filter by scope relevance first
        def scope_matches(ex: ModerationExemption) -> bool:
            if ex.scope == "global":
                return True
            if ex.scope == "channel":
                return ex.scope_id == channel_id
            if ex.scope == "category":
                return (category_name and ex.scope_name and ex.scope_name.lower() == category_name.lower()) or (ex.scope_id and category_name and str(ex.scope_id) == str(category_name))
            if ex.scope == "channel_type":
                return ex.channel_type == channel_type
            return True

        def rule_matches(ex: ModerationExemption) -> bool:
            if ex.bypass_all:
                return True
            attr_name = f"bypass_{rule_name.lower()}"
            if hasattr(ex, attr_name):
                return bool(getattr(ex, attr_name))
            return False

        # 1. User exemption
        user_exs = [e for e in exemptions if e.target_type == "user" and e.target_id == user_id and scope_matches(e)]
        for ex in user_exs:
            if rule_matches(ex):
                return True, ex

        # 2. Role exemptions
        role_id_set = set(role_ids or [])
        role_exs = [e for e in exemptions if e.target_type == "role" and e.target_id in role_id_set and scope_matches(e)]
        for ex in role_exs:
            if rule_matches(ex):
                return True, ex

        # 3. Bot exemption
        if is_bot:
            bot_exs = [e for e in exemptions if e.target_type == "bot" and (e.target_id == 0 or e.target_id == user_id) and scope_matches(e)]
            for ex in bot_exs:
                if rule_matches(ex):
                    return True, ex

        # 4. Channel exemption (target_type == 'channel' or scope == 'channel')
        chan_exs = [e for e in exemptions if (e.target_type == "channel" and e.target_id == channel_id) or (e.scope == "channel" and e.scope_id == channel_id)]
        for ex in chan_exs:
            if rule_matches(ex):
                return True, ex

        # 5. Category exemption
        if category_name:
            cat_exs = [e for e in exemptions if (e.target_type == "category" and e.scope_name and e.scope_name.lower() == category_name.lower()) or (e.scope == "category" and e.scope_name and e.scope_name.lower() == category_name.lower())]
            for ex in cat_exs:
                if rule_matches(ex):
                    return True, ex

        return False, None


# ─── Automod Rules ────────────────────────────────────────────────────────────

class AutomodRuleRepo:
    """Repository for configurable automated detection and action rules."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[AutomodRule]:
        result = await session.execute(select(AutomodRule).order_by(AutomodRule.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(session: AsyncSession, rule_id: int) -> Optional[AutomodRule]:
        result = await session.execute(select(AutomodRule).where(AutomodRule.id == rule_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_type(session: AsyncSession, rule_type: str) -> Optional[AutomodRule]:
        result = await session.execute(select(AutomodRule).where(AutomodRule.rule_type == rule_type))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, rule_type: str, name: str, **kwargs) -> AutomodRule:
        from app.database.serializers import serialize_json_field

        # Normalize UI / API field aliases
        if "threshold_count" in kwargs and "threshold" not in kwargs:
            kwargs["threshold"] = kwargs.pop("threshold_count")
        if "time_window_seconds" in kwargs and "time_window" not in kwargs:
            kwargs["time_window"] = kwargs.pop("time_window_seconds")
        elif "window_seconds" in kwargs and "time_window" not in kwargs:
            kwargs["time_window"] = kwargs.pop("window_seconds")
        if "action_duration" in kwargs and "timeout_duration" not in kwargs:
            kwargs["timeout_duration"] = kwargs.pop("action_duration")
        elif "duration_seconds" in kwargs and "timeout_duration" not in kwargs:
            kwargs["timeout_duration"] = kwargs.pop("duration_seconds")
        if "cooldown_seconds" in kwargs and "cooldown" not in kwargs:
            kwargs["cooldown"] = kwargs.pop("cooldown_seconds")

        for jf in ("channels", "categories", "exemptions", "custom_keywords"):
            if jf in kwargs and not isinstance(kwargs[jf], str):
                kwargs[jf] = serialize_json_field(kwargs[jf])

        # Filter kwargs to valid model attributes
        valid_attrs = {c.name for c in AutomodRule.__table__.columns}
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_attrs}

        rule = AutomodRule(rule_type=rule_type, name=name, **filtered_kwargs)
        session.add(rule)
        await session.flush()
        return rule

    @staticmethod
    async def update(session: AsyncSession, rule_id: int, **kwargs) -> Optional[AutomodRule]:
        from app.database.serializers import serialize_json_field

        rule = await AutomodRuleRepo.get_by_id(session, rule_id)
        if not rule:
            return None

        # Normalize UI / API field aliases
        if "threshold_count" in kwargs and "threshold" not in kwargs:
            kwargs["threshold"] = kwargs.pop("threshold_count")
        if "time_window_seconds" in kwargs and "time_window" not in kwargs:
            kwargs["time_window"] = kwargs.pop("time_window_seconds")
        elif "window_seconds" in kwargs and "time_window" not in kwargs:
            kwargs["time_window"] = kwargs.pop("window_seconds")
        if "action_duration" in kwargs and "timeout_duration" not in kwargs:
            kwargs["timeout_duration"] = kwargs.pop("action_duration")
        elif "duration_seconds" in kwargs and "timeout_duration" not in kwargs:
            kwargs["timeout_duration"] = kwargs.pop("duration_seconds")
        if "cooldown_seconds" in kwargs and "cooldown" not in kwargs:
            kwargs["cooldown"] = kwargs.pop("cooldown_seconds")

        for jf in ("channels", "categories", "exemptions", "custom_keywords"):
            if jf in kwargs and not isinstance(kwargs[jf], str):
                kwargs[jf] = serialize_json_field(kwargs[jf])

        for key, value in kwargs.items():
            if hasattr(rule, key) and key not in ("id", "created_at"):
                setattr(rule, key, value)
        rule.updated_at = datetime.utcnow()
        await session.flush()
        return rule


    @staticmethod
    async def delete(session: AsyncSession, rule_id: int) -> bool:
        result = await session.execute(delete(AutomodRule).where(AutomodRule.id == rule_id))
        return result.rowcount > 0

    @staticmethod
    async def create_defaults(session: AsyncSession) -> None:
        """Seed professional default automod rules."""
        defaults = [
            {
                "rule_type": "keyword_filter",
                "name": "Keyword Filter",
                "description": "Scans message text for prohibited words, slurs, or patterns.",
                "threshold": 1,
                "action": "delete_warn",
                "severity": "medium",
                "enabled": True,
            },
            {
                "rule_type": "invite_filter",
                "name": "Invite Link Filter",
                "description": "Detects unauthorized Discord invite links (discord.gg, discord.com/invite).",
                "threshold": 1,
                "action": "delete_warn",
                "severity": "high",
                "enabled": True,
            },
            {
                "rule_type": "link_filter",
                "name": "Link Filter",
                "description": "Restricts external URLs according to channel and global allowlists.",
                "threshold": 1,
                "action": "delete_warn",
                "severity": "medium",
                "enabled": True,
            },
            {
                "rule_type": "mention_spam",
                "name": "Mention Spam",
                "description": "Detects excessive user or role mentions in a single message.",
                "threshold": 5,
                "action": "delete_timeout",
                "timeout_duration": 600,
                "severity": "high",
                "enabled": True,
            },
            {
                "rule_type": "message_spam",
                "name": "Message Spam",
                "description": "Rate-limits excessive message volume in a short window.",
                "threshold": 5,
                "time_window": 5,
                "action": "delete_timeout",
                "timeout_duration": 300,
                "severity": "medium",
                "enabled": True,
            },
            {
                "rule_type": "attachment_restriction",
                "name": "Attachment Restriction",
                "description": "Restricts mass file uploads or disallowed file extensions.",
                "threshold": 3,
                "action": "delete_warn",
                "severity": "low",
                "enabled": True,
            },
            {
                "rule_type": "repeated_message",
                "name": "Repeated Message Detection",
                "description": "Blocks duplicate copy-paste messages sent across channels.",
                "threshold": 3,
                "time_window": 10,
                "action": "delete_warn",
                "severity": "medium",
                "enabled": True,
            },
            {
                "rule_type": "caps_spam",
                "name": "Caps / Character Spam",
                "description": "Detects messages with excessive capital letters or repeated characters.",
                "threshold": 70,
                "action": "delete_warn",
                "severity": "low",
                "enabled": False,
            },
            {
                "rule_type": "flood_protection",
                "name": "Flood Protection",
                "description": "Emergency raid and flood suppression.",
                "threshold": 10,
                "time_window": 5,
                "action": "timeout",
                "timeout_duration": 900,
                "severity": "critical",
                "enabled": True,
            },
        ]
        for item in defaults:
            existing = await AutomodRuleRepo.get_by_type(session, item["rule_type"])
            if not existing:
                await AutomodRuleRepo.create(session, **item)


# ─── Warning Records ──────────────────────────────────────────────────────────

class WarningRecordRepo:
    """Repository for user warning records and active strikes."""

    @staticmethod
    async def get_next_warning_number(session: AsyncSession) -> int:
        result = await session.execute(select(func.count(WarningRecord.id)))
        return (result.scalar() or 0) + 1

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: int,
        username: str,
        rule: str,
        reason: str,
        channel_id: Optional[int] = None,
        channel_name: Optional[str] = None,
        severity: str = "medium",
        points: int = 1,
        moderator: str = "PB HERO AutoMod",
        action_taken: str = "warn",
        dm_status: str = "disabled",
        case_number: Optional[int] = None,
        case_id: Optional[str] = None,
        expires_days: int = 30,
        expires_at: Optional[datetime] = None,
    ) -> WarningRecord:
        from datetime import timedelta

        warn_num = await WarningRecordRepo.get_next_warning_number(session)
        warning_id = f"WARN-{warn_num:04d}"
        if not case_id:
            case_id = f"CASE-{warn_num:04d}"

        now = datetime.utcnow()
        if expires_at is None:
            expires_at = now + timedelta(days=expires_days) if expires_days > 0 else None

        record = WarningRecord(
            warning_id=warning_id,
            case_id=case_id,
            case_number=case_number,
            user_id=int(user_id),
            username=username,
            channel_id=int(channel_id) if channel_id else None,
            channel_name=channel_name,
            rule=rule,
            reason=reason,
            moderator=moderator,
            severity=severity.lower(),
            points=points,
            status="active",
            action_taken=action_taken,
            dm_status=dm_status,
            created_at=now,
            expires_at=expires_at,
        )
        session.add(record)
        await session.flush()
        return record

    @staticmethod
    async def get_all(session: AsyncSession, user_id: Optional[int] = None, limit: int = 100) -> list[WarningRecord]:
        query = select(WarningRecord)
        if user_id:
            query = query.where(WarningRecord.user_id == int(user_id))
        result = await session.execute(query.order_by(WarningRecord.created_at.desc()).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_warning_id(session: AsyncSession, warning_id: str) -> Optional[WarningRecord]:
        result = await session.execute(
            select(WarningRecord).where(WarningRecord.warning_id == warning_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_for_user(session: AsyncSession, user_id: int, decay_days: int = 30) -> list[WarningRecord]:
        """Fetch active warnings for a user, taking decay into account."""
        from datetime import timedelta

        now = datetime.utcnow()
        query = select(WarningRecord).where(
            WarningRecord.user_id == int(user_id),
            WarningRecord.status == "active",
            or_(WarningRecord.expires_at.is_(None), WarningRecord.expires_at > now),
        )
        if decay_days > 0:
            cutoff = now - timedelta(days=decay_days)
            query = query.where(WarningRecord.created_at >= cutoff)

        result = await session.execute(query.order_by(WarningRecord.created_at.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_user_strikes_and_points(session: AsyncSession, user_id: int, decay_days: int = 30) -> tuple[int, int]:
        active_list = await WarningRecordRepo.get_active_for_user(session, user_id, decay_days)
        strikes = len(active_list)
        points = sum(w.points or 1 for w in active_list)
        return strikes, points

    @staticmethod
    async def count_active_total(session: AsyncSession, decay_days: int = 30) -> int:
        from datetime import timedelta

        now = datetime.utcnow()
        query = select(func.count(WarningRecord.id)).where(
            WarningRecord.status == "active",
            or_(WarningRecord.expires_at.is_(None), WarningRecord.expires_at > now),
        )
        if decay_days > 0:
            cutoff = now - timedelta(days=decay_days)
            query = query.where(WarningRecord.created_at >= cutoff)
        result = await session.execute(query)
        return result.scalar() or 0

    @staticmethod
    async def count_today(session: AsyncSession) -> int:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count(WarningRecord.id)).where(WarningRecord.created_at >= today_start)
        )
        return result.scalar() or 0

    @staticmethod
    async def revoke(session: AsyncSession, warning_id: str | int, revoked_by: str, reason: Optional[str] = None) -> bool:
        query = select(WarningRecord)
        if isinstance(warning_id, int):
            query = query.where(WarningRecord.id == warning_id)
        elif str(warning_id).isdigit():
            query = query.where(or_(WarningRecord.id == int(warning_id), WarningRecord.warning_id == str(warning_id)))
        else:
            query = query.where(WarningRecord.warning_id == str(warning_id))
        result = await session.execute(query)
        record = result.scalar_one_or_none()
        if not record:
            return False
        record.status = "revoked"
        record.revoked_at = datetime.utcnow()
        record.revoked_by = revoked_by
        record.revoke_reason = reason or "Revoked by moderator"
        await session.flush()
        return True

    @staticmethod
    async def clear_user(session: AsyncSession, user_id: int, revoked_by: str) -> int:
        active = await WarningRecordRepo.get_active_for_user(session, user_id, decay_days=0)
        now = datetime.utcnow()
        for w in active:
            w.status = "revoked"
            w.revoked_at = now
            w.revoked_by = revoked_by
            w.revoke_reason = "All warnings cleared by moderator"
        await session.flush()
        return len(active)


# ─── Warning Escalation Rules ─────────────────────────────────────────────────

class WarningEscalationRepo:
    """Repository for configurable strike/point escalation ladder."""

    @staticmethod
    async def get_all(session: AsyncSession, mode: Optional[str] = None) -> list[WarningEscalationRule]:
        query = select(WarningEscalationRule)
        if mode:
            query = query.where(WarningEscalationRule.mode == mode)
        result = await session.execute(query.order_by(WarningEscalationRule.threshold.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(session: AsyncSession, rule_id: int) -> Optional[WarningEscalationRule]:
        result = await session.execute(
            select(WarningEscalationRule).where(WarningEscalationRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, threshold: int, mode: str, action: str, **kwargs) -> WarningEscalationRule:
        rule = WarningEscalationRule(threshold=threshold, mode=mode, action=action, **kwargs)
        session.add(rule)
        await session.flush()
        return rule

    @staticmethod
    async def update(session: AsyncSession, rule_id: int, **kwargs) -> Optional[WarningEscalationRule]:
        rule = await WarningEscalationRepo.get_by_id(session, rule_id)
        if not rule:
            return None
        for key, value in kwargs.items():
            if hasattr(rule, key) and key not in ("id", "created_at"):
                setattr(rule, key, value)
        rule.updated_at = datetime.utcnow()
        await session.flush()
        return rule

    @staticmethod
    async def delete(session: AsyncSession, rule_id: int) -> bool:
        result = await session.execute(
            delete(WarningEscalationRule).where(WarningEscalationRule.id == rule_id)
        )
        return result.rowcount > 0

    @staticmethod
    async def delete_all(session: AsyncSession) -> int:
        """Atomically delete all warning escalation rules."""
        result = await session.execute(delete(WarningEscalationRule))
        return result.rowcount

    @staticmethod
    async def find_escalation(session: AsyncSession, current_val: int, mode: str = "count") -> Optional[WarningEscalationRule]:
        """Find the matching escalation rule for the given threshold level."""
        rules = await WarningEscalationRepo.get_all(session, mode=mode)
        matched = None
        for r in rules:
            if r.threshold == current_val:
                return r
            if r.threshold <= current_val:
                matched = r
        return matched

    @staticmethod
    async def create_defaults(session: AsyncSession) -> None:
        """Seed standard professional warning escalation ladder."""
        count = await session.execute(select(func.count(WarningEscalationRule.id)))
        if (count.scalar() or 0) > 0:
            return

        ladder = [
            {"threshold": 1, "mode": "count", "action": "warn", "duration": None, "send_dm": True, "reason_template": "First warning: message policy violation"},
            {"threshold": 2, "mode": "count", "action": "warn", "duration": None, "send_dm": True, "reason_template": "Second warning: repeated policy violation"},
            {"threshold": 3, "mode": "count", "action": "timeout", "duration": 600, "send_dm": True, "reason_template": "Third violation: 10 minute timeout"},
            {"threshold": 4, "mode": "count", "action": "timeout", "duration": 3600, "send_dm": True, "reason_template": "Fourth violation: 1 hour timeout"},
            {"threshold": 5, "mode": "count", "action": "kick", "duration": None, "send_dm": True, "reason_template": "Fifth violation: removed from server"},
            {"threshold": 6, "mode": "count", "action": "ban", "duration": None, "send_dm": True, "delete_message_history_days": 1, "reason_template": "Sixth violation: permanently banned for repeated infractions"},
        ]
        for item in ladder:
            await WarningEscalationRepo.create(session, **item)


# ??? Server Greeting Settings ??????????????????????????????????????????????????

class ServerGreetingSettingsRepo:
    """Repository for server welcome and goodbye automation settings."""

    DEFAULT_WELCOME_TITLE = "?? Welcome to {server_name}!"
    DEFAULT_WELCOME_DESCRIPTION = "Welcome {user_mention} to **{server_name}**! ??\n\nYou are member **#{member_count}**.\n\nPlease check the rules and enjoy your stay!"
    DEFAULT_WELCOME_FOOTER = "PB HERO SERVER"

    DEFAULT_GOODBYE_TITLE = "?? Goodbye {display_name}"
    DEFAULT_GOODBYE_DESCRIPTION = "**{display_name}** has left **{server_name}**.\n\nWe had **{member_count} members** before the departure."
    DEFAULT_GOODBYE_FOOTER = "PB HERO SERVER"

    DEFAULT_WELCOME_DM_TITLE = "?? Welcome to {server_name}!"
    DEFAULT_WELCOME_DM_DESCRIPTION = "Hi {display_name}! ??\n\nThanks for joining our Discord server.\n\n?? Please read the server rules:\n{rules_url}\n\n?? Server Invite:\n{invite_url}\n\nEnjoy the community!"
    DEFAULT_WELCOME_DM_FOOTER = "PB HERO SERVER"

    DEFAULT_GOODBYE_DM_TITLE = "?? Goodbye {display_name}"
    DEFAULT_GOODBYE_DM_DESCRIPTION = "You have left {server_name}.\n\nWe\'re sorry to see you go. ??\n\nIf you ever want to come back:\n?? Rejoin Server:\n{invite_url}\n\nTake care!"
    DEFAULT_GOODBYE_DM_FOOTER = "PB HERO SERVER"

    DEFAULT_RULES_TITLE = "?? {server_name} RULES"
    DEFAULT_RULES_DESCRIPTION = "1. Respect all members.\n2. No spam or unsolicited promotions.\n3. No offensive or harmful content.\n4. Follow channel guidelines and moderator instructions.\n\nPlease read the full rules before chatting!"
    DEFAULT_RULES_FOOTER = "PB HERO SERVER"

    @staticmethod
    async def get(session: AsyncSession, guild_id: int) -> Optional[ServerGreetingSettings]:
        result = await session.execute(
            select(ServerGreetingSettings).where(ServerGreetingSettings.guild_id == guild_id).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create(session: AsyncSession, guild_id: int) -> ServerGreetingSettings:
        settings_row = await ServerGreetingSettingsRepo.get(session, guild_id)
        if not settings_row:
            settings_row = ServerGreetingSettings(
                guild_id=guild_id,
                welcome_enabled=False,
                welcome_channel_id=None,
                welcome_title=ServerGreetingSettingsRepo.DEFAULT_WELCOME_TITLE,
                welcome_description=ServerGreetingSettingsRepo.DEFAULT_WELCOME_DESCRIPTION,
                welcome_footer=ServerGreetingSettingsRepo.DEFAULT_WELCOME_FOOTER,
                welcome_mention_user=True,
                welcome_show_avatar=True,
                welcome_show_server_icon=True,
                welcome_show_member_count=True,
                welcome_show_timestamp=True,
                welcome_use_embed=True,
                goodbye_enabled=False,
                goodbye_channel_id=None,
                goodbye_title=ServerGreetingSettingsRepo.DEFAULT_GOODBYE_TITLE,
                goodbye_description=ServerGreetingSettingsRepo.DEFAULT_GOODBYE_DESCRIPTION,
                goodbye_footer=ServerGreetingSettingsRepo.DEFAULT_GOODBYE_FOOTER,
                goodbye_mention_user=False,
                goodbye_show_avatar=True,
                goodbye_show_server_icon=True,
                goodbye_show_member_count=True,
                goodbye_show_timestamp=True,
                goodbye_use_embed=True,
                allow_mass_mentions=False,
                rules_delivery_enabled=False,
                rules_source="rules_channel",
                rules_channel_id=None,
                rules_title=ServerGreetingSettingsRepo.DEFAULT_RULES_TITLE,
                rules_description=ServerGreetingSettingsRepo.DEFAULT_RULES_DESCRIPTION,
                rules_footer=ServerGreetingSettingsRepo.DEFAULT_RULES_FOOTER,
                rules_button_text="Read Full Rules",
                auto_role_enabled=False,
                auto_role_id=None,
                welcome_dm_enabled=False,
                welcome_dm_title=ServerGreetingSettingsRepo.DEFAULT_WELCOME_DM_TITLE,
                welcome_dm_description=ServerGreetingSettingsRepo.DEFAULT_WELCOME_DM_DESCRIPTION,
                welcome_dm_footer=ServerGreetingSettingsRepo.DEFAULT_WELCOME_DM_FOOTER,
                welcome_dm_use_embed=True,
                welcome_dm_show_avatar=True,
                welcome_dm_show_server_icon=True,
                welcome_dm_show_timestamp=True,
                goodbye_dm_enabled=False,
                goodbye_dm_title=ServerGreetingSettingsRepo.DEFAULT_GOODBYE_DM_TITLE,
                goodbye_dm_description=ServerGreetingSettingsRepo.DEFAULT_GOODBYE_DM_DESCRIPTION,
                goodbye_dm_footer=ServerGreetingSettingsRepo.DEFAULT_GOODBYE_DM_FOOTER,
                goodbye_dm_use_embed=True,
                goodbye_dm_show_avatar=True,
                goodbye_dm_show_server_icon=True,
                goodbye_dm_show_timestamp=True,
            )
            session.add(settings_row)
            await session.flush()
        return settings_row

    @staticmethod
    async def update(session: AsyncSession, guild_id: int, **kwargs) -> ServerGreetingSettings:
        settings_row = await ServerGreetingSettingsRepo.get_or_create(session, guild_id)
        for key, value in kwargs.items():
            if hasattr(settings_row, key) and key not in ("id", "guild_id", "created_at"):
                setattr(settings_row, key, value)
        settings_row.updated_at = datetime.utcnow()
        await session.flush()
        return settings_row

    @staticmethod
    async def reset_welcome(session: AsyncSession, guild_id: int) -> ServerGreetingSettings:
        settings_row = await ServerGreetingSettingsRepo.get_or_create(session, guild_id)
        settings_row.welcome_title = ServerGreetingSettingsRepo.DEFAULT_WELCOME_TITLE
        settings_row.welcome_description = ServerGreetingSettingsRepo.DEFAULT_WELCOME_DESCRIPTION
        settings_row.welcome_footer = ServerGreetingSettingsRepo.DEFAULT_WELCOME_FOOTER
        settings_row.welcome_mention_user = True
        settings_row.welcome_show_avatar = True
        settings_row.welcome_show_server_icon = True
        settings_row.welcome_show_member_count = True
        settings_row.welcome_show_timestamp = True
        settings_row.welcome_use_embed = True
        settings_row.updated_at = datetime.utcnow()
        await session.flush()
        return settings_row

    @staticmethod
    async def reset_goodbye(session: AsyncSession, guild_id: int) -> ServerGreetingSettings:
        settings_row = await ServerGreetingSettingsRepo.get_or_create(session, guild_id)
        settings_row.goodbye_title = ServerGreetingSettingsRepo.DEFAULT_GOODBYE_TITLE
        settings_row.goodbye_description = ServerGreetingSettingsRepo.DEFAULT_GOODBYE_DESCRIPTION
        settings_row.goodbye_footer = ServerGreetingSettingsRepo.DEFAULT_GOODBYE_FOOTER
        settings_row.goodbye_mention_user = False
        settings_row.goodbye_show_avatar = True
        settings_row.goodbye_show_server_icon = True
        settings_row.goodbye_show_member_count = True
        settings_row.goodbye_show_timestamp = True
        settings_row.goodbye_use_embed = True
        settings_row.updated_at = datetime.utcnow()
        await session.flush()
        return settings_row

    @staticmethod
    async def reset_welcome_dm(session: AsyncSession, guild_id: int) -> ServerGreetingSettings:
        settings_row = await ServerGreetingSettingsRepo.get_or_create(session, guild_id)
        settings_row.welcome_dm_title = ServerGreetingSettingsRepo.DEFAULT_WELCOME_DM_TITLE
        settings_row.welcome_dm_description = ServerGreetingSettingsRepo.DEFAULT_WELCOME_DM_DESCRIPTION
        settings_row.welcome_dm_footer = ServerGreetingSettingsRepo.DEFAULT_WELCOME_DM_FOOTER
        settings_row.welcome_dm_use_embed = True
        settings_row.welcome_dm_show_avatar = True
        settings_row.welcome_dm_show_server_icon = True
        settings_row.welcome_dm_show_timestamp = True
        settings_row.updated_at = datetime.utcnow()
        await session.flush()
        return settings_row

    @staticmethod
    async def reset_goodbye_dm(session: AsyncSession, guild_id: int) -> ServerGreetingSettings:
        settings_row = await ServerGreetingSettingsRepo.get_or_create(session, guild_id)
        settings_row.goodbye_dm_title = ServerGreetingSettingsRepo.DEFAULT_GOODBYE_DM_TITLE
        settings_row.goodbye_dm_description = ServerGreetingSettingsRepo.DEFAULT_GOODBYE_DM_DESCRIPTION
        settings_row.goodbye_dm_footer = ServerGreetingSettingsRepo.DEFAULT_GOODBYE_DM_FOOTER
        settings_row.goodbye_dm_use_embed = True
        settings_row.goodbye_dm_show_avatar = True
        settings_row.goodbye_dm_show_server_icon = True
        settings_row.goodbye_dm_show_timestamp = True
        settings_row.updated_at = datetime.utcnow()
        await session.flush()
        return settings_row

    @staticmethod
    async def reset_rules(session: AsyncSession, guild_id: int) -> ServerGreetingSettings:
        settings_row = await ServerGreetingSettingsRepo.get_or_create(session, guild_id)
        settings_row.rules_title = ServerGreetingSettingsRepo.DEFAULT_RULES_TITLE
        settings_row.rules_description = ServerGreetingSettingsRepo.DEFAULT_RULES_DESCRIPTION
        settings_row.rules_footer = ServerGreetingSettingsRepo.DEFAULT_RULES_FOOTER
        settings_row.rules_button_text = "Read Full Rules"
        settings_row.updated_at = datetime.utcnow()
        await session.flush()
        return settings_row


class ServerInviteSettingsRepo:
    """Repository for permanent reusable server invitation settings."""

    @staticmethod
    async def get(session: AsyncSession, guild_id: int) -> Optional[ServerInviteSettings]:
        result = await session.execute(
            select(ServerInviteSettings).where(ServerInviteSettings.guild_id == guild_id).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create(session: AsyncSession, guild_id: int) -> ServerInviteSettings:
        invite_row = await ServerInviteSettingsRepo.get(session, guild_id)
        if not invite_row:
            invite_row = ServerInviteSettings(
                guild_id=guild_id,
                invite_channel_id=None,
                invite_code=None,
                invite_url=None,
                is_active=True,
                max_age=0,
                max_uses=0,
                temporary=False,
                last_verified_at=None,
                verification_status="not_generated",
                verification_error=None,
            )
            session.add(invite_row)
            await session.flush()
        return invite_row

    @staticmethod
    async def update(session: AsyncSession, guild_id: int, **kwargs) -> ServerInviteSettings:
        invite_row = await ServerInviteSettingsRepo.get_or_create(session, guild_id)
        for key, value in kwargs.items():
            if hasattr(invite_row, key) and key not in ("id", "guild_id", "created_at"):
                setattr(invite_row, key, value)
        invite_row.updated_at = datetime.utcnow()
        await session.flush()
        return invite_row


# ─── Custom Moderation Styles ────────────────────────────────────────────────

class CustomModerationStyleRepo:
    """Repository for user-defined custom moderation style presets."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[CustomModerationStyle]:
        result = await session.execute(
            select(CustomModerationStyle).order_by(CustomModerationStyle.name.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(session: AsyncSession, style_id: int) -> Optional[CustomModerationStyle]:
        result = await session.execute(
            select(CustomModerationStyle).where(CustomModerationStyle.id == style_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(session: AsyncSession, name: str) -> Optional[CustomModerationStyle]:
        result = await session.execute(
            select(CustomModerationStyle).where(func.lower(CustomModerationStyle.name) == name.strip().lower())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        session: AsyncSession,
        name: str,
        ladder: list[dict] | str,
        description: Optional[str] = None,
        warning_decay_days: int = 30,
        allow_warning_expiration: bool = True,
        warning_mode: str = "count",
        is_builtin: bool = False,
    ) -> CustomModerationStyle:
        ladder_json = json.dumps(ladder) if isinstance(ladder, list) else str(ladder)
        style = CustomModerationStyle(
            name=name.strip(),
            description=description.strip() if description else None,
            warning_decay_days=warning_decay_days,
            allow_warning_expiration=allow_warning_expiration,
            warning_mode=warning_mode,
            ladder=ladder_json,
            is_builtin=is_builtin,
        )
        session.add(style)
        await session.flush()
        return style

    @staticmethod
    async def update(session: AsyncSession, style_id: int, **kwargs) -> Optional[CustomModerationStyle]:
        style = await CustomModerationStyleRepo.get_by_id(session, style_id)
        if not style:
            return None
        for key, value in kwargs.items():
            if key == "ladder" and isinstance(value, list):
                value = json.dumps(value)
            if hasattr(style, key) and key not in ("id", "created_at"):
                setattr(style, key, value)
        style.updated_at = datetime.utcnow()
        await session.flush()
        return style

    @staticmethod
    async def delete(session: AsyncSession, style_id: int) -> bool:
        result = await session.execute(
            delete(CustomModerationStyle).where(CustomModerationStyle.id == style_id)
        )
        return result.rowcount > 0
