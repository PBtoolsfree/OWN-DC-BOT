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

    allow = "allow"
    deny = "deny"
    inherit = "inherit"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            val_lower = value.lower()
            for member in cls:
                if member.value.lower() == val_lower or member.name.lower() == val_lower:
                    return member
        return None


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

    # Voice policies
    allow_connect = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_speak = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_video = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_stream = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_soundboard = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_voice_activity = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_priority_speaker = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_mute_members = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_deafen_members = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)
    allow_move_members = Column(Enum(PolicyValue), default=PolicyValue.INHERIT)

    # Advanced
    allowed_domains = Column(Text, nullable=True)  # JSON list of allowed domains
    preset_name = Column(String(64), nullable=True)
    warning_message = Column(Text, nullable=True)
    log_violations = Column(Boolean, default=True)
    delete_violations = Column(Boolean, default=True)
    warn_on_violation = Column(Boolean, default=True)
    send_dm_warning = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(255), nullable=True)


class PolicyProfile(Base):
    """Reusable policy presets/profiles."""
    __tablename__ = "policy_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(64), default="General", nullable=True)
    policy_type = Column(String(32), default="text")  # 'text', 'voice', 'general'

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

    # Voice policies
    allow_connect = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_speak = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_video = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_stream = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_soundboard = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_voice_activity = Column(Enum(PolicyValue), default=PolicyValue.ALLOW)
    allow_priority_speaker = Column(Enum(PolicyValue), default=PolicyValue.DENY)
    allow_mute_members = Column(Enum(PolicyValue), default=PolicyValue.DENY)
    allow_deafen_members = Column(Enum(PolicyValue), default=PolicyValue.DENY)
    allow_move_members = Column(Enum(PolicyValue), default=PolicyValue.DENY)

    allowed_domains = Column(Text, nullable=True)
    delete_violations = Column(Boolean, default=True)
    warn_on_violation = Column(Boolean, default=True)
    log_violations = Column(Boolean, default=True)
    send_dm_warning = Column(Boolean, default=False)
    warning_message = Column(Text, nullable=True)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    case_id = Column(String(64), nullable=True, index=True)
    target_user_id = Column(BigInteger, nullable=False, index=True)
    target_username = Column(String(255), nullable=True)
    moderator_user_id = Column(BigInteger, nullable=False)
    moderator_username = Column(String(255), nullable=True)
    action = Column(Enum(ModerationAction), nullable=False)
    reason = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    channel_id = Column(BigInteger, nullable=True)
    channel_name = Column(String(255), nullable=True)
    message_id = Column(BigInteger, nullable=True)
    rule = Column(String(128), nullable=True)
    policy_name = Column(String(128), nullable=True)
    warning_id = Column(String(64), nullable=True)
    severity = Column(String(32), nullable=True)
    dm_status = Column(String(32), nullable=True)
    discord_log_status = Column(String(32), nullable=True)
    executor = Column(String(128), default="PB HERO AutoMod")
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
    """Legacy exemption rules for moderation policies."""
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


