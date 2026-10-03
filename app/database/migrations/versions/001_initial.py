"""Initial migration - all tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # App Config
    op.create_table(
        "app_config",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime),
    )

    # Admin Users
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"])

    # YouTube Channels
    op.create_table(
        "youtube_channels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("youtube_channel_id", sa.String(64), unique=True, nullable=False),
        sa.Column("channel_name", sa.String(255), nullable=False, server_default="Unknown"),
        sa.Column("handle", sa.String(255), nullable=True),
        sa.Column("enabled", sa.Boolean, default=True, nullable=False),
        sa.Column("feed_url", sa.String(512), nullable=False),
        sa.Column("last_checked_at", sa.DateTime, nullable=True),
        sa.Column("last_success_at", sa.DateTime, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    op.create_index("ix_yt_channels_channel_id", "youtube_channels", ["youtube_channel_id"])

    # YouTube Destinations
    op.create_table(
        "youtube_destinations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("youtube_channel_id", sa.String(64),
                  sa.ForeignKey("youtube_channels.youtube_channel_id", ondelete="CASCADE"), nullable=False),
        sa.Column("discord_channel_id", sa.BigInteger, nullable=False),
        sa.Column("notification_role_id", sa.BigInteger, nullable=True),
        sa.Column("upload_enabled", sa.Boolean, default=True, nullable=False),
        sa.Column("scheduled_live_enabled", sa.Boolean, default=True, nullable=False),
        sa.Column("live_started_enabled", sa.Boolean, default=True, nullable=False),
        sa.Column("premiere_enabled", sa.Boolean, default=True, nullable=False),
        sa.Column("custom_template", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.UniqueConstraint("youtube_channel_id", "discord_channel_id", name="uq_yt_dest"),
    )

    # YouTube Events
    op.create_table(
        "youtube_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("youtube_channel_id", sa.String(64),
                  sa.ForeignKey("youtube_channels.youtube_channel_id", ondelete="CASCADE"), nullable=False),
        sa.Column("video_id", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("video_url", sa.String(512), nullable=True),
        sa.Column("published_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("detected_at", sa.DateTime),
        sa.Column("notified_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(32), default="detected"),
        sa.Column("live_state", sa.String(32), nullable=True),
        sa.UniqueConstraint("youtube_channel_id", "video_id", "event_type", name="uq_yt_event"),
    )
    op.create_index("ix_yt_event_video_id", "youtube_events", ["video_id"])
    op.create_index("ix_yt_event_lookup", "youtube_events", ["youtube_channel_id", "video_id"])

    # Channel Policies
    op.create_table(
        "channel_policies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("discord_channel_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("channel_name", sa.String(255), nullable=True),
        sa.Column("category_name", sa.String(255), nullable=True),
        sa.Column("channel_type", sa.String(32), server_default="text"),
        sa.Column("allow_text", sa.String(16), server_default="inherit"),
        sa.Column("allow_links", sa.String(16), server_default="inherit"),
        sa.Column("allow_images", sa.String(16), server_default="inherit"),
        sa.Column("allow_videos", sa.String(16), server_default="inherit"),
        sa.Column("allow_files", sa.String(16), server_default="inherit"),
        sa.Column("allow_stickers", sa.String(16), server_default="inherit"),
        sa.Column("allow_everyone", sa.String(16), server_default="inherit"),
        sa.Column("allow_here", sa.String(16), server_default="inherit"),
        sa.Column("allow_role_mentions", sa.String(16), server_default="inherit"),
        sa.Column("allow_user_mentions", sa.String(16), server_default="inherit"),
        sa.Column("allowed_domains", sa.Text, nullable=True),
        sa.Column("preset_name", sa.String(64), nullable=True),
        sa.Column("warning_message", sa.Text, nullable=True),
        sa.Column("log_violations", sa.Boolean, default=True),
        sa.Column("delete_violations", sa.Boolean, default=True),
        sa.Column("warn_on_violation", sa.Boolean, default=True),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )
    op.create_index("ix_channel_policies_channel_id", "channel_policies", ["discord_channel_id"])

    # Policy Profiles
    op.create_table(
        "policy_profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("allow_text", sa.String(16), server_default="allow"),
        sa.Column("allow_links", sa.String(16), server_default="allow"),
        sa.Column("allow_images", sa.String(16), server_default="allow"),
        sa.Column("allow_videos", sa.String(16), server_default="allow"),
        sa.Column("allow_files", sa.String(16), server_default="allow"),
        sa.Column("allow_stickers", sa.String(16), server_default="allow"),
        sa.Column("allow_everyone", sa.String(16), server_default="deny"),
        sa.Column("allow_here", sa.String(16), server_default="deny"),
        sa.Column("allow_role_mentions", sa.String(16), server_default="allow"),
        sa.Column("allow_user_mentions", sa.String(16), server_default="allow"),
        sa.Column("allowed_domains", sa.Text, nullable=True),
        sa.Column("is_builtin", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime),
    )

    # Role Overrides
    op.create_table(
        "role_overrides",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("discord_channel_id", sa.BigInteger, nullable=False),
        sa.Column("role_id", sa.BigInteger, nullable=False),
        sa.Column("allow_links", sa.String(16), server_default="inherit"),
        sa.Column("allow_images", sa.String(16), server_default="inherit"),
        sa.Column("allow_videos", sa.String(16), server_default="inherit"),
        sa.Column("allow_files", sa.String(16), server_default="inherit"),
        sa.Column("allow_everyone", sa.String(16), server_default="inherit"),
        sa.Column("allow_here", sa.String(16), server_default="inherit"),
        sa.Column("allow_role_mentions", sa.String(16), server_default="inherit"),
        sa.Column("allow_user_mentions", sa.String(16), server_default="inherit"),
        sa.UniqueConstraint("discord_channel_id", "role_id", name="uq_role_override"),
    )

    # Moderation Cases
    op.create_table(
        "moderation_cases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_number", sa.Integer, unique=True, nullable=False),
        sa.Column("target_user_id", sa.BigInteger, nullable=False),
        sa.Column("target_username", sa.String(255), nullable=True),
        sa.Column("moderator_user_id", sa.BigInteger, nullable=False),
        sa.Column("moderator_username", sa.String(255), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("duration", sa.Integer, nullable=True),
        sa.Column("channel_id", sa.BigInteger, nullable=True),
        sa.Column("message_id", sa.BigInteger, nullable=True),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_mod_cases_number", "moderation_cases", ["case_number"])
    op.create_index("ix_mod_cases_target", "moderation_cases", ["target_user_id"])

    # Blocked Messages
    op.create_table(
        "blocked_messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.BigInteger, nullable=False),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("message_id", sa.BigInteger, nullable=True),
        sa.Column("content_preview", sa.String(200), nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("rule", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_blocked_msg_channel", "blocked_messages", ["channel_id", "created_at"])

    # Audit Logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime),
    )

    # Exemption Rules
    op.create_table(
        "exemption_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.BigInteger, nullable=False),
        sa.Column("target_name", sa.String(255), nullable=True),
        sa.Column("exempt_from", sa.String(64), server_default="all"),
        sa.Column("created_at", sa.DateTime),
        sa.UniqueConstraint("rule_type", "target_id", "exempt_from", name="uq_exemption"),
    )

    # Server Config
    op.create_table(
        "server_config",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("mod_log_channel_id", sa.BigInteger, nullable=True),
        sa.Column("admin_role_ids", sa.Text, nullable=True),
        sa.Column("moderator_role_ids", sa.Text, nullable=True),
        sa.Column("global_allowed_domains", sa.Text, nullable=True),
        sa.Column("warning_message_template", sa.Text, nullable=True),
        sa.Column("default_timeout_duration", sa.Integer, server_default="300"),
        sa.Column("updated_at", sa.DateTime),
    )


def downgrade() -> None:
    op.drop_table("server_config")
    op.drop_table("exemption_rules")
    op.drop_table("audit_logs")
    op.drop_table("blocked_messages")
    op.drop_table("moderation_cases")
    op.drop_table("role_overrides")
    op.drop_table("policy_profiles")
    op.drop_table("channel_policies")
    op.drop_table("youtube_events")
    op.drop_table("youtube_destinations")
    op.drop_table("youtube_channels")
    op.drop_table("admin_users")
    op.drop_table("app_config")
