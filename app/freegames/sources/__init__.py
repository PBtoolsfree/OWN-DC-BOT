"""
Source registry and factory for Free Games & Deals Tracker.
"""

from typing import Dict, List, Optional, Type

from app.freegames.sources.app_store import AppStoreSource
from app.freegames.sources.base import FreeGameSource
from app.freegames.sources.epic import EpicGamesSource
from app.freegames.sources.gog import GOGSource
from app.freegames.sources.google_play import GooglePlaySource
from app.freegames.sources.steam import SteamSource

SOURCE_REGISTRY: Dict[str, Type[FreeGameSource]] = {
    "epic": EpicGamesSource,
    "steam": SteamSource,
    "gog": GOGSource,
    "google_play": GooglePlaySource,
    "app_store": AppStoreSource,
}


def register_source(name: str, source_cls: Type[FreeGameSource]) -> None:
    """Register a new custom source adapter."""
    SOURCE_REGISTRY[name.lower()] = source_cls


def get_source(name: str) -> Optional[FreeGameSource]:
    """Instantiate a source adapter by name."""
    cls = SOURCE_REGISTRY.get(name.lower())
    return cls() if cls else None


def get_all_sources() -> List[FreeGameSource]:
    """Instantiate and return all registered sources."""
    return [cls() for cls in SOURCE_REGISTRY.values()]


def get_available_source_names() -> List[str]:
    """Get list of registered source identifiers."""
    return list(SOURCE_REGISTRY.keys())


__all__ = [
    "AppStoreSource",
    "EpicGamesSource",
    "FreeGameSource",
    "GOGSource",
    "GooglePlaySource",
    "SteamSource",
    "get_all_sources",
    "get_available_source_names",
    "get_source",
    "register_source",
]
