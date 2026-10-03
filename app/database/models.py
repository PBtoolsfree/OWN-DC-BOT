"""
PB HERO Database Models - SQLAlchemy ORM models.

Single-server architecture: all records belong to the one configured Guild.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base model class."""
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class EventType(str, enum.Enum):
    """YouTube event types."""
    UPLOAD = "upload"
    SCHEDULED_LIVE = "scheduled_live"
    LIVE_STARTED = "live_started"
    PREMIERE = "premiere"


class EventStatus(str, enum.Enum):
    """YouTube event notification status."""
    DETECTED = "detected"
    NOTIFIED = "notified"
    FAILED = "failed"
    SKIPPED = "skipped"


class VideoState(str, enum.Enum):
    """YouTube video live state."""
    UPCOMING = "upcoming"
    LIVE = "live"
    ENDED = "ended"
    PREMIERE = "premiere"
    REGULAR_VIDEO = "regular_video"
    UNKNOWN = "unknown"


class ModerationAction(str, enum.Enum):
    """Moderation action types."""
    WARN = "warn"
    TIMEOUT = "timeout"
    UNTIMEOUT = "untimeout"
    KICK = "kick"
    BAN = "ban"
    UNBAN = "unban"
    CLEAR = "clear"
    PURGE = "purge"
    LOCK = "lock"
    UNLOCK = "unlock"
    SLOWMODE = "slowmode"


class PolicyValue(str, enum.Enum):
    """Channel policy permission value."""
    ALLOW = "allow"
    DENY = "deny"
    INHERIT = "inherit"


# ─── Models ───────────────────────────────────────────────────────────────────

class AppConfig(Base):
    """Application configuration key-value store (no secrets)."""
    __tablename__ = "app_config"

    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminUser(Base):
    """Dashboard admin users."""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class YouTubeChannel(Base):
    """Monitored YouTube channels."""
    __tablename__ = "youtube_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    youtube_channel_id = Column(String(64), unique=True, nullable=False, index=True)
    channel_name = Column(String(255), nullable=False, default="Unknown")
    handle = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    feed_url = Column(String(512), nullable=False)
    last_checked_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    destinations = relationship("YouTubeDestination", back_populates="channel", cascade="all, delete-orphan")
    events = relationship("YouTubeEvent", back_populates="channel", cascade="all, delete-orphan")


class YouTubeDestination(Base):
    """YouTube notification destination mapping."""
    __tablename__ = "youtube_destinations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    youtube_channel_id = Column(String(64), ForeignKey("youtube_channels.youtube_channel_id", ondelete="CASCADE"), nullable=False)
    discord_channel_id = Column(BigInteger, nullable=False)
    notification_role_id = Column(BigInteger, nullable=True)
    upload_enabled = Column(Boolean, default=True, nullable=False)
    scheduled_live_enabled = Column(Boolean, default=True, nullable=False)
    live_started_enabled = Column(Boolean, default=True, nullable=False)
    premiere_enabled = Column(Boolean, default=True, nullable=False)
    custom_template = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    channel = relationship("YouTubeChannel", back_populates="destinations")

    __table_args__ = (
        UniqueConstraint("youtube_channel_id", "discord_channel_id", name="uq_yt_dest"),
    )


class YouTubeEvent(Base):
    """YouTube events for deduplication and history."""
    __tablename__ = "youtube_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    youtube_channel_id = Column(String(64), ForeignKey("youtube_channels.youtube_channel_id", ondelete="CASCADE"), nullable=False)
    video_id = Column(String(32), nullable=False, index=True)
    event_type = Column(Enum(EventType), nullable=False)
    title = Column(String(512), nullable=True)
    video_url = Column(String(512), nullable=True)
    published_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    notified_at = Column(DateTime, nullable=True)
    status = Column(Enum(EventStatus), default=EventStatus.DETECTED)
    live_state = Column(Enum(VideoState), nullable=True)

    # Relationships
    channel = relationship("YouTubeChannel", back_populates="events")

    __table_args__ = (
        UniqueConstraint("youtube_channel_id", "video_id", "event_type", name="uq_yt_event"),
        Index("ix_yt_event_lookup", "youtube_channel_id", "video_id"),
    )


