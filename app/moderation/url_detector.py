"""
PB HERO URL Detector.

Real URL detection for link blocking. Detects http/https, www,
markdown links, Discord invites, shortened URLs.
"""

import re
from typing import Optional


# Comprehensive URL patterns
URL_PATTERNS = [
    # Standard URLs
    re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE),
    # www. URLs without protocol
    re.compile(r'(?<!\S)www\.[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE),
    # Markdown links [text](url)
    re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)', re.IGNORECASE),
    # Discord invite links
    re.compile(r'(?:discord\.gg|discord\.com/invite|discordapp\.com/invite)/[\w-]+', re.IGNORECASE),
]

# Common shortened URL domains
SHORTENED_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "cutt.ly", "rb.gy", "shorturl.at",
    "tiny.cc", "v.gd", "qr.ae", "link.ac",
}

# Domain extraction pattern
DOMAIN_PATTERN = re.compile(r'(?:https?://)?(?:www\.)?([^/\s:]+)', re.IGNORECASE)


def detect_urls(text: str) -> list[str]:
    """
    Detect all URLs in a text string.

    Returns list of found URLs.
    """
    if not text:
        return []

    found_urls = set()

    for pattern in URL_PATTERNS:
        for match in pattern.finditer(text):
            url = match.group(0)
            # Clean up trailing punctuation
            url = url.rstrip(".,;:!?)>\"'")
            found_urls.add(url)

    return list(found_urls)


def contains_url(text: str) -> bool:
    """Check if text contains any URL."""
    return len(detect_urls(text)) > 0


def extract_domain(url: str) -> Optional[str]:
    """Extract the domain from a URL."""
    match = DOMAIN_PATTERN.match(url)
    if match:
        domain = match.group(1).lower()
        # Remove port if present
        if ":" in domain:
            domain = domain.split(":")[0]
        return domain
    return None


def is_domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    """
    Check if a URL's domain is in the allowed list.

    Supports:
    - Exact match: youtube.com
    - Subdomain match: *.youtube.com matches www.youtube.com
    """
    domain = extract_domain(url)
    if not domain:
        return False

    for allowed in allowed_domains:
        allowed = allowed.lower().strip()
        if not allowed:
            continue
        # Exact match
        if domain == allowed:
            return True
        # Subdomain match
        if domain.endswith(f".{allowed}"):
            return True

    return False


def is_discord_invite(text: str) -> bool:
    """Check if text contains a Discord invite link."""
    patterns = [
        re.compile(r'discord\.gg/[\w-]+', re.IGNORECASE),
        re.compile(r'discord\.com/invite/[\w-]+', re.IGNORECASE),
        re.compile(r'discordapp\.com/invite/[\w-]+', re.IGNORECASE),
    ]
    return any(p.search(text) for p in patterns)


def is_shortened_url(url: str) -> bool:
    """Check if a URL uses a known URL shortener."""
    domain = extract_domain(url)
    if domain:
        return domain.lower() in SHORTENED_DOMAINS
    return False


def filter_urls(text: str, allowed_domains: list[str] = None) -> list[dict]:
    """
    Analyze all URLs in text and classify them.

    Returns list of dicts with url, domain, allowed, is_invite, is_shortened.
    """
    urls = detect_urls(text)
    results = []

    for url in urls:
        domain = extract_domain(url)
        allowed = False
        if allowed_domains:
            allowed = is_domain_allowed(url, allowed_domains)

        results.append({
            "url": url,
            "domain": domain,
            "allowed": allowed,
            "is_invite": is_discord_invite(url),
            "is_shortened": is_shortened_url(url),
        })

    return results
