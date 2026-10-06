"""Add welcome_dm_include_rules field to ServerGreetingSettings

Revision ID: 011_welcome_dm_include_rules
Revises: 010_premium_onboarding_2
Create Date: 2026-10-06 14:40:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011_welcome_dm_include_rules"
down_revision: Union[str, None] = "010_premium_onboarding_2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "server_greeting_settings" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("server_greeting_settings")}
        if "welcome_dm_include_rules" not in existing_cols:
            op.add_column(
                "server_greeting_settings",
                sa.Column("welcome_dm_include_rules", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "server_greeting_settings" in tables:
        existing_cols = {c["name"] for c in inspector.get_columns("server_greeting_settings")}
        if "welcome_dm_include_rules" in existing_cols:
            with op.batch_alter_table("server_greeting_settings") as batch_op:
                batch_op.drop_column("welcome_dm_include_rules")
