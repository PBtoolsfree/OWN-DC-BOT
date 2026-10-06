"""Add premium onboarding 2.0 fields for welcome and goodbye automation

Revision ID: 010_premium_onboarding_2
Revises: 009_invite_activity_log
Create Date: 2026-10-06 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010_premium_onboarding_2"
down_revision: Union[str, None] = "009_invite_activity_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "server_greeting_settings" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("server_greeting_settings")}

        columns_to_add = [
            ("welcome_banner_url", sa.Column("welcome_banner_url", sa.String(1024), nullable=True)),
            ("welcome_banner_mode", sa.Column("welcome_banner_mode", sa.String(32), server_default="none", nullable=False)),
            ("welcome_accent_color", sa.Column("welcome_accent_color", sa.String(16), server_default="#5865F2", nullable=False)),
            ("welcome_buttons_json", sa.Column("welcome_buttons_json", sa.Text(), nullable=True)),
            ("welcome_theme", sa.Column("welcome_theme", sa.String(32), server_default="default", nullable=False)),
            ("welcome_show_inviter", sa.Column("welcome_show_inviter", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
            ("welcome_show_invite_code", sa.Column("welcome_show_invite_code", sa.Boolean(), server_default=sa.text("1"), nullable=False)),
            ("welcome_author_text", sa.Column("welcome_author_text", sa.String(256), nullable=True)),
            ("welcome_author_icon_url", sa.Column("welcome_author_icon_url", sa.String(1024), nullable=True)),

            ("goodbye_banner_url", sa.Column("goodbye_banner_url", sa.String(1024), nullable=True)),
            ("goodbye_banner_mode", sa.Column("goodbye_banner_mode", sa.String(32), server_default="none", nullable=False)),
            ("goodbye_accent_color", sa.Column("goodbye_accent_color", sa.String(16), server_default="#ED4245", nullable=False)),
            ("goodbye_buttons_json", sa.Column("goodbye_buttons_json", sa.Text(), nullable=True)),
            ("goodbye_theme", sa.Column("goodbye_theme", sa.String(32), server_default="default", nullable=False)),
            ("goodbye_author_text", sa.Column("goodbye_author_text", sa.String(256), nullable=True)),
            ("goodbye_author_icon_url", sa.Column("goodbye_author_icon_url", sa.String(1024), nullable=True)),

            ("welcome_dm_banner_url", sa.Column("welcome_dm_banner_url", sa.String(1024), nullable=True)),
            ("welcome_dm_banner_mode", sa.Column("welcome_dm_banner_mode", sa.String(32), server_default="none", nullable=False)),
            ("welcome_dm_accent_color", sa.Column("welcome_dm_accent_color", sa.String(16), server_default="#57F287", nullable=False)),
            ("welcome_dm_buttons_json", sa.Column("welcome_dm_buttons_json", sa.Text(), nullable=True)),
            ("welcome_dm_author_text", sa.Column("welcome_dm_author_text", sa.String(256), nullable=True)),
            ("welcome_dm_author_icon_url", sa.Column("welcome_dm_author_icon_url", sa.String(1024), nullable=True)),

            ("goodbye_dm_banner_url", sa.Column("goodbye_dm_banner_url", sa.String(1024), nullable=True)),
            ("goodbye_dm_banner_mode", sa.Column("goodbye_dm_banner_mode", sa.String(32), server_default="none", nullable=False)),
            ("goodbye_dm_accent_color", sa.Column("goodbye_dm_accent_color", sa.String(16), server_default="#FEE75C", nullable=False)),
            ("goodbye_dm_buttons_json", sa.Column("goodbye_dm_buttons_json", sa.Text(), nullable=True)),
            ("goodbye_dm_author_text", sa.Column("goodbye_dm_author_text", sa.String(256), nullable=True)),
            ("goodbye_dm_author_icon_url", sa.Column("goodbye_dm_author_icon_url", sa.String(1024), nullable=True)),
        ]

        for col_name, col_obj in columns_to_add:
            if col_name not in existing_cols:
                op.add_column("server_greeting_settings", col_obj)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "server_greeting_settings" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("server_greeting_settings")}
        columns_to_drop = [
            "welcome_banner_url", "welcome_banner_mode", "welcome_accent_color",
            "welcome_buttons_json", "welcome_theme", "welcome_show_inviter",
            "welcome_show_invite_code", "welcome_author_text", "welcome_author_icon_url",
            "goodbye_banner_url", "goodbye_banner_mode", "goodbye_accent_color",
            "goodbye_buttons_json", "goodbye_theme", "goodbye_author_text", "goodbye_author_icon_url",
            "welcome_dm_banner_url", "welcome_dm_banner_mode", "welcome_dm_accent_color",
            "welcome_dm_buttons_json", "welcome_dm_author_text", "welcome_dm_author_icon_url",
            "goodbye_dm_banner_url", "goodbye_dm_banner_mode", "goodbye_dm_accent_color",
            "goodbye_dm_buttons_json", "goodbye_dm_author_text", "goodbye_dm_author_icon_url",
        ]
        for col_name in columns_to_drop:
            if col_name in existing_cols:
                op.drop_column("server_greeting_settings", col_name)
