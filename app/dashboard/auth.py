"""
PB HERO Dashboard Authentication.

Secure password authentication with Argon2id hashing.
Session management, rate limiting, and brute-force protection.
"""

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.requests import Request

from app.config import get_settings

logger = logging.getLogger("pbhero.dashboard")

# Argon2id hasher
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

# Rate limiting state
_login_attempts: dict[str, list[float]] = {}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutes


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against an Argon2id hash."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def check_rate_limit(ip_address: str) -> tuple[bool, int]:
    """
    Check if login attempts are rate limited.

    Returns (is_allowed, seconds_remaining).
    """
    now = time.time()

    if ip_address not in _login_attempts:
        _login_attempts[ip_address] = []
        return True, 0

    # Clean old attempts
    _login_attempts[ip_address] = [
        t for t in _login_attempts[ip_address]
        if now - t < LOCKOUT_SECONDS
    ]

    attempts = _login_attempts[ip_address]

    if len(attempts) >= MAX_ATTEMPTS:
        oldest = min(attempts)
        remaining = int(LOCKOUT_SECONDS - (now - oldest))
        return False, max(remaining, 0)

    return True, 0


def record_login_attempt(ip_address: str) -> None:
    """Record a failed login attempt."""
    if ip_address not in _login_attempts:
        _login_attempts[ip_address] = []
    _login_attempts[ip_address].append(time.time())


def clear_login_attempts(ip_address: str) -> None:
    """Clear login attempts after successful login."""
    _login_attempts.pop(ip_address, None)


# Session management
class SessionManager:
    """Secure session management using signed cookies."""

    def __init__(self, secret_key: str, max_age: int = 86400):
        self.serializer = URLSafeTimedSerializer(secret_key)
        self.max_age = max_age  # 24 hours default

    def create_session(self, username: str) -> str:
        """Create a signed session token."""
        data = {
            "username": username,
            "created": datetime.utcnow().isoformat(),
            "nonce": secrets.token_hex(8),
        }
        return self.serializer.dumps(data, salt="pbhero-session")

    def validate_session(self, token: str) -> Optional[dict]:
        """Validate a session token. Returns session data or None."""
        try:
            data = self.serializer.loads(token, salt="pbhero-session", max_age=self.max_age)
            return data
        except (BadSignature, SignatureExpired):
            return None

    def get_username(self, token: str) -> Optional[str]:
        """Extract username from session token."""
        data = self.validate_session(token)
        if data:
            return data.get("username")
        return None


def get_client_ip(request: Request) -> str:
    """Get the client IP address from request."""
    # Check X-Forwarded-For for reverse proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def generate_csrf_token(session_token: str) -> str:
    """Generate a CSRF token tied to the session."""
    return hashlib.sha256(f"csrf:{session_token}:pbhero".encode()).hexdigest()[:32]


def validate_csrf_token(session_token: str, csrf_token: str) -> bool:
    """Validate a CSRF token against the session."""
    expected = generate_csrf_token(session_token)
    return secrets.compare_digest(expected, csrf_token)
