"""Add advanced greetings rules delivery DMs and invite settings

Revision ID: 006_advanced_greetings_and_invites
Revises: 005_server_greetings
Create Date: 2026-10-04 19:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_advanced_greetings_and_invites"
down_revision: Union[str, None] = "005_server_greetings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Create server_invite_settings if not exists
    if "server_invite_settings" not in tables:
        op.create_table(
            "server_invite_settings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("guild_id", sa.BigInteger(), nullable=False, unique=True, index=True),
            sa.Column("invite_channel_id", sa.BigInteger(), nullable=True),
            sa.Column("invite_code", sa.String(64), nullable=True),
            sa.Column("invite_url", sa.String(256), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("max_age", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("max_uses", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("temporary", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("last_verified_at", sa.DateTime(), nullable=True),
            sa.Column("verification_status", sa.String(64), server_default="not_generated", nullable=False),
            sa.Column("verification_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

    # 2. Add columns to server_greeting_settings if not exist
    if "server_greeting_settings" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("server_greeting_settings")}

        columns_to_add = [
            ("rules_delivery_enabled", sa.Column("rules_delivery_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False)),
            ("rules_source", sa.Column("rules_source", sa.String(32), server_default="rules_channel", nullable=False)),
            ("rules_channel_id", sa.Column("rules_channel_id", sa.BigInteger(), nullable=True)),
            ("rules_title", sa.Column("rules_title", sa.String(256), nullable=True)),
            ("rules_description", sa.Column("rules_description", sa.Text(), nullable=True)),
            ("rules_footer", sa.Column("rules_footer", sa.String(256), nullable=True)),
            ("rules_button_text", sa.Column("rules_button_text", sa.String(128), nullable=True)),
            ("auto_role_enabled", sa.Column("auto_role_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False)),
            ("auto_role_id", sa.Column("auto_role_id", sa.BigInteger(), nullable=True)),
            ("welcome_dm_enabled", sa.Column("welcome_dm_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False)),
            ("welcome_dm_title", sa.Column("welcome_dm_title", sa.String(256), nullable=True)),
            ("welcome_dm_description", sa.Column("welcome_dm_description", sa.Text(), nullable=True)),
            ("welcome_dm_footer", sa.Column("welcome_dm_footer", sa.String(256), nullable=True)),
            ("welcome_dm_use_embed", sa.Column("welcome_dm_use_embed", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
            ("welcome_dm_show_avatar", sa.Column("welcome_dm_show_avatar", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
            ("welcome_dm_show_server_icon", sa.Column("welcome_dm_show_server_icon", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
            ("welcome_dm_show_timestamp", sa.Column("welcome_dm_show_timestamp", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
            ("goodbye_dm_enabled", sa.Column("goodbye_dm_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False)),
            ("goodbye_dm_title", sa.Column("goodbye_dm_title", sa.String(256), nullable=True)),
            ("goodbye_dm_description", sa.Column("goodbye_dm_description", sa.Text(), nullable=True)),
            ("goodbye_dm_footer", sa.Column("goodbye_dm_footer", sa.String(256), nullable=True)),
            ("goodbye_dm_use_embed", sa.Column("goodbye_dm_use_embed", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
            ("goodbye_dm_show_avatar", sa.Column("goodbye_dm_show_avatar", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
            ("goodbye_dm_show_server_icon", sa.Column("goodbye_dm_show_server_icon", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
            ("goodbye_dm_show_timestamp", sa.Column("goodbye_dm_show_timestamp", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
        ]

        for col_name, col_obj in columns_to_add:
            if col_name not in existing_cols:
                op.add_column("server_greeting_settings", col_obj)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "server_invite_settings" in tables:
        op.drop_table("server_invite_settings")
