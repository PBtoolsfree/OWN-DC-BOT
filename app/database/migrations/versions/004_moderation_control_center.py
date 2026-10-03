"""Add moderation control center tables and voice policy columns

Revision ID: 004_moderation_control_center
Revises: 003_moderation_enhancements
Create Date: 2026-10-03 16:15:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_moderation_control_center"
down_revision: Union[str, None] = "003_moderation_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Update channel_policies table with voice policies
    if "channel_policies" in tables:
        cp_cols = [c["name"] for c in inspector.get_columns("channel_policies")]
        voice_cols = [
            "allow_connect", "allow_speak", "allow_video", "allow_stream",
            "allow_soundboard", "allow_voice_activity", "allow_priority_speaker",
            "allow_mute_members", "allow_deafen_members", "allow_move_members"
        ]
        for col_name in voice_cols:
            if col_name not in cp_cols:
                op.add_column("channel_policies", sa.Column(col_name, sa.String(16), server_default="INHERIT", nullable=True))
        for col_name in voice_cols:
            conn.execute(sa.text(f"UPDATE channel_policies SET {col_name}='INHERIT' WHERE {col_name}='inherit'"))

    # 2. Update policy_profiles table with policy_type and voice policies
    if "policy_profiles" in tables:
        pp_cols = [c["name"] for c in inspector.get_columns("policy_profiles")]
        if "policy_type" not in pp_cols:
            op.add_column("policy_profiles", sa.Column("policy_type", sa.String(32), server_default="text", nullable=True))
        
        voice_allow_cols = [
            "allow_connect", "allow_speak", "allow_video", "allow_stream",
            "allow_soundboard", "allow_voice_activity"
        ]
        for col_name in voice_allow_cols:
            if col_name not in pp_cols:
                op.add_column("policy_profiles", sa.Column(col_name, sa.String(16), server_default="ALLOW", nullable=True))
            conn.execute(sa.text(f"UPDATE policy_profiles SET {col_name}='ALLOW' WHERE {col_name}='allow'"))

        voice_deny_cols = [
            "allow_priority_speaker", "allow_mute_members", "allow_deafen_members", "allow_move_members"
        ]
        for col_name in voice_deny_cols:
            if col_name not in pp_cols:
                op.add_column("policy_profiles", sa.Column(col_name, sa.String(16), server_default="DENY", nullable=True))
            conn.execute(sa.text(f"UPDATE policy_profiles SET {col_name}='DENY' WHERE {col_name}='deny'"))

    # 3. Update moderation_cases with case_id, rule, etc.
    if "moderation_cases" in tables:
        mc_cols = [c["name"] for c in inspector.get_columns("moderation_cases")]
        new_mc_cols = {
            "case_id": sa.Column("case_id", sa.String(64), nullable=True),
            "rule": sa.Column("rule", sa.String(128), nullable=True),
            "policy_name": sa.Column("policy_name", sa.String(128), nullable=True),
            "channel_name": sa.Column("channel_name", sa.String(255), nullable=True),
            "warning_id": sa.Column("warning_id", sa.String(64), nullable=True),
            "severity": sa.Column("severity", sa.String(32), nullable=True),
            "dm_status": sa.Column("dm_status", sa.String(32), nullable=True),
            "discord_log_status": sa.Column("discord_log_status", sa.String(32), nullable=True),
            "executor": sa.Column("executor", sa.String(128), server_default="PB HERO AutoMod", nullable=True),
        }
        for col_name, col_obj in new_mc_cols.items():
            if col_name not in mc_cols:
                op.add_column("moderation_cases", col_obj)

    # 4. Update server_config with decay, mode, rate limits
    if "server_config" in tables:
        sc_cols = [c["name"] for c in inspector.get_columns("server_config")]
        new_sc_cols = {
            "warning_decay_days": sa.Column("warning_decay_days", sa.Integer, server_default="30", nullable=True),
            "warning_mode": sa.Column("warning_mode", sa.String(32), server_default="count", nullable=True),
            "quick_setup_style": sa.Column("quick_setup_style", sa.String(32), server_default="balanced", nullable=True),
            "rate_limit_actions_per_min": sa.Column("rate_limit_actions_per_min", sa.Integer, server_default="20", nullable=True),
            "rate_limit_user_actions_per_min": sa.Column("rate_limit_user_actions_per_min", sa.Integer, server_default="5", nullable=True),
            "rate_limit_auto_bans_per_hour": sa.Column("rate_limit_auto_bans_per_hour", sa.Integer, server_default="10", nullable=True),
        }
        for col_name, col_obj in new_sc_cols.items():
            if col_name not in sc_cols:
                op.add_column("server_config", col_obj)

    # 5. Create moderation_exemptions table
    if "moderation_exemptions" not in tables:
        op.create_table(
            "moderation_exemptions",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("target_type", sa.String(32), nullable=False),
            sa.Column("target_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("target_name", sa.String(255), nullable=True),
            sa.Column("scope", sa.String(32), server_default="global", nullable=True),
            sa.Column("scope_id", sa.BigInteger, nullable=True),
            sa.Column("scope_name", sa.String(255), nullable=True),
            sa.Column("channel_type", sa.String(32), nullable=True),
            sa.Column("bypass_all", sa.Boolean, server_default=sa.text("0"), nullable=True),
            sa.Column("bypass_text", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_links", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_images", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_videos", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_files", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_stickers", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_mentions", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_spam", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_keywords", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_invites", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("bypass_warnings", sa.Boolean, server_default=sa.text("0"), nullable=True),
            sa.Column("bypass_timeout", sa.Boolean, server_default=sa.text("0"), nullable=True),
            sa.Column("bypass_kick", sa.Boolean, server_default=sa.text("0"), nullable=True),
            sa.Column("bypass_ban", sa.Boolean, server_default=sa.text("0"), nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=True),
        )

    # 6. Create automod_rules table
    if "automod_rules" not in tables:
        op.create_table(
            "automod_rules",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("rule_type", sa.String(64), nullable=False, index=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("enabled", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("scope", sa.String(32), server_default="global", nullable=True),
            sa.Column("channels", sa.Text, nullable=True),
            sa.Column("categories", sa.Text, nullable=True),
            sa.Column("threshold", sa.Integer, server_default="5", nullable=True),
            sa.Column("time_window", sa.Integer, server_default="5", nullable=True),
            sa.Column("action", sa.String(64), server_default="delete_warn", nullable=True),
            sa.Column("timeout_duration", sa.Integer, server_default="600", nullable=True),
            sa.Column("cooldown", sa.Integer, server_default="10", nullable=True),
            sa.Column("exemptions", sa.Text, nullable=True),
            sa.Column("custom_keywords", sa.Text, nullable=True),
            sa.Column("log_event", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("severity", sa.String(32), server_default="medium", nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=True),
        )

    # 7. Create warning_records table
    if "warning_records" not in tables:
        op.create_table(
            "warning_records",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("warning_id", sa.String(64), unique=True, nullable=False, index=True),
            sa.Column("case_id", sa.String(64), nullable=True, index=True),
            sa.Column("case_number", sa.Integer, nullable=True),
            sa.Column("user_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("username", sa.String(255), nullable=True),
            sa.Column("channel_id", sa.BigInteger, nullable=True),
            sa.Column("channel_name", sa.String(255), nullable=True),
            sa.Column("rule", sa.String(128), nullable=False),
            sa.Column("reason", sa.Text, nullable=False),
            sa.Column("moderator", sa.String(255), server_default="PB HERO AutoMod", nullable=True),
            sa.Column("severity", sa.String(32), server_default="medium", nullable=True),
            sa.Column("points", sa.Integer, server_default="1", nullable=True),
            sa.Column("status", sa.String(32), server_default="active", nullable=True),
            sa.Column("action_taken", sa.String(64), server_default="warn", nullable=True),
            sa.Column("dm_status", sa.String(32), server_default="disabled", nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=True),
            sa.Column("expires_at", sa.DateTime, nullable=True),
            sa.Column("revoked_at", sa.DateTime, nullable=True),
            sa.Column("revoked_by", sa.String(255), nullable=True),
            sa.Column("revoke_reason", sa.Text, nullable=True),
        )

    # 8. Create warning_escalation_rules table
    if "warning_escalation_rules" not in tables:
        op.create_table(
            "warning_escalation_rules",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("threshold", sa.Integer, nullable=False),
            sa.Column("mode", sa.String(32), server_default="count", nullable=True),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("duration", sa.Integer, nullable=True),
            sa.Column("send_dm", sa.Boolean, server_default=sa.text("1"), nullable=True),
            sa.Column("delete_message_history_days", sa.Integer, server_default="0", nullable=True),
            sa.Column("reason_template", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=True),
        )


def downgrade() -> None:
    pass
