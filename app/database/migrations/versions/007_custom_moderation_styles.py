"""Add custom moderation styles table

Revision ID: 007_custom_moderation_styles
Revises: 006_advanced_greetings_and_invites
Create Date: 2026-10-05 01:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_custom_moderation_styles"
down_revision: Union[str, None] = "006_advanced_greetings_and_invites"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "custom_moderation_styles" not in tables:
        op.create_table(
            "custom_moderation_styles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(128), unique=True, nullable=False, index=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("warning_decay_days", sa.Integer(), server_default=sa.text("30"), nullable=False),
            sa.Column("allow_warning_expiration", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("warning_mode", sa.String(32), server_default="count", nullable=False),
            sa.Column("ladder", sa.Text(), nullable=False),
            sa.Column("is_builtin", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "custom_moderation_styles" in tables:
        op.drop_table("custom_moderation_styles")
