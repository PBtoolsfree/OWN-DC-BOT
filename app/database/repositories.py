"""
PB HERO Database Repositories - Data access layer.

All repositories operate within the single configured Guild context.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AdminUser,
    AppConfig,
    AuditLog,
    BlockedMessage,
    ChannelPolicy,
    EventStatus,
    EventType,
    ExemptionRule,
    ModerationAction,
    ModerationCase,
    PolicyProfile,
    PolicyValue,
    RoleOverride,
    ServerConfig,
    YouTubeChannel,
    YouTubeDestination,
    YouTubeEvent,
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
    async def upsert(session: AsyncSession, channel_id: int, **kwargs) -> ChannelPolicy:
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
        result = await session.execute(select(PolicyProfile).order_by(PolicyProfile.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_name(session: AsyncSession, name: str) -> Optional[PolicyProfile]:
        result = await session.execute(select(PolicyProfile).where(PolicyProfile.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, name: str, **kwargs) -> PolicyProfile:
        profile = PolicyProfile(name=name, **kwargs)
        session.add(profile)
        await session.flush()
        return profile

    @staticmethod
    async def create_defaults(session: AsyncSession) -> None:
        """Create built-in policy presets."""
        defaults = [
            {
                "name": "GENERAL_CHAT",
                "description": "Standard chat: text, links, images, files allowed. @everyone/@here blocked.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.ALLOW,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.ALLOW,
                "allow_files": PolicyValue.ALLOW, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.ALLOW, "allow_user_mentions": PolicyValue.ALLOW,
                "is_builtin": True,
            },
            {
                "name": "NO_LINK_CHAT",
                "description": "Chat without links. Text and images allowed, no URLs or mentions.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            {
                "name": "IMAGE_ONLY",
                "description": "Only images allowed. No text, links, files, or mentions.",
                "allow_text": PolicyValue.DENY, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            {
                "name": "ANNOUNCEMENTS",
                "description": "Read-only for members. Only moderators/admins can post.",
                "allow_text": PolicyValue.DENY, "allow_links": PolicyValue.DENY,
                "allow_images": PolicyValue.DENY, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.DENY, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            {
                "name": "MEDIA",
                "description": "Media sharing: text, images, videos allowed. Links configurable.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.INHERIT,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.ALLOW,
                "allow_files": PolicyValue.ALLOW, "allow_stickers": PolicyValue.ALLOW,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.DENY,
                "is_builtin": True,
            },
            {
                "name": "SUPPORT",
                "description": "Support channel: text, images, links allowed. Threads enabled.",
                "allow_text": PolicyValue.ALLOW, "allow_links": PolicyValue.ALLOW,
                "allow_images": PolicyValue.ALLOW, "allow_videos": PolicyValue.DENY,
                "allow_files": PolicyValue.ALLOW, "allow_stickers": PolicyValue.DENY,
                "allow_everyone": PolicyValue.DENY, "allow_here": PolicyValue.DENY,
                "allow_role_mentions": PolicyValue.DENY, "allow_user_mentions": PolicyValue.ALLOW,
                "is_builtin": True,
            },
        ]

        for preset in defaults:
            existing = await PolicyProfileRepo.get_by_name(session, preset["name"])
            if not existing:
                await PolicyProfileRepo.create(session, **preset)


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
                     target_username: str = None, moderator_username: str = None) -> ModerationCase:
        case_number = await ModerationCaseRepo.get_next_case_number(session)
        case = ModerationCase(
            case_number=case_number,
            target_user_id=target_user_id,
            target_username=target_username,
            moderator_user_id=moderator_user_id,
            moderator_username=moderator_username,
            action=action,
            reason=reason,
            duration=duration,
            channel_id=channel_id,
            message_id=message_id,
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
