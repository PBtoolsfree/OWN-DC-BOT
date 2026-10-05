"""Add discord_invites and invite_joins tables for invite tracking

Revision ID: 008_discord_invite_tracking
Revises: 007_custom_moderation_styles
Create Date: 2026-10-05 14:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_discord_invite_tracking"
down_revision: Union[str, None] = "007_custom_moderation_styles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Create discord_invites
    if "discord_invites" not in tables:
        op.create_table(
            "discord_invites",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("guild_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("invite_code", sa.String(64), nullable=False, unique=True, index=True),
            sa.Column("inviter_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("inviter_name", sa.String(255), nullable=True),
            sa.Column("channel_id", sa.BigInteger(), nullable=True),
            sa.Column("channel_name", sa.String(255), nullable=True),
            sa.Column("uses", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("max_uses", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("max_age", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("temporary", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("is_vanity", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("is_permanent_config", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        )
        op.create_index(
            "ix_discord_invites_guild_status",
            "discord_invites",
            ["guild_id", "status"],
            unique=False,
        )

    # 2. Create invite_joins
    if "invite_joins" not in tables:
        op.create_table(
            "invite_joins",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("guild_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("member_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("member_name", sa.String(255), nullable=True),
            sa.Column("invite_code", sa.String(64), nullable=True, index=True),
            sa.Column("inviter_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("inviter_name", sa.String(255), nullable=True),
            sa.Column("source_type", sa.String(32), server_default="NORMAL_INVITE", nullable=False),
            sa.Column("channel_id", sa.BigInteger(), nullable=True),
            sa.Column("channel_name", sa.String(255), nullable=True),
            sa.Column("joined_at", sa.DateTime(), server_default=sa.func.now(), nullable=False, index=True),
            sa.Column("is_still_member", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("left_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_invite_joins_lookup",
            "invite_joins",
            ["guild_id", "member_id", "joined_at"],
            unique=False,
        )
        op.create_index(
            "ix_invite_joins_guild_inviter",
            "invite_joins",
            ["guild_id", "inviter_id"],
            unique=False,
        )
        op.create_index(
            "ix_invite_joins_guild_code",
            "invite_joins",
            ["guild_id", "invite_code"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "invite_joins" in tables:
        op.drop_table("invite_joins")

    if "discord_invites" in tables:
        op.drop_table("discord_invites")
