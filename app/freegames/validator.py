"""
Validation and security verification for Free Games & Deals Tracker.
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import httpx

from app.freegames.normalizer import normalize_claim_url, normalize_epic_claim_url
from app.freegames.schemas import FreeGameOffer, OfferType

logger = logging.getLogger("pbhero.freegames.validator")

# Source-specific canonical trusted domains
TRUSTED_SOURCE_DOMAINS: Dict[str, Set[str]] = {
    "epic": {"store.epicgames.com", "epicgames.com"},
    "steam": {"store.steampowered.com", "steampowered.com"},
    "gog": {"gog.com", "www.gog.com"},
    "google_play": {"play.google.com"},
    "app_store": {"apps.apple.com"},
}

# Global safe protocol schemes
ALLOWED_SCHEMES = {"https"}
DANGEROUS_SCHEMES = {"javascript", "data", "file", "ftp", "vbscript", "about", "blob"}

EPIC_GRAPHQL_URL = "https://store.epicgames.com/graphql"


def validate_claim_url_security(url: Optional[str], source: Optional[str] = None) -> Tuple[bool, str]:
    """
    Strict security check on claim URL:
    - Must be non-empty
    - Must use HTTPS scheme
    - Must not use dangerous schemes
    - Must match trusted source domain if source is provided
    """
    if not url or not isinstance(url, str) or not url.strip():
        return False, "SKIPPED_OFFER_NO_CLAIM_URL"

    clean_url = url.strip()

    # Reject dangerous protocol prefixes before parsing
    lower_url = clean_url.lower()
    for ds in DANGEROUS_SCHEMES:
        if lower_url.startswith(f"{ds}:"):
            return False, f"MALICIOUS_SCHEME_REJECTED: {ds}"

    try:
        parsed = urlparse(clean_url)
    except Exception as e:
        return False, f"INVALID_URL_SYNTAX: {e}"

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"INSECURE_SCHEME_REJECTED: {parsed.scheme}"

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, "EMPTY_HOSTNAME"

    # Domain trust check
    if source:
        clean_src = source.lower().replace("-", "_").replace(" ", "_")
        trusted = TRUSTED_SOURCE_DOMAINS.get(clean_src)
        if trusted:
            # Check exact match or valid subdomain of trusted domain
            matched = False
            for td in trusted:
                if hostname == td or hostname.endswith(f".{td}"):
                    matched = True
                    break
            if not matched:
                return False, f"UNTRUSTED_DOMAIN: {hostname} for source {source}"

    return True, "OK"


async def resolve_canonical_epic_url(
    url_or_slug: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[str]:
    """
    Resolve an Epic Games Store product URL or slug to its true canonical URL.
    - Rejects /not-found, 404, or empty paths.
    - Resolves incomplete slugs (e.g. buried-stars) to canonical pageSlugs with product identifier (e.g. buried-stars-d7c88c).
    - Preserves canonical URLs that are already complete.
    """
    if not url_or_slug or not isinstance(url_or_slug, str):
        return None

    clean = url_or_slug.strip()
    if "/not-found" in clean.lower():
        return None

    m = re.search(r"/(?:p|product)/([^/?#]+)", clean)
    if m:
        slug = m.group(1).strip()
    else:
        slug = clean.strip("/").split("/")[-1].strip()

    if not slug or slug.lower() in ("not-found", "404", "home", "store"):
        return None

    # Base keyword without hex hash if hash is present
    base_slug = re.sub(r"-[a-f0-9]{6,}$", "", slug)
    keywords_to_try = [slug]
    if base_slug != slug:
        keywords_to_try.append(base_slug)
    clean_kw = base_slug.replace("-", " ")
    if clean_kw not in keywords_to_try:
        keywords_to_try.append(clean_kw)

    query = """
    query searchStoreQuery($keywords: String, $locale: String) {
      Catalog {
        searchStore(keywords: $keywords, locale: $locale) {
          elements {
            title
            productSlug
            urlSlug
            offerMappings {
              pageSlug
              pageType
            }
            catalogNs {
              mappings {
                pageSlug
                pageType
              }
            }
          }
        }
      }
    }
    """

    close_client = False
    http_client = client
    if http_client is None:
        http_client = httpx.AsyncClient(
            timeout=10.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json",
            },
        )
        close_client = True

    try:
        for kw in keywords_to_try:
            payload = {"query": query, "variables": {"keywords": kw, "locale": "en-US"}}
            try:
                resp = await http_client.post(
                    EPIC_GRAPHQL_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=8.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elements = (
                        data.get("data", {})
                        .get("Catalog", {})
                        .get("searchStore", {})
                        .get("elements", [])
                    )
                    for el in elements:
                        # Extract productHome pageSlug from offerMappings or catalogNs.mappings
                        for mapping in (el.get("offerMappings") or []):
                            ps = mapping.get("pageSlug")
                            if ps and (mapping.get("pageType") == "productHome" or ps == slug or ps.startswith(base_slug)):
                                return normalize_epic_claim_url(f"https://store.epicgames.com/p/{ps}")

                        for mapping in (el.get("catalogNs", {}).get("mappings") or []):
                            ps = mapping.get("pageSlug")
                            if ps and (mapping.get("pageType") == "productHome" or ps == slug or ps.startswith(base_slug)):
                                return normalize_epic_claim_url(f"https://store.epicgames.com/p/{ps}")

                        if el.get("productSlug"):
                            ps = str(el["productSlug"]).split("/")[0]
                            return normalize_epic_claim_url(f"https://store.epicgames.com/p/{ps}")
            except Exception as e:
                logger.debug("Epic GraphQL search error for '%s': %s", kw, e)
    finally:
        if close_client:
            await http_client.aclose()

    # If slug already contains a canonical product hash (e.g. -d7c88c), preserve canonical format
    if re.search(r"-[a-f0-9]{6,}$", slug):
        return normalize_epic_claim_url(f"https://store.epicgames.com/p/{slug}")

    return None


async def validate_claim_url(
    offer_or_url: Any,
    source: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Source-generic preflight URL validation and canonicalization.
    Performs:
    1. HTTPS validation
    2. Trusted domain validation
    3. Canonical path validation
    4. Lightweight GET/HEAD or API preflight
    5. Redirect inspection
    6. Product page validity assertion

    Rejects:
    - /not-found, 404, invalid product pages
    - third-party redirects, URL shorteners, tracking hosts
    - incomplete slugs that fail canonical resolution
    """
    is_offer_obj = isinstance(offer_or_url, FreeGameOffer)
    if is_offer_obj:
        raw_url = getattr(offer_or_url, "canonical_claim_url", None) or offer_or_url.claim_url
        src = (offer_or_url.source or source or "").lower().replace("-", "_").replace(" ", "_")
    else:
        raw_url = str(offer_or_url) if offer_or_url else ""
        src = (source or "").lower().replace("-", "_").replace(" ", "_")

    if not raw_url or not raw_url.strip():
        if is_offer_obj:
            offer_or_url.claim_url_status = "INVALID"
        logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: No claim URL provided")
        return False, "SKIPPED_OFFER_NO_CLAIM_URL", None

    clean_url = raw_url.strip()

    # 1 & 2. HTTPS and security trust check
    is_secure, sec_reason = validate_claim_url_security(clean_url, src)
    if not is_secure:
        if is_offer_obj:
            offer_or_url.claim_url_status = "INVALID"
        logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: %s (%s)", sec_reason, clean_url)
        return False, sec_reason, None

    parsed = urlparse(clean_url)
    path = parsed.path.lower()

    # Check for obvious not-found destinations
    if "/not-found" in path or "/404" in path or path in ("", "/"):
        if is_offer_obj:
            offer_or_url.claim_url_status = "INVALID"
        logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: Invalid destination path %s", clean_url)
        return False, "SKIPPED_OFFER_INVALID_CLAIM_URL", None

    # 3. Source-specific canonical path checks & preflight
    if src == "epic":
        if not (path.startswith("/p/") or path.startswith("/product/")):
            if is_offer_obj:
                offer_or_url.claim_url_status = "INVALID"
            logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: Invalid Epic path %s", clean_url)
            return False, "SKIPPED_OFFER_INVALID_CLAIM_URL", None

        # Preflight & canonical resolution via Epic API
        canonical = await resolve_canonical_epic_url(clean_url, client=client)
        if not canonical:
            if is_offer_obj:
                offer_or_url.claim_url_status = "INVALID"
            logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: Could not resolve canonical Epic URL for %s", clean_url)
            return False, "SKIPPED_OFFER_INVALID_CLAIM_URL", None

        if is_offer_obj:
            offer_or_url.canonical_claim_url = canonical
            offer_or_url.claim_url = canonical
            offer_or_url.claim_url_status = "VALID"
            offer_or_url.validated_at = datetime.utcnow()
        return True, "OK", canonical

    elif src in ("steam", "gog", "google_play", "app_store"):
        # Check source path conventions
        if src == "steam" and not re.search(r"/(?:app|sub)/\d+", path):
            if is_offer_obj:
                offer_or_url.claim_url_status = "INVALID"
            logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: Invalid Steam path %s", clean_url)
            return False, "SKIPPED_OFFER_INVALID_CLAIM_URL", None

        if src == "gog" and "/game/" not in path:
            if is_offer_obj:
                offer_or_url.claim_url_status = "INVALID"
            logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: Invalid GOG path %s", clean_url)
            return False, "SKIPPED_OFFER_INVALID_CLAIM_URL", None

        if src == "google_play" and "id=" not in clean_url:
            if is_offer_obj:
                offer_or_url.claim_url_status = "INVALID"
            logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: Invalid Google Play URL %s", clean_url)
            return False, "SKIPPED_OFFER_INVALID_CLAIM_URL", None

        if src == "app_store" and "id" not in path:
            if is_offer_obj:
                offer_or_url.claim_url_status = "INVALID"
            logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: Invalid Apple App Store URL %s", clean_url)
            return False, "SKIPPED_OFFER_INVALID_CLAIM_URL", None

        # HTTP preflight validation with redirect inspection
        close_client = False
        http_client = client
        if http_client is None:
            http_client = httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            close_client = True

        try:
            resp = await http_client.head(clean_url, timeout=8.0)
            if resp.status_code >= 400:
                resp = await http_client.get(clean_url, timeout=8.0)

            if resp.status_code >= 400:
                if is_offer_obj:
                    offer_or_url.claim_url_status = "INVALID"
                logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: HTTP %d for %s", resp.status_code, clean_url)
                return False, f"HTTP_{resp.status_code}", None

            final_url_str = str(resp.url)
            final_parsed = urlparse(final_url_str)
            final_host = (final_parsed.hostname or "").lower()

            # Verify trusted domain after redirects
            trusted = TRUSTED_SOURCE_DOMAINS.get(src, set())
            is_trusted = False
            for td in trusted:
                if final_host == td or final_host.endswith(f".{td}"):
                    is_trusted = True
                    break

            if not is_trusted:
                if is_offer_obj:
                    offer_or_url.claim_url_status = "INVALID"
                logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: Untrusted redirect to %s", final_url_str)
                return False, "UNTRUSTED_REDIRECT_DESTINATION", None

            # Verify final page is not a 404/not-found or root homepage
            final_path = final_parsed.path.lower()
            if "/not-found" in final_path or "/404" in final_path or "/error" in final_path:
                if is_offer_obj:
                    offer_or_url.claim_url_status = "INVALID"
                logger.warning("SKIPPED_OFFER_INVALID_CLAIM_URL: Final URL is error page: %s", final_url_str)
                return False, "SKIPPED_OFFER_INVALID_CLAIM_URL", None

            canonical = normalize_claim_url(final_url_str, source=src)
            if is_offer_obj:
                offer_or_url.canonical_claim_url = canonical
                offer_or_url.claim_url = canonical
                offer_or_url.claim_url_status = "VALID"
                offer_or_url.validated_at = datetime.utcnow()
            return True, "OK", canonical

        except Exception as e:
            logger.debug("[%s] Preflight check exception for %s: %s", src, clean_url, e)
            canonical = normalize_claim_url(clean_url, source=src)
            if is_offer_obj:
                offer_or_url.canonical_claim_url = canonical
                offer_or_url.claim_url = canonical
                offer_or_url.claim_url_status = "VALID"
                offer_or_url.validated_at = datetime.utcnow()
            return True, "OK", canonical
        finally:
            if close_client:
                await http_client.aclose()

    # Generic fallback
    canonical = normalize_claim_url(clean_url, source=src)
    if is_offer_obj:
        offer_or_url.canonical_claim_url = canonical
        offer_or_url.claim_url = canonical
        offer_or_url.claim_url_status = "VALID"
        offer_or_url.validated_at = datetime.utcnow()
    return True, "OK", canonical


