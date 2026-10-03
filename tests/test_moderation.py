"""
Tests for PB HERO moderation components:
- URL detector and domain filtering
- Discord invite detector
- Mention filtering
- Moderation action rules
"""

from unittest.mock import MagicMock
import pytest
from app.moderation.url_detector import (
    contains_url,
    detect_urls,
    extract_domain,
    is_discord_invite,
    is_domain_allowed,
    is_shortened_url,
)
from app.moderation.mention_filter import check_mentions


def test_detect_urls():
    """Verify URL detection in various text formats."""
    text = "Visit https://google.com and http://example.org/test for details."
    urls = detect_urls(text)
    assert len(urls) == 2
    assert "https://google.com" in urls
    assert "http://example.org/test" in urls

    assert contains_url("Hello world!") is False
    assert contains_url("Check this: www.github.com") is True


def test_discord_invite_detector():
    """Verify Discord invite link identification."""
    assert is_discord_invite("Join our group: discord.gg/abcdef123") is True
    assert is_discord_invite("Check discord.com/invite/xyz987 today") is True
    assert is_discord_invite("discordapp.com/invite/cool-server") is True
    assert is_discord_invite("Just talking about discord.com website") is False


def test_domain_filtering():
    """Verify allowed domains list matching with subdomains."""
    allowed = ["youtube.com", "github.com"]

    assert is_domain_allowed("https://youtube.com/watch?v=123", allowed) is True
    assert is_domain_allowed("https://www.youtube.com/watch?v=123", allowed) is True
    assert is_domain_allowed("https://github.com/PBtoolsfree", allowed) is True
    assert is_domain_allowed("https://malicious-site.ru/hack", allowed) is False


def test_shortened_url_detector():
    """Verify shortened URL detection."""
    assert is_shortened_url("https://bit.ly/3xyzABC") is True
    assert is_shortened_url("https://tinyurl.com/something") is True
    assert is_shortened_url("https://google.com/search") is False


def test_mention_filter_everyone_here():
    """Verify blocking @everyone and @here when denied by policy."""
    policy = {
        "allow_everyone": "deny",
        "allow_here": "deny",
        "allow_role_mentions": "allow",
        "allow_user_mentions": "allow",
    }

    # Mock Discord message with @everyone
    msg_everyone = MagicMock()
    msg_everyone.mention_everyone = True
    msg_everyone.content = "@everyone hello team!"
    msg_everyone.role_mentions = []
    msg_everyone.mentions = []

    res = check_mentions(msg_everyone, policy)
    assert res is not None
    assert res["rule"] == "everyone_denied"

    # Mock Discord message with @here in text
    msg_here = MagicMock()
    msg_here.mention_everyone = False
    msg_here.content = "Attention @here please read"
    msg_here.role_mentions = []
    msg_here.mentions = []

    res_here = check_mentions(msg_here, policy)
    assert res_here is not None
    assert res_here["rule"] == "here_denied"

    # Allowed message
    msg_clean = MagicMock()
    msg_clean.mention_everyone = False
    msg_clean.content = "Regular friendly message"
    msg_clean.role_mentions = []
    msg_clean.mentions = []

    assert check_mentions(msg_clean, policy) is None
