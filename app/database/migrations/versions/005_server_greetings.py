"""Add server greeting settings table

Revision ID: 005_server_greetings
Revises: 004_moderation_control_center
Create Date: 2026-10-04 18:25:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_server_greetings"
down_revision: Union[str, None] = "004_moderation_control_center"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "server_greeting_settings" not in tables:
        op.create_table(
            "server_greeting_settings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("guild_id", sa.BigInteger(), nullable=False, unique=True, index=True),
            sa.Column("welcome_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("welcome_channel_id", sa.BigInteger(), nullable=True),
            sa.Column("welcome_title", sa.String(256), nullable=True),
            sa.Column("welcome_description", sa.Text(), nullable=True),
            sa.Column("welcome_footer", sa.String(256), nullable=True),
            sa.Column("welcome_mention_user", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("welcome_show_avatar", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("welcome_show_server_icon", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("welcome_show_member_count", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("welcome_show_timestamp", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("welcome_use_embed", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("goodbye_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("goodbye_channel_id", sa.BigInteger(), nullable=True),
            sa.Column("goodbye_title", sa.String(256), nullable=True),
            sa.Column("goodbye_description", sa.Text(), nullable=True),
            sa.Column("goodbye_footer", sa.String(256), nullable=True),
            sa.Column("goodbye_mention_user", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("goodbye_show_avatar", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("goodbye_show_server_icon", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("goodbye_show_member_count", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("goodbye_show_timestamp", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("goodbye_use_embed", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("allow_mass_mentions", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "server_greeting_settings" in tables:
        op.drop_table("server_greeting_settings")
