"""
Apple App Store iOS free games and temporary 100% off deals adapter.
"""

from datetime import datetime
import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.freegames.normalizer import normalize_claim_url, parse_price, parse_utc_timestamp
from app.freegames.schemas import FreeGameOffer, OfferType
from app.freegames.sources.base import FreeGameSource

logger = logging.getLogger("pbhero.freegames.sources.app_store")

GAMERPOWER_IOS_URL = "https://www.gamerpower.com/api/giveaways?platform=ios"


class AppStoreSource(FreeGameSource):
    """Apple App Store free games and deals adapter."""

    name = "app_store"
    category = "mobile"
    trusted_domains = {"apps.apple.com"}

    async def fetch_offers(self) -> List[FreeGameOffer]:
        start_time = time.time()
        offers: List[FreeGameOffer] = []

        try:
            data = await self._fetch_json(GAMERPOWER_IOS_URL)
            if isinstance(data, list):
                for item in data:
                    offer = await self._parse_ios_item(item)
                    if offer:
                        offers.append(offer)

            latency_ms = (time.time() - start_time) * 1000.0
            self.record_success(len(offers), latency_ms)
            logger.info("[app_store] Fetched %d App Store free offers (%.1f ms)", len(offers), latency_ms)
            return offers

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            self.record_failure(str(e), latency_ms)
            logger.warning("[app_store] Error fetching App Store offers: %s", e)
            return []

    async def _parse_ios_item(self, item: Dict[str, Any]) -> Optional[FreeGameOffer]:
        title = item.get("title", "")
        if not title:
            return None

        clean_title = re.sub(r"\s*\(iOS\)\s*(Giveaway)?", "", title, flags=re.IGNORECASE)
        clean_title = re.sub(r"\s*\(Mobile\)\s*(Giveaway)?", "", clean_title, flags=re.IGNORECASE)
        clean_title = re.sub(r"\s*Giveaway\s*$", "", clean_title, flags=re.IGNORECASE).strip()

        open_url = item.get("open_giveaway_url")
        if not open_url:
            return None

        canonical_url = await self._resolve_canonical_redirect(open_url)
        # Must resolve to apps.apple.com
        if not canonical_url or not self.is_trusted_url(canonical_url):
            return None

        original_price, _, currency, _ = parse_price(item.get("worth"))
        ends_at = parse_utc_timestamp(item.get("end_date"))
        external_id = str(item.get("id") or open_url)

        raw_type = (item.get("type") or "").lower()
        offer_type = OfferType.FREE_DLC.value if "dlc" in raw_type else OfferType.FREE_TO_KEEP.value

        return FreeGameOffer(
            source=self.name,
            external_id=external_id,
            title=clean_title,
            description=item.get("description"),
            store_name="Apple App Store",
            platform="iOS",
            offer_type=offer_type,
            original_price=original_price,
            current_price=0.0,
            currency=currency,
            discount_percent=100,
            claim_url=canonical_url,
            source_url=canonical_url,
            thumbnail_url=item.get("image") or item.get("thumbnail"),
            starts_at=None,
            ends_at=ends_at,
            is_free=True,
            metadata={"platform": "iOS", "item_id": item.get("id")},
        )