def validate_offer_eligibility(
    offer: FreeGameOffer,
    allowed_offer_types: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Verify offer completeness and eligibility for notification.
    """
    if not offer.title or not offer.title.strip():
        return False, "MISSING_TITLE"

    if not offer.source or not offer.source.strip():
        return False, "MISSING_SOURCE"

    # Claim URL verification
    is_valid_url, reason = validate_claim_url_security(offer.claim_url, offer.source)
    if not is_valid_url:
        logger.warning("FreeGames claim URL rejected for '%s': %s (URL: %s)", offer.title, reason, offer.claim_url)
        return False, reason

    # Price verification: must be free
    if not offer.is_free and offer.current_price > 0:
        return False, f"NOT_FREE: price={offer.current_price}"

    # Offer type verification
    if allowed_offer_types is not None:
        if offer.offer_type not in allowed_offer_types:
            return False, f"OFFER_TYPE_DISABLED: {offer.offer_type}"
    else:
        # Default behavior: FREE_TO_PLAY is disabled unless explicitly permitted
        if offer.offer_type == OfferType.FREE_TO_PLAY.value:
            return False, "FREE_TO_PLAY_DISABLED_BY_DEFAULT"

    # Expiry verification: if already expired, do not post
    if offer.ends_at:
        now = datetime.now(timezone.utc)
        ends = offer.ends_at if offer.ends_at.tzinfo else offer.ends_at.replace(tzinfo=timezone.utc)
        if ends < now:
            return False, "OFFER_ALREADY_EXPIRED"

    return True, "ELIGIBLE"
