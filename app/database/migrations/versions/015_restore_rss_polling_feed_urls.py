"""Restore YouTube feed URLs to direct RSS polling endpoint /feeds/videos.xml.

Revision ID: 015_restore_rss_polling_feed_urls
Revises: 014_repair_youtube_feed_urls
Create Date: 2026-10-13 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_restore_rss_polling_feed_urls"
down_revision: Union[str, None] = "014_repair_youtube_feed_urls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "youtube_channels" in tables:
        # Idempotently restore stored feed URLs from /xml/feeds/ to /feeds/
        # Preserves channel IDs, Discord destinations, templates, and enabled state.
        op.execute(
            "UPDATE youtube_channels "
            "SET feed_url = replace(feed_url, '/xml/feeds/videos.xml', '/feeds/videos.xml') "
            "WHERE feed_url LIKE '%/xml/feeds/videos.xml%'"
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "youtube_channels" in tables:
        op.execute(
            "UPDATE youtube_channels "
            "SET feed_url = replace(feed_url, '/feeds/videos.xml', '/xml/feeds/videos.xml') "
            "WHERE feed_url LIKE '%/feeds/videos.xml%'"
        )
