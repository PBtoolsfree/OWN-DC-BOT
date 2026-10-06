"""Add Free Games and Deals Tracker tables

Revision ID: 012_free_games_tracker
Revises: 011_welcome_dm_include_rules
Create Date: 2026-10-06 16:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012_free_games_tracker"
down_revision: Union[str, None] = "011_welcome_dm_include_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. free_game_settings
    if "free_game_settings" not in tables:
        op.create_table(
            "free_game_settings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("guild_id", sa.BigInteger(), nullable=False, unique=True),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("destination_channel_id", sa.BigInteger(), nullable=True),
            sa.Column("role_mention_id", sa.BigInteger(), nullable=True),
            sa.Column("poll_interval_seconds", sa.Integer(), server_default=sa.text("900"), nullable=False),
            sa.Column("enabled_sources_json", sa.Text(), server_default='["epic", "steam", "gog", "google_play", "app_store"]', nullable=False),
            sa.Column("offer_types_json", sa.Text(), server_default='["free_to_keep"]', nullable=False),
            sa.Column("ending_soon_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("ending_soon_hours", sa.Integer(), server_default=sa.text("24"), nullable=False),
            sa.Column("post_thumbnail", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("post_description", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("show_price", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("show_expiry", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_free_game_settings_guild_id", "free_game_settings", ["guild_id"], unique=True)

    # 2. free_game_offers
    if "free_game_offers" not in tables:
        op.create_table(
            "free_game_offers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("source", sa.String(64), nullable=False),
            sa.Column("external_id", sa.String(256), nullable=False),
            sa.Column("unique_key", sa.String(512), nullable=False, unique=True),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("store_name", sa.String(128), nullable=False),
            sa.Column("platform", sa.String(64), nullable=False),
            sa.Column("offer_type", sa.String(64), server_default="free_to_keep", nullable=False),
            sa.Column("original_price", sa.Float(), nullable=True),
            sa.Column("current_price", sa.Float(), server_default=sa.text("0.0"), nullable=False),
            sa.Column("currency", sa.String(16), server_default="USD", nullable=False),
            sa.Column("discount_percent", sa.Integer(), server_default=sa.text("100"), nullable=False),
            sa.Column("claim_url", sa.String(1024), nullable=False),
            sa.Column("canonical_claim_url", sa.String(1024), nullable=True),
            sa.Column("claim_url_status", sa.String(32), server_default="VALID", nullable=False),
            sa.Column("validated_at", sa.DateTime(), nullable=True),
            sa.Column("source_url", sa.String(1024), nullable=True),
            sa.Column("thumbnail_url", sa.String(1024), nullable=True),
            sa.Column("starts_at", sa.DateTime(), nullable=True),
            sa.Column("ends_at", sa.DateTime(), nullable=True),
            sa.Column("is_free", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("status", sa.String(32), server_default="NEW", nullable=False),
            sa.Column("first_seen_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
            sa.Column("last_posted_at", sa.DateTime(), nullable=True),
            sa.Column("posted_message_id", sa.BigInteger(), nullable=True),
            sa.Column("posted_channel_id", sa.BigInteger(), nullable=True),
            sa.Column("ending_soon_posted_at", sa.DateTime(), nullable=True),
            sa.Column("raw_metadata_json", sa.Text(), nullable=True),
        )
        op.create_index("ix_free_game_offers_source", "free_game_offers", ["source"])
        op.create_index("ix_free_game_offers_external_id", "free_game_offers", ["external_id"])
        op.create_index("ix_free_game_offers_unique_key", "free_game_offers", ["unique_key"], unique=True)
        op.create_index("ix_free_game_offers_status", "free_game_offers", ["status"])
        op.create_index("ix_free_game_offers_ends_at", "free_game_offers", ["ends_at"])
        op.create_index("ix_free_game_offers_source_ext", "free_game_offers", ["source", "external_id"])
        op.create_index("ix_free_game_offers_status_ends", "free_game_offers", ["status", "ends_at"])

    # 3. free_game_sources
    if "free_game_sources" not in tables:
        op.create_table(
            "free_game_sources",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("source_name", sa.String(64), nullable=False, unique=True),
            sa.Column("category", sa.String(32), server_default="pc", nullable=False),
            sa.Column("status", sa.String(32), server_default="HEALTHY", nullable=False),
            sa.Column("last_checked_at", sa.DateTime(), nullable=True),
            sa.Column("last_success_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.Column("consecutive_failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("offer_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("response_latency_ms", sa.Float(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_free_game_sources_source_name", "free_game_sources", ["source_name"], unique=True)

    # 4. free_game_notifications
    if "free_game_notifications" not in tables:
        op.create_table(
            "free_game_notifications",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("offer_id", sa.Integer(), sa.ForeignKey("free_game_offers.id", ondelete="SET NULL"), nullable=True),
            sa.Column("notification_type", sa.String(32), server_default="NEW_OFFER", nullable=False),
            sa.Column("channel_id", sa.BigInteger(), nullable=False),
            sa.Column("message_id", sa.BigInteger(), nullable=True),
            sa.Column("claim_url", sa.String(1024), nullable=False),
            sa.Column("status", sa.String(32), server_default="delivered", nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "free_game_notifications" in tables:
        op.drop_table("free_game_notifications")
    if "free_game_sources" in tables:
        op.drop_table("free_game_sources")
    if "free_game_offers" in tables:
        op.drop_table("free_game_offers")
    if "free_game_settings" in tables:
        op.drop_table("free_game_settings")