class ModerationExemption(Base):
    """Granular moderation bypass rules for users, roles, bots, and webhooks."""
    __tablename__ = "moderation_exemptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_type = Column(String(32), nullable=False)  # 'user', 'role', 'bot', 'webhook'
    target_id = Column(BigInteger, nullable=False, index=True)
    target_name = Column(String(255), nullable=True)
    scope = Column(String(32), default="global")  # 'global', 'category', 'channel', 'channel_type'
    scope_id = Column(BigInteger, nullable=True)
    scope_name = Column(String(255), nullable=True)
    channel_type = Column(String(32), nullable=True)  # 'text', 'voice', 'thread'

    # Granular permission bypasses
    bypass_all = Column(Boolean, default=False)
    bypass_text = Column(Boolean, default=True)
    bypass_links = Column(Boolean, default=True)
    bypass_images = Column(Boolean, default=True)
    bypass_videos = Column(Boolean, default=True)
    bypass_files = Column(Boolean, default=True)
    bypass_stickers = Column(Boolean, default=True)
    bypass_mentions = Column(Boolean, default=True)
    bypass_spam = Column(Boolean, default=True)
    bypass_keywords = Column(Boolean, default=True)
    bypass_invites = Column(Boolean, default=True)
    bypass_warnings = Column(Boolean, default=False)
    bypass_timeout = Column(Boolean, default=False)
    bypass_kick = Column(Boolean, default=False)
    bypass_ban = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AutomodRule(Base):
    """Configurable automated moderation detection and action rules."""
    __tablename__ = "automod_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_type = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
    scope = Column(String(32), default="global")  # 'global', 'channels', 'categories'
    channels = Column(Text, nullable=True)  # JSON list
    categories = Column(Text, nullable=True)  # JSON list
    threshold = Column(Integer, default=5)
    time_window = Column(Integer, default=5)  # seconds
    action = Column(String(64), default="delete_warn")
    timeout_duration = Column(Integer, default=600)  # seconds
    cooldown = Column(Integer, default=10)  # seconds
    exemptions = Column(Text, nullable=True)  # JSON list
    custom_keywords = Column(Text, nullable=True)  # JSON list
    log_event = Column(Boolean, default=True)
    severity = Column(String(32), default="medium")  # 'low', 'medium', 'high', 'critical'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WarningRecord(Base):
    """Audit records of user warnings."""
    __tablename__ = "warning_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    warning_id = Column(String(64), unique=True, nullable=False, index=True)
    case_id = Column(String(64), nullable=True, index=True)
    case_number = Column(Integer, nullable=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    channel_id = Column(BigInteger, nullable=True)
    channel_name = Column(String(255), nullable=True)
    rule = Column(String(128), nullable=False)
    reason = Column(Text, nullable=False)
    moderator = Column(String(255), default="PB HERO AutoMod")
    severity = Column(String(32), default="medium")  # 'low', 'medium', 'high', 'critical'
    points = Column(Integer, default=1)
    status = Column(String(32), default="active")  # 'active', 'expired', 'revoked'
    action_taken = Column(String(64), default="warn")
    dm_status = Column(String(32), default="disabled")  # 'delivered', 'failed', 'disabled'
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(String(255), nullable=True)
    revoke_reason = Column(Text, nullable=True)


class WarningEscalationRule(Base):
    """Configurable strike/point escalation ladder."""
    __tablename__ = "warning_escalation_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    threshold = Column(Integer, nullable=False)  # 1, 2, 3, etc.
    mode = Column(String(32), default="count")  # 'count' or 'point'
    action = Column(String(64), nullable=False)  # 'warn', 'timeout', 'kick', 'ban'
    duration = Column(Integer, nullable=True)  # seconds
    send_dm = Column(Boolean, default=True)
    delete_message_history_days = Column(Integer, default=0)
    reason_template = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ServerConfig(Base):
    """Server-level configuration for the single guild."""
    __tablename__ = "server_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mod_log_channel_id = Column(BigInteger, nullable=True)
    admin_role_ids = Column(Text, nullable=True)  # JSON list
    moderator_role_ids = Column(Text, nullable=True)  # JSON list
    global_allowed_domains = Column(Text, nullable=True)  # JSON list
    warning_message_template = Column(Text, nullable=True)
    mod_log_events = Column(Text, nullable=True)  # JSON list of enabled log events
    default_timeout_duration = Column(Integer, default=300)  # seconds
    warning_decay_days = Column(Integer, default=30)  # 0 = never expire
    warning_mode = Column(String(32), default="count")  # 'count' or 'point'
    quick_setup_style = Column(String(32), default="balanced")
    rate_limit_actions_per_min = Column(Integer, default=20)
    rate_limit_user_actions_per_min = Column(Integer, default=5)
    rate_limit_auto_bans_per_hour = Column(Integer, default=10)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ServerGreetingSettings(Base):
    """Server welcome and goodbye message configuration (single-server)."""
    __tablename__ = "server_greeting_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, unique=True, nullable=False, index=True)

    # Welcome Settings
    welcome_enabled = Column(Boolean, default=False, nullable=False)
    welcome_channel_id = Column(BigInteger, nullable=True)
    welcome_title = Column(String(256), nullable=True)
    welcome_description = Column(Text, nullable=True)
    welcome_footer = Column(String(256), nullable=True)
    welcome_mention_user = Column(Boolean, default=True, nullable=False)
    welcome_show_avatar = Column(Boolean, default=True, nullable=False)
    welcome_show_server_icon = Column(Boolean, default=True, nullable=False)
    welcome_show_member_count = Column(Boolean, default=True, nullable=False)
    welcome_show_timestamp = Column(Boolean, default=True, nullable=False)
    welcome_use_embed = Column(Boolean, default=True, nullable=False)

    # Goodbye Settings
    goodbye_enabled = Column(Boolean, default=False, nullable=False)
    goodbye_channel_id = Column(BigInteger, nullable=True)
    goodbye_title = Column(String(256), nullable=True)
    goodbye_description = Column(Text, nullable=True)
    goodbye_footer = Column(String(256), nullable=True)
    goodbye_mention_user = Column(Boolean, default=False, nullable=False)
    goodbye_show_avatar = Column(Boolean, default=True, nullable=False)
    goodbye_show_server_icon = Column(Boolean, default=True, nullable=False)
    goodbye_show_member_count = Column(Boolean, default=True, nullable=False)
    goodbye_show_timestamp = Column(Boolean, default=True, nullable=False)
    goodbye_use_embed = Column(Boolean, default=True, nullable=False)

    # Safety
    allow_mass_mentions = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
