"""
PB HERO Personal Discord Bot - Configuration Module.

Loads and validates all configuration from environment variables.
Single-server architecture: exactly ONE Discord Guild ID.
"""

import os
import secrets
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

# Load .env file
load_dotenv()

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
BACKUPS_DIR = BASE_DIR / "backups"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Discord
    DISCORD_BOT_TOKEN: str = ""
    DISCORD_GUILD_ID: int = 0

    # Dashboard Authentication
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = ""

    # Dashboard Server
    DASHBOARD_HOST: str = "0.0.0.0"
    DASHBOARD_PORT: int = 8000

    # Session Security
    SESSION_SECRET: str = ""

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR / 'pbhero.db'}"

    # YouTube Monitoring
    YOUTUBE_POLL_INTERVAL: int = 60
    YOUTUBE_LIVE_CHECK_INTERVAL: int = 30

    # Logging
    LOG_LEVEL: str = "INFO"

    # Timezone
    TIMEZONE: str = "Asia/Kolkata"

    # Optional: IP allowlist for dashboard (comma-separated)
    DASHBOARD_ALLOWED_IPS: str = ""

    # Optional: Moderation log channel
    MOD_LOG_CHANNEL_ID: int = 0

    @field_validator("SESSION_SECRET", mode="before")
    @classmethod
    def generate_session_secret(cls, v: str) -> str:
        """Generate a session secret if not provided."""
        if not v:
            return secrets.token_hex(32)
        return v

    @property
    def allowed_ips_list(self) -> list[str]:
        """Parse allowed IPs into a list."""
        if not self.DASHBOARD_ALLOWED_IPS:
            return []
        return [ip.strip() for ip in self.DASHBOARD_ALLOWED_IPS.split(",") if ip.strip()]

    def validate_config(self) -> list[str]:
        """Validate critical configuration. Returns list of errors."""
        errors = []
        if not self.DISCORD_BOT_TOKEN:
            errors.append("DISCORD_BOT_TOKEN is not configured")
        if not self.DISCORD_GUILD_ID:
            errors.append("DISCORD_GUILD_ID is not configured")
        if not self.ADMIN_USERNAME:
            errors.append("ADMIN_USERNAME is not configured")
        return errors

    def is_configured(self) -> bool:
        """Check if minimum configuration is present."""
        return bool(self.DISCORD_BOT_TOKEN and self.DISCORD_GUILD_ID)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def ensure_directories() -> None:
    """Create required directories if they don't exist."""
    for directory in [DATA_DIR, LOGS_DIR, BACKUPS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


# Create directories on import
ensure_directories()
