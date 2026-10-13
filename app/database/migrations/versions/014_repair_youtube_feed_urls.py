"""Repair YouTube feed URLs to canonical /xml/feeds/videos.xml and add health telemetry columns.

Revision ID: 014_repair_youtube_feed_urls
Revises: 013_canonical_claim_url
Create Date: 2026-10-13 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014_repair_youtube_feed_urls"
down_revision: Union[str, None] = "013_canonical_claim_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "youtube_channels" in tables:
        columns = [c["name"] for c in inspector.get_columns("youtube_channels")]
        if "last_successful_parse_at" not in columns:
            op.add_column("youtube_channels", sa.Column("last_successful_parse_at", sa.DateTime(), nullable=True))
        if "last_http_status" not in columns:
            op.add_column("youtube_channels", sa.Column("last_http_status", sa.Integer(), nullable=True))
        if "consecutive_failures" not in columns:
            op.add_column("youtube_channels", sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False))
        if "feed_health" not in columns:
            op.add_column("youtube_channels", sa.Column("feed_health", sa.String(32), server_default="UNKNOWN", nullable=False))
        if "live_health" not in columns:
            op.add_column("youtube_channels", sa.Column("live_health", sa.String(32), server_default="UNKNOWN", nullable=False))
        if "next_retry_at" not in columns:
            op.add_column("youtube_channels", sa.Column("next_retry_at", sa.DateTime(), nullable=True))

        # Idempotent repair of existing stored feed URLs:
        # Changes only YouTube feed URLs from /feeds/videos.xml to /xml/feeds/videos.xml
        # Preserves all other settings, channel IDs, destinations, and enabled state.
        op.execute(
            "UPDATE youtube_channels "
            "SET feed_url = replace(feed_url, '/feeds/videos.xml', '/xml/feeds/videos.xml') "
            "WHERE feed_url LIKE '%/feeds/videos.xml%'"
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "youtube_channels" in tables:
        op.execute(
            "UPDATE youtube_channels "
            "SET feed_url = replace(feed_url, '/xml/feeds/videos.xml', '/feeds/videos.xml') "
            "WHERE feed_url LIKE '%/xml/feeds/videos.xml%'"
        )
        columns = [c["name"] for c in inspector.get_columns("youtube_channels")]
        if "next_retry_at" in columns:
            op.drop_column("youtube_channels", "next_retry_at")
        if "live_health" in columns:
            op.drop_column("youtube_channels", "live_health")
        if "feed_health" in columns:
            op.drop_column("youtube_channels", "feed_health")
        if "consecutive_failures" in columns:
            op.drop_column("youtube_channels", "consecutive_failures")
        if "last_http_status" in columns:
            op.drop_column("youtube_channels", "last_http_status")
        if "last_successful_parse_at" in columns:
            op.drop_column("youtube_channels", "last_successful_parse_at")
