"""
Validation and security verification for Free Games & Deals Tracker.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

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
