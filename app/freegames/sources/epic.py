"""
Epic Games Store free game promotions adapter.
Fetches from the official Epic Games Promotions API.
"""

from datetime import datetime
import logging
import time
from typing import Any, Dict, List, Optional

from app.freegames.normalizer import (
    normalize_claim_url,
    normalize_epic_claim_url,
    parse_utc_timestamp,
)
from app.freegames.schemas import FreeGameOffer, OfferType
from app.freegames.sources.base import FreeGameSource

logger = logging.getLogger("pbhero.freegames.sources.epic")

EPIC_PROMOTIONS_URL = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"


class EpicGamesSource(FreeGameSource):
    """Official Epic Games Store free game promotion crawler."""

    name = "epic"
    category = "pc"
    trusted_domains = {"store.epicgames.com", "epicgames.com"}

    async def fetch_offers(self) -> List[FreeGameOffer]:
        start_time = time.time()
        params = {"locale": "en-US", "country": "US", "allowCountries": "US"}

        try:
            data = await self._fetch_json(EPIC_PROMOTIONS_URL, params=params)
            latency_ms = (time.time() - start_time) * 1000.0

            elements = (
                data.get("data", {})
                .get("Catalog", {})
                .get("searchStore", {})
                .get("elements", [])
            )

            offers: List[FreeGameOffer] = []
            now = datetime.utcnow()

            for el in elements:
                offer = self._parse_element(el, now)
                if offer:
                    offers.append(offer)

            self.record_success(len(offers), latency_ms)
            logger.info("[epic] Fetched %d active free offers (%.1f ms)", len(offers), latency_ms)
            return offers

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            self.record_failure(str(e), latency_ms)
            logger.warning("[epic] Failed to fetch promotions: %s", e)
            return []

    def _extract_canonical_claim_url(self, el: Dict[str, Any]) -> str:
        """
        Extract canonical official Epic product claim URL directly from element payload.
        Section 3: Source-First URL Extraction:
        - Prefer canonical URL directly provided by source data (product_url, url, canonical_url, etc.)
        - Extract full canonical product path preserving identifier (offerMappings / catalogNs.mappings productHome pageSlug)
        - Never truncate required product identifiers (e.g. buried-stars-d7c88c)
        """
        # 1. Direct URL fields
        for field in (
            "canonicalUrl", "canonical_url",
            "productUrl", "product_url",
            "url", "offerUrl", "offer_url",
            "catalogProductUrl", "catalog_product_url",
        ):
            val = el.get(field)
            if val and isinstance(val, str) and val.strip():
                clean_val = val.strip()
                if clean_val.startswith("http") or "/p/" in clean_val:
                    return normalize_epic_claim_url(clean_val)

        slug = None

        # 2. offerMappings: productHome is the canonical store product page
        offer_mappings = el.get("offerMappings") or []
        for m in offer_mappings:
            if isinstance(m, dict) and m.get("pageType") == "productHome" and m.get("pageSlug"):
                slug = m["pageSlug"]
                break

        # 3. catalogNs.mappings: productHome mapping
        if not slug:
            ns_mappings = el.get("catalogNs", {}).get("mappings", [])
            for m in ns_mappings:
                if isinstance(m, dict) and m.get("pageType") == "productHome" and m.get("pageSlug"):
                    slug = m["pageSlug"]
                    break

        # 4. Any offerMappings or catalogNs mapping with pageSlug
        if not slug:
            for m in offer_mappings:
                if isinstance(m, dict) and m.get("pageSlug"):
                    slug = m["pageSlug"]
                    break

        if not slug:
            ns_mappings = el.get("catalogNs", {}).get("mappings", [])
            for m in ns_mappings:
                if isinstance(m, dict) and m.get("pageSlug"):
                    slug = m["pageSlug"]
                    break

        # 5. customAttributes
        if not slug:
            for ca in (el.get("customAttributes") or []):
                if isinstance(ca, dict) and ca.get("key") in ("com.epicgames.app.productSlug", "productSlug") and ca.get("value"):
                    slug = ca["value"]
                    break

        # 6. productSlug (clean subpath like /home)
        if not slug and el.get("productSlug"):
            slug = str(el["productSlug"]).strip().split("/")[0]

        # 7. Fallback to urlSlug or id
        if not slug:
            slug = el.get("urlSlug") or el.get("id")

        if not slug:
            return ""

        return normalize_epic_claim_url(f"https://store.epicgames.com/p/{slug}")

    def _parse_element(self, el: Dict[str, Any], now: datetime) -> Optional[FreeGameOffer]:
        title = el.get("title")
        if not title:
            return None

        # Price info
        price_info = el.get("price", {}).get("totalPrice", {})
        orig_price_cents = price_info.get("originalPrice", 0)
        disc_price_cents = price_info.get("discountPrice", 0)
        original_price = (orig_price_cents / 100.0) if orig_price_cents else None

        # Promotions info
        promos = el.get("promotions") or {}
        promo_offers = promos.get("promotionalOffers", [])

        is_free_promo = False
        starts_at = None
        ends_at = None

        for group in promo_offers:
            for po in group.get("promotionalOffers", []):
                ds = po.get("discountSetting", {})
                # Check for 0% price (100% discount) or discountPercentage == 0
                if ds.get("discountType") == "PERCENTAGE" and ds.get("discountPercentage") == 0:
                    s_at = parse_utc_timestamp(po.get("startDate"))
                    e_at = parse_utc_timestamp(po.get("endDate"))
                    # Must be active now
                    if (s_at is None or s_at <= now) and (e_at is None or e_at > now):
                        is_free_promo = True
                        starts_at = s_at
                        ends_at = e_at
                        break

        # Check if discount price is 0 and it has an original price
        if not is_free_promo and disc_price_cents == 0 and orig_price_cents > 0:
            is_free_promo = True

        if not is_free_promo:
            return None

        # Extract canonical URL using source-first priority
        claim_url = self._extract_canonical_claim_url(el)
        if not claim_url:
            return None

        # Thumbnail
        thumb = None
        key_images = el.get("keyImages", [])
        for ki in key_images:
            type_name = ki.get("type", "")
            if type_name in ("DieselStoreFrontWide", "OfferImageWide", "Thumbnail"):
                thumb = ki.get("url")
                break
        if not thumb and key_images:
            thumb = key_images[0].get("url")

        external_id = str(el.get("id") or claim_url.split("/")[-1])
        description = el.get("description")

        return FreeGameOffer(
            source=self.name,
            external_id=external_id,
            title=title,
            description=description,
            store_name="Epic Games Store",
            platform="PC",
            offer_type=OfferType.FREE_TO_KEEP.value,
            original_price=original_price,
            current_price=0.0,
            currency="USD",
            discount_percent=100,
            claim_url=claim_url,
            canonical_claim_url=claim_url,
            source_url=claim_url,
            claim_url_status="VALID",
            validated_at=now,
            thumbnail_url=thumb,
            starts_at=starts_at,
            ends_at=ends_at,
            is_free=True,
            metadata={"namespace": el.get("namespace"), "seller": el.get("seller")},
        )
