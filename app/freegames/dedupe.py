"""
Deduplication and lifecycle tracking for Free Games & Deals Tracker.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import logging
from typing import Any, Optional

from app.freegames.normalizer import normalize_claim_url
from app.freegames.schemas import FreeGameOffer, OfferStatus

logger = logging.getLogger("pbhero.freegames.dedupe")


def compute_offer_unique_key(source: str, external_id: Optional[str] = None, claim_url: Optional[str] = None) -> str:
    """
    Generate deterministic unique identity:
    Primary: source:external_id
    Fallback: source:sha256(normalized_claim_url)
    """
    clean_src = (source or "unknown").strip().lower()
    if external_id and str(external_id).strip():
        clean_ext = str(external_id).strip()
        return f"{clean_src}:{clean_ext}"

    if claim_url:
        norm_url = normalize_claim_url(claim_url)
        url_hash = hashlib.sha256(norm_url.encode("utf-8")).hexdigest()[:16]
        return f"{clean_src}:{url_hash}"

    return f"{clean_src}:unidentified"


def is_new_or_reactivated_offer(
    existing_status: Optional[str],
    existing_ends_at: Optional[datetime],
    new_ends_at: Optional[datetime],
    is_currently_free: bool = True,
) -> bool:
    """
    Determine if an offer should trigger a new notification:
    - Truly new (no existing record): True
    - Previously EXPIRED or REMOVED, but now active again with a future ends_at: True (new cycle)
    - Already ACTIVE or NEW: False (prevent duplicate posting)
    """
    if not existing_status:
        return True

    if existing_status in (OfferStatus.EXPIRED.value, OfferStatus.REMOVED.value):
        now = datetime.utcnow()
        if is_currently_free and (new_ends_at is None or new_ends_at > now):
            # If the offer has a new future end date or is free again
            if existing_ends_at is None or new_ends_at is None or new_ends_at > existing_ends_at:
                return True

    return False


def is_duplicate_offer(new_offer: FreeGameOffer, existing_model: Optional[Any]) -> bool:
    """
    Check if an incoming offer is an active duplicate that should NOT trigger a new Discord post.
    Returns True if it's a duplicate (do not post), False if it is new/reactivated and should be posted.
    """
    if existing_model is None:
        return False

    status = getattr(existing_model, "status", None)
    has_posted = bool(getattr(existing_model, "posted_message_id", None))

    if status in (OfferStatus.ACTIVE.value, OfferStatus.NEW.value, OfferStatus.ENDING_SOON.value) and has_posted:
        return True

    # Check if reactivated from expired
    ends_at = getattr(existing_model, "ends_at", None)
    if is_new_or_reactivated_offer(status, ends_at, new_offer.ends_at, new_offer.is_free):
        return False

    return True


def should_send_ending_soon(offer: Any, ending_soon_hours: int = 24) -> bool:
    """
    Check if an offer is expiring soon within the configured threshold hours.
    """
    ends_at = getattr(offer, "ends_at", None)
    if not ends_at:
        return False

    now = datetime.now(timezone.utc)
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)

    remaining = ends_at - now
    from datetime import timedelta
    return timedelta(0) < remaining <= timedelta(hours=ending_soon_hours)

