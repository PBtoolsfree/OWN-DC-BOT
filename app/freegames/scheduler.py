"""
Background Polling Scheduler for Free Games & Deals Tracker.

Periodically queries enabled game sources, normalizes and validates offers,
persists state, and delivers rich Discord notifications.
Lightweight design suitable for 1 vCPU / 1 GB RAM environments.
"""

import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, Optional

import discord

from app.freegames.service import get_freegame_service

logger = logging.getLogger("pbhero.freegames.scheduler")


class FreeGamesScheduler:
    """
    Background scheduler for Free Games tracking.
    Polls store sources at configurable intervals (default: 15 minutes).
    Ensures safe error isolation without crashing PB HERO.
    """

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self._running = False
        self._healthy = True
        self._task: Optional[asyncio.Task] = None
        self._last_check: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._error_count = 0
        self._service = get_freegame_service(bot=bot)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    @property
    def last_check(self) -> Optional[datetime]:
        return self._last_check

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def error_count(self) -> int:
        return self._error_count

    async def start(self) -> None:
        """Start the free games polling scheduler."""
        if self._running:
            logger.warning("FreeGames scheduler is already running")
            return

        self._running = True
        self._healthy = True
        self._error_count = 0
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("FreeGames scheduler started successfully")

    async def stop(self) -> None:
        """Stop the free games polling scheduler gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("FreeGames scheduler stopped gracefully")

    async def trigger_immediate_sync(self) -> Dict[str, Any]:
        """Manually trigger an immediate scan across all enabled sources."""
        logger.info("FreeGames immediate sync requested")
        try:
            res = await self._service.sync_offers()
            self._last_check = datetime.utcnow()
            self._healthy = True
            self._error_count = 0
            return res
        except Exception as e:
            self._last_error = str(e)
            self._error_count += 1
            if self._error_count >= 3:
                self._healthy = False
            logger.exception("FreeGames immediate sync error: %s", e)
            return {"error": str(e), "status": "failed"}

    async def _poll_loop(self) -> None:
        """Main polling background loop."""
        try:
            # Wait for bot gateway connection
            if hasattr(self.bot, "wait_until_ready"):
                await self.bot.wait_until_ready()
            # Initial startup delay (8 seconds) to let other systems initialize
            await asyncio.sleep(8)
        except asyncio.CancelledError:
            return

        while self._running:
            interval = 900  # Default 15 minutes
            try:
                cfg = await self._service.get_settings()
                if cfg:
                    interval = max(300, int(cfg.poll_interval_seconds or 900))

                if cfg and cfg.enabled:
                    logger.debug("FreeGames scheduler executing periodic sync")
                    await self._service.sync_offers()
                    self._last_check = datetime.utcnow()
                    self._healthy = True
                    self._error_count = 0
                    self._last_error = None
                else:
                    logger.debug("FreeGames tracker is disabled in settings. Skipping poll.")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._error_count += 1
                self._last_error = str(e)
                if self._error_count >= 3:
                    self._healthy = False
                logger.exception("FreeGames scheduler periodic sync error (count=%d): %s", self._error_count, e)

            # Sleep until next poll interval
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
