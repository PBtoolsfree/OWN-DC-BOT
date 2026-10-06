"""
Pydantic and dataclass schemas for Free Games & Deals Tracker.
"""

from dataclasses import dataclass, field
from datetime import datetime
import enum
from typing import Any, Dict, List, Optional


class OfferType(str, enum.Enum):
    FREE_TO_KEEP = "free_to_keep"
    FREE_DLC = "free_dlc"
    FREE_TRIAL = "free_trial"
    FREE_TO_PLAY = "free_to_play"


class OfferStatus(str, enum.Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    ENDING_SOON = "ENDING_SOON"
    EXPIRED = "EXPIRED"
    REMOVED = "REMOVED"


class SourceStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


@dataclass
class FreeGameOffer:
    """Normalized free game or deal offer representation."""
    source: str
    external_id: str
    title: str
    store_name: str
    platform: str
    claim_url: str
    canonical_claim_url: Optional[str] = None
    claim_url_status: str = "VALID"
    validated_at: Optional[datetime] = None
    description: Optional[str] = None
    offer_type: str = OfferType.FREE_TO_KEEP.value
    original_price: Optional[float] = None
    current_price: float = 0.0
    currency: str = "USD"
    discount_percent: int = 100
    source_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_free: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    unique_key: Optional[str] = None

    def __post_init__(self):
        if not self.canonical_claim_url:
            self.canonical_claim_url = self.claim_url
        if not self.unique_key:
            self.unique_key = f"{self.source}:{self.external_id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "external_id": self.external_id,
            "unique_key": self.unique_key,
            "title": self.title,
            "description": self.description,
            "store_name": self.store_name,
            "platform": self.platform,
            "offer_type": self.offer_type,
            "original_price": self.original_price,
            "current_price": self.current_price,
            "currency": self.currency,
            "discount_percent": self.discount_percent,
            "claim_url": self.claim_url,
            "canonical_claim_url": self.canonical_claim_url or self.claim_url,
            "claim_url_status": self.claim_url_status,
            "validated_at": self.validated_at,
            "source_url": self.source_url,
            "thumbnail_url": self.thumbnail_url,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "is_free": self.is_free,
            "raw_metadata_json": None,
        }


@dataclass
class SourceHealth:
    """Source health and operational metrics."""
    source_name: str
    category: str
    status: str
    last_checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    consecutive_failures: int = 0
    offer_count: int = 0
    response_latency_ms: Optional[float] = None
