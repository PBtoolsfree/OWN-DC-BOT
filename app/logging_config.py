"""
PB HERO Personal Discord Bot - Logging Configuration.

Rotating file logs for app, bot, youtube, moderation, and dashboard.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import LOGS_DIR

# Log file paths
LOG_FILES = {
    "app": LOGS_DIR / "app.log",
    "bot": LOGS_DIR / "bot.log",
    "youtube": LOGS_DIR / "youtube.log",
    "moderation": LOGS_DIR / "moderation.log",
    "dashboard": LOGS_DIR / "dashboard.log",
}

# Format
LOG_FORMAT = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Rotation settings
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
BACKUP_COUNT = 5  # Keep 5 rotated files


def setup_logging(level: str = "INFO") -> None:
    """Configure logging with rotating file handlers."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # App-wide file handler
    app_handler = RotatingFileHandler(
        LOG_FILES["app"], maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    app_handler.setLevel(numeric_level)
    app_handler.setFormatter(formatter)
    root_logger.addHandler(app_handler)

    # Module-specific loggers with dedicated files
    for module_name, log_path in LOG_FILES.items():
        if module_name == "app":
            continue
        logger = logging.getLogger(f"pbhero.{module_name}")
        logger.setLevel(numeric_level)
        file_handler = RotatingFileHandler(
            log_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.propagate = True

    # Suppress noisy third-party loggers
    for noisy_logger in ["discord.http", "discord.gateway", "aiosqlite", "httpx", "uvicorn.access"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logging.getLogger("pbhero").info("Logging initialized at level %s", level)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the pbhero namespace."""
    return logging.getLogger(f"pbhero.{name}")