class YouTubeNotificationTemplate(Base):
    """Notification template per YouTube event type (single-server)."""
    __tablename__ = "youtube_notification_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(Enum(EventType), nullable=False, unique=True, index=True)
    title_template = Column(String(256), nullable=False)
    description_template = Column(Text, nullable=False)
    mention_role = Column(String(128), nullable=True)
    footer_text = Column(String(256), nullable=True)
    show_thumbnail = Column(Boolean, default=True, nullable=False)
    show_timestamp = Column(Boolean, default=True, nullable=False)
    enable_button = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChannelPolicy(Base):
    """Channel-specific moderation policies."""
    __tablename__ = "channel_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_channel_id = Column(BigInteger, unique=True, nullable=False, index=True)
    channel_name = Column(String(255), nullable=True)
    category_name = Column(String(255), nullable=True)
    channel_type = Column(String(32), default="text")

    # Message content policies
    allow_text = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_links = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_images = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_videos = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_files = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_stickers = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)

    # Mention policies
    allow_everyone = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_here = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_role_mentions = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_user_mentions = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)

    # Advanced
    allowed_domains = Column(Text, nullable=True)  # JSON list of allowed domains
    preset_name = Column(String(64), nullable=True)
    warning_message = Column(Text, nullable=True)
    log_violations = Column(Boolean, default=True)
    delete_violations = Column(Boolean, default=True)
    warn_on_violation = Column(Boolean, default=True)
    enabled = Column(Boolean, default=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(255), nullable=True)


class PolicyProfile(Base):
    """Reusable policy presets/profiles."""
    __tablename__ = "policy_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    allow_text = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_links = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_images = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_videos = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_files = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_stickers = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_everyone = Column(Enum(PolicyValue), default=PolicyValue.DENY)
    allow_here = Column(Enum(PolicyValue), default=PolicyValue.DENY)
    allow_role_mentions = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_user_mentions = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)

    allowed_domains = Column(Text, nullable=True)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RoleOverride(Base):
    """Role-specific policy overrides for channels."""
    __tablename__ = "role_overrides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_channel_id = Column(BigInteger, nullable=False)
    role_id = Column(BigInteger, nullable=False)

    allow_links = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_images = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_videos = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_files = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_everyone = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_here = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_role_mentions = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_user_mentions = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)

    __table_args__ = (
        UniqueConstraint("discord_channel_id", "role_id", name="uq_role_override"),
    )


class ModerationCase(Base):
    """Moderation action case log."""
    __tablename__ = "moderation_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_number = Column(Integer, unique=True, nullable=False, index=True)
    target_user_id = Column(BigInteger, nullable=False, index=True)
    target_username = Column(String(255), nullable=True)
    moderator_user_id = Column(BigInteger, nullable=False)
    moderator_username = Column(String(255), nullable=True)
    action = Column(Enum(ModerationAction), nullable=False)
    reason = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    channel_id = Column(BigInteger, nullable=True)
    message_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BlockedMessage(Base):
    """Log of messages blocked by policy engine."""
    __tablename__ = "blocked_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    message_id = Column(BigInteger, nullable=True)
    content_preview = Column(String(200), nullable=True)
    reason = Column(Text, nullable=False)
    rule = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_blocked_msg_channel", "channel_id", "created_at"),
    )


class AuditLog(Base):
    """Dashboard audit trail."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    target = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExemptionRule(Base):
    """Exemption rules for moderation policies."""
    __tablename__ = "exemption_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_type = Column(String(32), nullable=False)  # 'role', 'user', 'channel'
    target_id = Column(BigInteger, nullable=False)
    target_name = Column(String(255), nullable=True)
    exempt_from = Column(String(64), default="all")  # 'all', 'links', 'mentions', etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("rule_type", "target_id", "exempt_from", name="uq_exemption"),
    )


class ServerConfig(Base):
    """Server-level configuration for the single guild."""
    __tablename__ = "server_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mod_log_channel_id = Column(BigInteger, nullable=True)
    admin_role_ids = Column(Text, nullable=True)  # JSON list
    moderator_role_ids = Column(Text, nullable=True)  # JSON list
    global_allowed_domains = Column(Text, nullable=True)  # JSON list
    warning_message_template = Column(Text, nullable=True)
    default_timeout_duration = Column(Integer, default=300)  # seconds
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
