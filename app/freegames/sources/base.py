"""
Base class and common interface for Free Game Source adapters.
"""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import httpx

from app.freegames.normalizer import normalize_claim_url
from app.freegames.schemas import FreeGameOffer, SourceHealth, SourceStatus

logger = logging.getLogger("pbhero.freegames.sources")

DEFAULT_USER_AGENT = "PBHeroBot/2.0 (FreeGamesTracker; +https://github.com/PBtoolsfree/OWN-DC-BOT)"


class FreeGameSource(ABC):
    """Abstract base class for all pluggable free game sources."""

    name: str = "base"
    category: str = "pc"  # "pc" or "mobile"
    trusted_domains: Set[str] = set()

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client
        self.last_checked_at: Optional[datetime] = None
        self.last_success_at: Optional[datetime] = None
        self.last_error_at: Optional[datetime] = None
        self.last_error_message: Optional[str] = None
        self.consecutive_failures: int = 0
        self.last_offer_count: int = 0
        self.last_latency_ms: Optional[float] = None

    @abstractmethod
    async def fetch_offers(self) -> List[FreeGameOffer]:
        """Fetch and return normalized FreeGameOffer items from the source."""
        pass

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client and not self._client.is_closed:
            return self._client
        return httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"User-Agent": DEFAULT_USER_AGENT},
            follow_redirects=True,
        )

    async def _fetch_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 15.0,
        retries: int = 2,
    ) -> Any:
        """Fetch JSON with retry and exponential backoff."""
        req_headers = {"User-Agent": DEFAULT_USER_AGENT}
        if headers:
            req_headers.update(headers)

        last_exc = None
        for attempt in range(retries + 1):
            try:
                client = await self._get_client()
                resp = await client.get(url, params=params, headers=req_headers, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                if attempt < retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))

        logger.warning("[%s] Failed to fetch JSON from %s: %s", self.name, url, last_exc)
        raise last_exc

    async def _resolve_canonical_redirect(self, raw_url: str) -> Optional[str]:
        """
        Safely resolve redirect to retrieve canonical store claim URL.
        Verifies that final destination belongs to this source's trusted domains.
        """
        if not raw_url:
            return None

        clean = normalize_claim_url(raw_url)
        parsed = urlparse(clean)
        # If already on trusted domain, return directly
        if self.is_trusted_url(clean):
            return clean

        try:
            client = await self._get_client()
            # Follow redirects up to 3 hops without auto-redirecting to untrusted targets
            resp = await client.head(clean, follow_redirects=True, timeout=8.0)
            final_url = str(resp.url)
            norm_final = normalize_claim_url(final_url)
            if self.is_trusted_url(norm_final):
                return norm_final
            logger.info("[%s] Resolved redirect to untrusted domain: %s", self.name, norm_final)
            return None
        except Exception as e:
            logger.debug("[%s] Redirect resolution failed for %s: %s", self.name, raw_url, e)
            return None

    def is_trusted_url(self, url: str) -> bool:
        """Verify URL hostname belongs to source's trusted domains."""
        try:
            hostname = (urlparse(url).hostname or "").lower()
            for td in self.trusted_domains:
                if hostname == td or hostname.endswith(f".{td}"):
                    return True
        except Exception:
            pass
        return False

    def record_success(self, count: int, latency_ms: float) -> None:
        self.last_checked_at = datetime.utcnow()
        self.last_success_at = self.last_checked_at
        self.consecutive_failures = 0
        self.last_offer_count = count
        self.last_latency_ms = latency_ms

    def record_failure(self, error_message: str, latency_ms: Optional[float] = None) -> None:
        self.last_checked_at = datetime.utcnow()
        self.last_error_at = self.last_checked_at
        self.last_error_message = error_message
        self.consecutive_failures += 1
        if latency_ms is not None:
            self.last_latency_ms = latency_ms

    def get_health(self) -> SourceHealth:
        status = SourceStatus.HEALTHY.value
        if self.consecutive_failures >= 3:
            status = SourceStatus.ERROR.value
        elif self.consecutive_failures > 0:
            status = SourceStatus.DEGRADED.value

        return SourceHealth(
            source_name=self.name,
            category=self.category,
            status=status,
            last_checked_at=self.last_checked_at,
            last_success_at=self.last_success_at,
            last_error_at=self.last_error_at,
            last_error_message=self.last_error_message,
            consecutive_failures=self.consecutive_failures,
            offer_count=self.last_offer_count,
            response_latency_ms=self.last_latency_ms,
        )
