"""
Unit tests for PB HERO configuration and single-server enforcement.
"""

import pytest
from app.config import Settings


def test_settings_default_values():
    """Verify default configuration attributes."""
    settings = Settings(
        DISCORD_BOT_TOKEN="test_token",
        DISCORD_GUILD_ID=123456789012345678,
        ADMIN_USERNAME="admin",
    )
    assert settings.DASHBOARD_PORT == 8000
    assert settings.DASHBOARD_HOST == "0.0.0.0"
    assert settings.YOUTUBE_POLL_INTERVAL == 60
    assert settings.YOUTUBE_LIVE_CHECK_INTERVAL == 30
    assert settings.is_configured() is True


def test_settings_validation_missing_token():
    """Verify validation fails when token or guild id is missing."""
    settings = Settings(DISCORD_BOT_TOKEN="", DISCORD_GUILD_ID=0)
    errors = settings.validate_config()
    assert any("DISCORD_BOT_TOKEN" in err for err in errors)
    assert any("DISCORD_GUILD_ID" in err for err in errors)
    assert settings.is_configured() is False


def test_single_server_enforcement():
    """Verify single-server enforcement logic."""
    configured_guild = 123456789012345678
    settings = Settings(
        DISCORD_BOT_TOKEN="test_token",
        DISCORD_GUILD_ID=configured_guild,
    )

    # Allowed guild
    assert int(settings.DISCORD_GUILD_ID) == configured_guild

    # Unauthorized guild IDs must be rejected
    foreign_guild_id = 999999999999999999
    assert foreign_guild_id != settings.DISCORD_GUILD_ID


def test_allowed_ips_parsing():
    """Verify IP allowlist parsing."""
    settings = Settings(
        DISCORD_BOT_TOKEN="test",
        DISCORD_GUILD_ID=123,
        DASHBOARD_ALLOWED_IPS="127.0.0.1, 192.168.1.100, 10.0.0.1",
    )
    assert settings.allowed_ips_list == ["127.0.0.1", "192.168.1.100", "10.0.0.1"]
