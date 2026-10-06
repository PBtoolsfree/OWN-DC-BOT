"""Add canonical_claim_url, claim_url_status, and validated_at to free_game_offers.

Revision ID: 013_canonical_claim_url
Revises: 012_free_games_tracker
Create Date: 2026-10-06 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013_canonical_claim_url"
down_revision: Union[str, None] = "012_free_games_tracker"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "free_game_offers" in tables:
        columns = [c["name"] for c in inspector.get_columns("free_game_offers")]
        if "canonical_claim_url" not in columns:
            op.add_column("free_game_offers", sa.Column("canonical_claim_url", sa.String(1024), nullable=True))
        if "claim_url_status" not in columns:
            op.add_column("free_game_offers", sa.Column("claim_url_status", sa.String(32), server_default="VALID", nullable=False))
        if "validated_at" not in columns:
            op.add_column("free_game_offers", sa.Column("validated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "free_game_offers" in tables:
        columns = [c["name"] for c in inspector.get_columns("free_game_offers")]
        if "validated_at" in columns:
            op.drop_column("free_game_offers", "validated_at")
        if "claim_url_status" in columns:
            op.drop_column("free_game_offers", "claim_url_status")
        if "canonical_claim_url" in columns:
            op.drop_column("free_game_offers", "canonical_claim_url")
