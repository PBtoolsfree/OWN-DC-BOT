"""
Centralized Free Game Service orchestrating sources, database, deduplication, and notifications.
"""

import asyncio
from datetime import datetime
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord.ext import commands

from app.config import get_settings
from app.database.engine import get_session_direct
from app.database.models import FreeGameSettings
from app.database.repositories import (
    FreeGameNotificationRepo,
    FreeGameOfferRepo,
    FreeGameSettingsRepo,
    FreeGameSourceRepo,
)
from app.freegames.dedupe import compute_offer_unique_key
from app.freegames.notifier import prepare_notification_payload
from app.freegames.schemas import FreeGameOffer, SourceHealth
from app.freegames.sources import get_all_sources, get_source
from app.freegames.validator import validate_offer_eligibility

logger = logging.getLogger("pbhero.freegames.service")
settings = get_settings()

_service_instance: Optional["FreeGameService"] = None


def get_freegame_service(bot: Optional[commands.Bot] = None) -> "FreeGameService":
    """Singleton getter for FreeGameService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = FreeGameService(bot=bot)
    elif bot is not None and _service_instance.bot is None:
        _service_instance.bot = bot
    return _service_instance


class FreeGameService:
    """Orchestrator for Free Games & Deals Tracker."""

    def __init__(self, bot: Optional[commands.Bot] = None):
        self.bot = bot
        self._sync_lock = asyncio.Lock()

    # ─── Settings ─────────────────────────────────────────────────────────────

    async def get_settings(self, guild_id: Optional[int] = None) -> FreeGameSettings:
        target_guild_id = guild_id or settings.DISCORD_GUILD_ID
        session = await get_session_direct()
        try:
            cfg = await FreeGameSettingsRepo.get_or_create(session, target_guild_id)
            await session.commit()
            return cfg
        finally:
            await session.close()

    async def update_settings(self, guild_id: Optional[int] = None, **kwargs) -> FreeGameSettings:
        target_guild_id = guild_id or settings.DISCORD_GUILD_ID
        session = await get_session_direct()
        try:
            cfg = await FreeGameSettingsRepo.update(session, target_guild_id, **kwargs)
            await session.commit()
            return cfg
        finally:
            await session.close()

    # ─── Channel Permissions ──────────────────────────────────────────────────

    def check_channel_permissions(
        self, channel: Optional[discord.abc.GuildChannel]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Verify Discord permissions for posting free game alerts."""
        if not channel:
            return False, {
                "status": "missing_channel",
                "can_view": False,
                "can_send": False,
                "can_embed": False,
                "warning": "Destination channel not found.",
            }

        guild = getattr(channel, "guild", None)
        me = getattr(guild, "me", None) if guild else None
        if not me:
            return True, {"status": "ok", "can_view": True, "can_send": True, "can_embed": True}

        perms = channel.permissions_for(me)
        can_view = perms.view_channel
        can_send = perms.send_messages
        can_embed = perms.embed_links

        is_valid = can_view and can_send and can_embed
        warning = None
        if not can_view:
            warning = "Missing 'View Channel' permission."
        elif not can_send:
            warning = "Missing 'Send Messages' permission."
        elif not can_embed:
            warning = "Missing 'Embed Links' permission."

        return is_valid, {
            "status": "ok" if is_valid else "missing_permissions",
            "can_view": can_view,
            "can_send": can_send,
            "can_embed": can_embed,
            "warning": warning,
            "channel_id": channel.id,
            "channel_name": getattr(channel, "name", "channel"),
        }

    # ─── Offer Polling and Synchronization ────────────────────────────────────

    async def sync_offers(self) -> Dict[str, Any]:
        """
        Scan all enabled sources, validate offers, update database, and deliver notifications.
        Concurrency-safe via internal lock.
        """
        async with self._sync_lock:
            start_time = time.time()
            config = await self.get_settings()
            if not config.enabled:
                logger.info("FreeGames Tracker is disabled in configuration. Skipping sync.")
                return {"status": "disabled", "new_offers": 0, "processed": 0}

            enabled_sources = []
            try:
                enabled_sources = json.loads(config.enabled_sources_json or "[]")
            except Exception:
                enabled_sources = ["epic", "steam", "gog", "google_play", "app_store"]

            allowed_offer_types = []
            try:
                allowed_offer_types = json.loads(config.offer_types_json or "[]")
            except Exception:
                allowed_offer_types = ["free_to_keep"]

            logger.info("FreeGames source scan started (sources: %s)", enabled_sources)
            total_discovered = 0
            total_posted = 0
            source_results = {}

            # 1. Fetch offers from each enabled source (with complete error isolation)
            for src_name in enabled_sources:
                source = get_source(src_name)
                if not source:
                    continue

                t0 = time.time()
                try:
                    offers = await source.fetch_offers()
                    latency = (time.time() - t0) * 1000.0
                    source_results[src_name] = {"success": True, "count": len(offers), "latency_ms": latency}

                    # Persist source success metrics
                    session_src = await get_session_direct()
                    try:
                        await FreeGameSourceRepo.record_success(session_src, src_name, len(offers), latency)
                        await session_src.commit()
                    finally:
                        await session_src.close()

                    # Process each offer
                    for offer in offers:
                        total_discovered += 1
                        posted = await self._process_offer(offer, config, allowed_offer_types)
                        if posted:
                            total_posted += 1

                except Exception as e:
                    latency = (time.time() - t0) * 1000.0
                    logger.exception("FreeGames source exception in %s: %s", src_name, e)
                    source_results[src_name] = {"success": False, "error": str(e), "latency_ms": latency}

                    session_err = await get_session_direct()
                    try:
                        await FreeGameSourceRepo.record_failure(session_err, src_name, str(e), latency)
                        await session_err.commit()
                    finally:
                        await session_err.close()

            # 2. Check ending soon notifications
            ending_soon_posted = 0
            if config.ending_soon_enabled:
                ending_soon_posted = await self._check_ending_soon_offers(config)

            # 3. Clean up expired offers
            await self._cleanup_expired_offers()

            duration_s = round(time.time() - start_time, 2)
            logger.info(
                "FreeGames sync finished in %.2fs: %d discovered, %d posted, %d ending-soon",
                duration_s, total_discovered, total_posted, ending_soon_posted
            )
            return {
                "status": "success",
                "duration_seconds": duration_s,
                "discovered": total_discovered,
                "posted": total_posted,
                "ending_soon_posted": ending_soon_posted,
                "sources": source_results,
            }

    async def _process_offer(
        self,
        offer: FreeGameOffer,
        config: FreeGameSettings,
        allowed_offer_types: List[str],
    ) -> bool:
        """Validate, upsert, and optionally post a single offer."""
        # 1. Validation
        is_eligible, reason = validate_offer_eligibility(offer, allowed_offer_types)
        if not is_eligible:
            if "NO_CLAIM_URL" in reason:
                logger.warning("SKIPPED_OFFER_NO_CLAIM_URL: '%s' (%s)", offer.title, offer.source)
            else:
                logger.info("Offer skipped (%s): '%s' from %s", reason, offer.title, offer.source)
            return False

        # 2. Compute unique identity
        offer.unique_key = compute_offer_unique_key(offer.source, offer.external_id, offer.claim_url)

        # 3. Database Upsert
        session = await get_session_direct()
        try:
            offer_dict = offer.to_dict()
            db_offer, is_new = await FreeGameOfferRepo.upsert_offer(session, offer_dict)
            await session.commit()
        except Exception as e:
            logger.error("Failed to upsert offer '%s': %s", offer.title, e)
            await session.rollback()
            return False
        finally:
            await session.close()

        # 4. If new offer (or unposted NEW offer) and destination channel is configured, deliver Discord notification
        needs_post = (is_new or (db_offer.status == "NEW" and not db_offer.posted_message_id))
        if needs_post and config.destination_channel_id and self.bot:
            return await self._deliver_new_offer_notification(db_offer.id, offer, config)
        elif not is_new:
            logger.debug("FreeGames duplicate skipped: '%s' (%s)", offer.title, offer.unique_key)

        return False

    async def _deliver_new_offer_notification(
        self,
        offer_id: int,
        offer: FreeGameOffer,
        config: FreeGameSettings,
    ) -> bool:
        """Deliver Discord embed and claim button for a newly discovered offer."""
        channel = self.bot.get_channel(config.destination_channel_id) if self.bot else None
        if not channel:
            logger.warning("Destination channel %s not found for FreeGames notification.", config.destination_channel_id)
            return False

        is_valid, perm_telemetry = self.check_channel_permissions(channel)
        if not is_valid:
            logger.warning("FreeGames Discord permission missing: %s", perm_telemetry.get("warning"))
            return False

        content, embed, view, mentions = prepare_notification_payload(
            offer=offer,
            role_mention_id=config.role_mention_id,
            is_ending_soon=False,
            is_test=False,
            show_thumbnail=config.post_thumbnail,
            show_description=config.post_description,
            show_price=config.show_price,
            show_expiry=config.show_expiry,
        )

        try:
            msg = await channel.send(content=content, embed=embed, view=view, allowed_mentions=mentions)
            logger.info("FreeGames notification sent: '%s' to #%s (Msg ID: %s)", offer.title, channel.name, msg.id)

            session = await get_session_direct()
            try:
                await FreeGameOfferRepo.mark_posted(session, offer_id, channel.id, msg.id)
                await FreeGameNotificationRepo.record(
                    session=session,
                    offer_id=offer_id,
                    notification_type="NEW_OFFER",
                    channel_id=channel.id,
                    message_id=msg.id,
                    claim_url=offer.claim_url,
                    status="delivered",
                )
                await session.commit()
            finally:
                await session.close()
            return True

        except Exception as e:
            logger.error("FreeGames Discord send failure for '%s': %s", offer.title, e)
            session = await get_session_direct()
            try:
                await FreeGameNotificationRepo.record(
                    session=session,
                    offer_id=offer_id,
                    notification_type="NEW_OFFER",
                    channel_id=channel.id,
                    message_id=None,
                    claim_url=offer.claim_url,
                    status="failed",
                    error_message=str(e),
                )
                await session.commit()
            finally:
                await session.close()
            return False

    async def _check_ending_soon_offers(self, config: FreeGameSettings) -> int:
        """Find active offers ending within the configured window and post reminder."""
        if not config.destination_channel_id or not self.bot:
            return 0

        channel = self.bot.get_channel(config.destination_channel_id)
        if not channel:
            return 0

        session = await get_session_direct()
        candidates = []
        try:
            candidates = await FreeGameOfferRepo.get_ending_soon_candidates(session, config.ending_soon_hours)
            await session.commit()
        finally:
            await session.close()

        posted_count = 0
        for db_offer in candidates:
            offer = FreeGameOffer(
                source=db_offer.source,
                external_id=db_offer.external_id,
                title=db_offer.title,
                store_name=db_offer.store_name,
                platform=db_offer.platform,
                claim_url=db_offer.claim_url,
                description=db_offer.description,
                offer_type=db_offer.offer_type,
                original_price=db_offer.original_price,
                current_price=db_offer.current_price,
                currency=db_offer.currency,
                discount_percent=db_offer.discount_percent,
                thumbnail_url=db_offer.thumbnail_url,
                starts_at=db_offer.starts_at,
                ends_at=db_offer.ends_at,
                is_free=db_offer.is_free,
            )

            content, embed, view, mentions = prepare_notification_payload(
                offer=offer,
                role_mention_id=config.role_mention_id,
                is_ending_soon=True,
                is_test=False,
                show_thumbnail=config.post_thumbnail,
                show_description=config.post_description,
                show_price=config.show_price,
                show_expiry=config.show_expiry,
            )

            try:
                msg = await channel.send(content=content, embed=embed, view=view, allowed_mentions=mentions)
                posted_count += 1
                logger.info("Ending-soon alert delivered for '%s' to #%s", offer.title, channel.name)

                session_mark = await get_session_direct()
                try:
                    await FreeGameOfferRepo.mark_ending_soon_posted(session_mark, db_offer.id)
                    await FreeGameNotificationRepo.record(
                        session=session_mark,
                        offer_id=db_offer.id,
                        notification_type="ENDING_SOON",
                        channel_id=channel.id,
                        message_id=msg.id,
                        claim_url=offer.claim_url,
                        status="delivered",
                    )
                    await session_mark.commit()
                finally:
                    await session_mark.close()

            except Exception as e:
                logger.warning("Failed to send ending-soon alert for '%s': %s", offer.title, e)

        return posted_count

    async def _cleanup_expired_offers(self) -> None:
        """Mark offers that have passed their ends_at as EXPIRED."""
        session = await get_session_direct()
        try:
            expired_offers = await FreeGameOfferRepo.get_expired_active_offers(session)
            for off in expired_offers:
                off.status = "EXPIRED"
            if expired_offers:
                logger.debug("Marked %d past offers as EXPIRED", len(expired_offers))
            await session.commit()
        except Exception as e:
            logger.warning("Error cleaning up expired offers: %s", e)
            await session.rollback()
        finally:
            await session.close()

    # ─── Admin Test Dispatch ──────────────────────────────────────────────────

    async def send_test_notification(self, channel_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Send a single clearly marked test embed and claim button to the channel.
        Section 24: MUST NOT create a real offer database record.
        """
        config = await self.get_settings()
        target_channel_id = channel_id or config.destination_channel_id
        if not target_channel_id:
            return {"success": False, "error": "No destination channel configured."}

        if not self.bot:
            return {"success": False, "error": "Discord bot instance is not available."}

        channel = self.bot.get_channel(target_channel_id)
        if not channel:
            return {"success": False, "error": f"Channel with ID {target_channel_id} not found."}

        is_valid, perm_telemetry = self.check_channel_permissions(channel)
        if not is_valid:
            return {"success": False, "error": perm_telemetry.get("warning") or "Missing channel permissions."}

        # Safe mock offer (does NOT save to DB)
        test_offer = FreeGameOffer(
            source="epic",
            external_id="test_game_123",
            title="System Shock 2 (Test Preview)",
            store_name="Epic Games Store",
            platform="PC",
            claim_url="https://store.epicgames.com/p/system-shock-2-test",
            description="This is a test notification from PB HERO Free Games & Deals Tracker verifying embed, styling, and claim button functionality.",
            offer_type="free_to_keep",
            original_price=29.99,
            current_price=0.0,
            currency="USD",
            discount_percent=100,
            thumbnail_url="https://cdn1.epicgames.com/offer/placeholder/test_image.jpg",
            starts_at=datetime.utcnow(),
            ends_at=datetime.utcnow(),
            is_free=True,
        )

        content, embed, view, mentions = prepare_notification_payload(
            offer=test_offer,
            role_mention_id=config.role_mention_id,
            is_ending_soon=False,
            is_test=True,
            show_thumbnail=True,
            show_description=True,
            show_price=True,
            show_expiry=True,
        )

        try:
            msg = await channel.send(content=content, embed=embed, view=view, allowed_mentions=mentions)
            logger.info("FreeGames test notification delivered to #%s (Msg ID: %s)", channel.name, msg.id)
            return {
                "success": True,
                "message": f"Test notification sent to #{channel.name}",
                "channel_id": channel.id,
                "message_id": msg.id,
                "claim_url": test_offer.claim_url,
            }
        except Exception as e:
            logger.error("Failed to send FreeGames test notification: %s", e)
            return {"success": False, "error": str(e)}

    # ─── Status & Health ──────────────────────────────────────────────────────

    async def get_status_overview(self) -> Dict[str, Any]:
        """Summary status for dashboard and slash commands."""
        config = await self.get_settings()
        session = await get_session_direct()
        try:
            active_offers = await FreeGameOfferRepo.get_active_offers(session, limit=10)
            sources = await FreeGameSourceRepo.get_all(session)
            await session.commit()
        finally:
            await session.close()

        channel_info = None
        if config.destination_channel_id and self.bot:
            ch = self.bot.get_channel(config.destination_channel_id)
            if ch:
                is_valid, _ = self.check_channel_permissions(ch)
                channel_info = {"id": str(ch.id), "name": ch.name, "status": "OK" if is_valid else "DEGRADED"}

        source_stats = []
        for s in sources:
            source_stats.append({
                "source": s.source_name,
                "category": s.category,
                "status": s.status,
                "offer_count": s.offer_count,
                "latency_ms": s.response_latency_ms,
                "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
            })

        return {
            "enabled": config.enabled,
            "destination_channel": channel_info,
            "poll_interval_seconds": config.poll_interval_seconds,
            "active_offers_count": len(active_offers),
            "sources": source_stats,
        }
