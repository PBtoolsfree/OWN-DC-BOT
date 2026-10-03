"""
PB HERO Application Main Entry Point.
"""

from typing import Optional
from app.bot.client import PBHeroBot

_bot_instance: Optional[PBHeroBot] = None


def get_bot_instance() -> Optional[PBHeroBot]:
    """Get the active Discord bot instance."""
    return _bot_instance


def set_bot_instance(bot: Optional[PBHeroBot]) -> None:
    """Set the active Discord bot instance."""
    global _bot_instance
    _bot_instance = bot
