"""
PB HERO Dashboard Dependencies.

FastAPI dependencies for authentication, IP filtering, and session validation.
"""

import ipaddress
import logging
from typing import Optional

from fastapi import Cookie, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.dashboard.auth import SessionManager, get_client_ip

logger = logging.getLogger("pbhero.dashboard")
settings = get_settings()

# Initialize session manager
session_manager = SessionManager(settings.SESSION_SECRET)


def check_ip_allowlist(request: Request) -> bool:
    """Check if client IP is in the allowlist. Returns True if allowed."""
    allowed_ips = settings.allowed_ips_list
    if not allowed_ips:
        return True  # No allowlist = all IPs allowed

    client_ip = get_client_ip(request)

    for allowed in allowed_ips:
        try:
            if "/" in allowed:
                # CIDR range
                network = ipaddress.ip_network(allowed, strict=False)
                if ipaddress.ip_address(client_ip) in network:
                    return True
            else:
                if client_ip == allowed:
                    return True
        except (ValueError, TypeError):
            continue

    return False


async def get_current_user(request: Request, session: str = Cookie(None, alias="pbhero_session")) -> Optional[str]:
    """Get the current authenticated user from session cookie."""
    if not session:
        return None

    username = session_manager.get_username(session)
    if not username:
        return None

    return username


async def require_auth(request: Request, session: str = Cookie(None, alias="pbhero_session")) -> str:
    """Require authentication. Raises HTTPException if not authenticated."""
    # Check IP allowlist
    if not check_ip_allowlist(request):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = session_manager.get_username(session)
    if not username:
        raise HTTPException(status_code=401, detail="Session expired")

    return username


def require_auth_redirect(request: Request) -> Optional[str]:
    """Check authentication for page routes. Returns username or None."""
    session = request.cookies.get("pbhero_session")
    if not session:
        return None

    # Check IP allowlist
    if not check_ip_allowlist(request):
        return None

    return session_manager.get_username(session)
