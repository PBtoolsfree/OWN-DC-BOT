"""Add moderation enhancements: category, toggles, mod_log_events

Revision ID: 003_moderation_enhancements
Revises: 002_notification_templates
Create Date: 2026-10-03 15:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_moderation_enhancements"
down_revision: Union[str, None] = "002_notification_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. Update channel_policies table
    if "channel_policies" in inspector.get_table_names():
        cp_cols = [c["name"] for c in inspector.get_columns("channel_policies")]
        if "send_dm_warning" not in cp_cols:
            op.add_column("channel_policies", sa.Column("send_dm_warning", sa.Boolean, default=False, nullable=True))

    # 2. Update policy_profiles table
    if "policy_profiles" in inspector.get_table_names():
        pp_cols = [c["name"] for c in inspector.get_columns("policy_profiles")]
        if "category" not in pp_cols:
            op.add_column("policy_profiles", sa.Column("category", sa.String(64), default="General", nullable=True))
        if "delete_violations" not in pp_cols:
            op.add_column("policy_profiles", sa.Column("delete_violations", sa.Boolean, default=True, nullable=True))
        if "warn_on_violation" not in pp_cols:
            op.add_column("policy_profiles", sa.Column("warn_on_violation", sa.Boolean, default=True, nullable=True))
        if "log_violations" not in pp_cols:
            op.add_column("policy_profiles", sa.Column("log_violations", sa.Boolean, default=True, nullable=True))
        if "send_dm_warning" not in pp_cols:
            op.add_column("policy_profiles", sa.Column("send_dm_warning", sa.Boolean, default=False, nullable=True))
        if "warning_message" not in pp_cols:
            op.add_column("policy_profiles", sa.Column("warning_message", sa.Text, nullable=True))
        if "updated_at" not in pp_cols:
            op.add_column("policy_profiles", sa.Column("updated_at", sa.DateTime, nullable=True))

    # 3. Update server_config table
    if "server_config" in inspector.get_table_names():
        sc_cols = [c["name"] for c in inspector.get_columns("server_config")]
        if "mod_log_events" not in sc_cols:
            op.add_column("server_config", sa.Column("mod_log_events", sa.Text, nullable=True))


def downgrade() -> None:
    pass
