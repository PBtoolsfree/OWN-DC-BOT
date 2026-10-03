"""Add youtube_notification_templates table

Revision ID: 002_notification_templates
Revises: 001_initial
Create Date: 2026-10-03 14:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_notification_templates"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if table already exists (SQLite safe create)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "youtube_notification_templates" not in inspector.get_table_names():
        op.create_table(
            "youtube_notification_templates",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("title_template", sa.String(256), nullable=False),
            sa.Column("description_template", sa.Text, nullable=False),
            sa.Column("mention_role", sa.String(128), nullable=True),
            sa.Column("footer_text", sa.String(256), nullable=True),
            sa.Column("show_thumbnail", sa.Boolean, default=True, nullable=False),
            sa.Column("show_timestamp", sa.Boolean, default=True, nullable=False),
            sa.Column("enable_button", sa.Boolean, default=True, nullable=False),
            sa.Column("created_at", sa.DateTime),
            sa.Column("updated_at", sa.DateTime),
        )
        op.create_index(
            "ix_youtube_notification_templates_event_type",
            "youtube_notification_templates",
            ["event_type"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_table("youtube_notification_templates")
