"""
PB HERO Shared Runtime State Module.

Authoritative singleton store for application runtime state and bot instance.
Decoupled from app.main to avoid module dual-import issues when launched with `python -m app.main`.
"""

import enum
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.bot.client import PBHeroBot

logger = logging.getLogger("pbhero.runtime")


class BotState(str, enum.Enum):
    """Possible runtime lifecycle states for PB HERO Bot."""
    STARTING = "STARTING"
    READY = "READY"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


_bot_instance: Optional["PBHeroBot"] = None
_bot_state: BotState = BotState.STOPPED


def set_bot_instance(bot: Optional["PBHeroBot"]) -> None:
    """Set the authoritative PBHeroBot instance."""
    global _bot_instance
    _bot_instance = bot


def get_bot_instance() -> Optional["PBHeroBot"]:
    """Get the authoritative PBHeroBot instance."""
    return _bot_instance


def set_bot_state(state: BotState) -> None:
    """Update current lifecycle state."""
    global _bot_state
    _bot_state = state
    logger.debug("Runtime bot state changed to: %s", state.value)


def get_bot_state() -> BotState:
    """Get current lifecycle state."""
    return _bot_state


def is_bot_ready() -> bool:
    """
    Check if the bot is ready and connected.

    Guarantees that bot instance exists, lifecycle state is READY,
    and discord client is connected and not closed.
    """
    if _bot_instance is None or _bot_state != BotState.READY:
        return False
    try:
        return bool(_bot_instance.is_ready() and not _bot_instance.is_closed())
    except Exception:
        return False


def is_youtube_healthy() -> bool:
    """Check if the YouTube scheduler is healthy on the authoritative bot instance."""
    if not is_bot_ready() or _bot_instance is None:
        return False
    scheduler = getattr(_bot_instance, "youtube_scheduler", None)
    if scheduler:
        return bool(getattr(scheduler, "is_healthy", False))
    return False


def is_youtube_running() -> bool:
    """Check if the YouTube scheduler is running on the authoritative bot instance."""
    if not is_bot_ready() or _bot_instance is None:
        return False
    scheduler = getattr(_bot_instance, "youtube_scheduler", None)
    if scheduler:
        return bool(getattr(scheduler, "is_running", False))
    return False


def clear_bot_instance() -> None:
    """Clear authoritative bot instance and reset state to STOPPED."""
    global _bot_instance, _bot_state
    _bot_instance = None
    _bot_state = BotState.STOPPED
