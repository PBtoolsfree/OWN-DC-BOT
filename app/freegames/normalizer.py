"""
URL, price, and metadata normalizer for Free Games & Deals Tracker.
"""

from datetime import datetime, timezone
import re
from typing import Any, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "ref",
    "referrer",
    "affiliate",
    "aff",
    "ref_id",
    "fbclid",
    "gclid",
    "gbraid",
    "wbraid",
    "msclkid",
    "mc_eid",
    "session",
    "session_id",
    "source",
}


def normalize_claim_url(raw_url: str, source_hint: Optional[str] = None, source: Optional[str] = None) -> str:
    """
    Clean and canonicalize a store claim URL.
    - Forces HTTPS
    - Lowercases hostname
    - Strips marketing/tracking query parameters
    - Normalizes known store URL patterns
    """
    hint = source or source_hint
    if not raw_url or not isinstance(raw_url, str):
        return ""

    raw_url = raw_url.strip()
    if not raw_url.startswith(("http://", "https://")):
        raw_url = f"https://{raw_url}"

    parsed = urlparse(raw_url)
    scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path

    # Clean query parameters
    clean_query = []
    if parsed.query:
        query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        for k, v in query_pairs:
            if k.lower() not in TRACKING_PARAMS:
                clean_query.append((k, v))

    # Store-specific canonical normalization
    # 1. Epic Games Store
    if "epicgames.com" in netloc:
        # Normalize /en-US/p/slug -> /p/slug
        path = re.sub(r"^/[a-zA-Z]{2}(-[a-zA-Z]{2})?/p/", "/p/", path)
        path = re.sub(r"^/[a-zA-Z]{2}(-[a-zA-Z]{2})?/product/", "/p/", path)
        netloc = "store.epicgames.com"

    # 2. Steam
    elif "steampowered.com" in netloc:
        netloc = "store.steampowered.com"
        # Match /app/123456/Optional_Title/ -> /app/123456/
        m = re.match(r"^/app/(\d+)", path)
        if m:
            path = f"/app/{m.group(1)}/"
            clean_query = []  # Steam app pages don't need query params
        else:
            m_sub = re.match(r"^/sub/(\d+)", path)
            if m_sub:
                path = f"/sub/{m_sub.group(1)}/"
                clean_query = []

    # 3. GOG
    elif "gog.com" in netloc:
        netloc = "www.gog.com"
        path = re.sub(r"^/[a-zA-Z]{2}/game/", "/game/", path)

    # 4. Google Play
    elif "play.google.com" in netloc:
        netloc = "play.google.com"
        # Keep only the 'id' parameter for store details
        id_val = None
        for k, v in clean_query:
            if k == "id":
                id_val = v
                break
        clean_query = [("id", id_val)] if id_val else []

    # 5. Apple App Store
    elif "apple.com" in netloc:
        netloc = "apps.apple.com"
        # Normalize /us/app/title/id12345 -> /app/id12345
        m_app = re.search(r"id(\d+)", path)
        if m_app:
            path = f"/app/id{m_app.group(1)}"
            clean_query = []

    new_query = urlencode(clean_query)
    normalized = urlunparse((scheme, netloc, path, "", new_query, ""))
    return normalized.rstrip("/") if not path.endswith("/") or len(clean_query) > 0 else normalized


def parse_price(price_raw: Any) -> Tuple[Optional[float], float, str, int]:
    """
    Parse raw price information into (original_price, current_price, currency, discount_percent).
    Returns (original_price, current_price, currency, discount_percent).
    """
    if price_raw is None:
        return None, 0.0, "USD", 100

    if isinstance(price_raw, (int, float)):
        val = float(price_raw)
        return val, 0.0, "USD", 100

    text = str(price_raw).strip()
    if text.upper() in ("FREE", "0", "$0", "₹0", "0.0", "N/A"):
        return None, 0.0, "USD", 100

    # Extract currency symbol
    currency = "USD"
    if "₹" in text or "INR" in text.upper():
        currency = "INR"
    elif "€" in text or "EUR" in text.upper():
        currency = "EUR"
    elif "£" in text or "GBP" in text.upper():
        currency = "GBP"

    # Extract digits
    clean_num = re.sub(r"[^\d.]", "", text)
    try:
        orig = float(clean_num) if clean_num else None
        return orig, 0.0, currency, 100
    except ValueError:
        return None, 0.0, currency, 100


def parse_utc_timestamp(val: Any) -> Optional[datetime]:
    """Parse various timestamp representations into a naive UTC datetime."""
    if not val:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is not None:
            return val.astimezone(timezone.utc).replace(tzinfo=None)
        return val

    if isinstance(val, (int, float)):
        # Support millisecond or second UNIX timestamp
        ts = float(val)
        if ts > 1e11:  # milliseconds
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)

    text = str(val).strip()
    # ISO 8601 variants
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    return None
