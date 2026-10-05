"""Add invite_activity_settings table and activity_message_id to invite_joins

Revision ID: 009_invite_activity_log
Revises: 008_discord_invite_tracking
Create Date: 2026-10-05 15:15:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009_invite_activity_log"
down_revision: Union[str, None] = "008_discord_invite_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Create invite_activity_settings
    if "invite_activity_settings" not in tables:
        op.create_table(
            "invite_activity_settings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("guild_id", sa.BigInteger(), nullable=False, unique=True, index=True),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("channel_id", sa.BigInteger(), nullable=True),
            sa.Column("title_template", sa.String(256), server_default="🎉 NEW MEMBER INVITED", nullable=False),
            sa.Column("description_template", sa.Text(), server_default="{inviter_mention} invited {member_mention}", nullable=False),
            sa.Column("color_hex", sa.String(16), server_default="#5865F2", nullable=False),
            sa.Column("log_unknown", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("log_vanity", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("log_created", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("log_revoked", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

    # 2. Add activity_message_id column to invite_joins if not present
    if "invite_joins" in tables:
        columns = [c["name"] for c in inspector.get_columns("invite_joins")]
        if "activity_message_id" not in columns:
            op.add_column("invite_joins", sa.Column("activity_message_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "invite_activity_settings" in tables:
        op.drop_table("invite_activity_settings")

    if "invite_joins" in tables:
        columns = [c["name"] for c in inspector.get_columns("invite_joins")]
        if "activity_message_id" in columns:
            op.drop_column("invite_joins", "activity_message_id")
