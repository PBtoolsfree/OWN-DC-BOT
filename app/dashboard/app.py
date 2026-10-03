"""
PB HERO Dashboard Application.

FastAPI-based web dashboard for the personal Discord bot.
Secure authentication, session management, IP filtering.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.dashboard.auth import (
    check_rate_limit,
    clear_login_attempts,
    generate_csrf_token,
    get_client_ip,
    hash_password,
    record_login_attempt,
    verify_password,
)
from app.dashboard.dependencies import check_ip_allowlist, require_auth_redirect, session_manager
from app.dashboard.routes.api import router as api_router
from app.database.engine import get_session_direct
from app.database.repositories import AdminUserRepo

logger = logging.getLogger("pbhero.dashboard")
settings = get_settings()

# Paths
DASHBOARD_DIR = Path(__file__).parent
TEMPLATES_DIR = DASHBOARD_DIR / "templates"
STATIC_DIR = DASHBOARD_DIR / "static"
WEB_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "dist"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        return response


def create_dashboard_app() -> FastAPI:
    """Create and configure the dashboard FastAPI application."""

    app = FastAPI(
        title="PB HERO Personal Bot Dashboard",
        docs_url=None,  # Disable docs in production
        redoc_url=None,
    )

    # Security middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Static files
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    if (WEB_DIST_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(WEB_DIST_DIR / "assets")), name="assets")

    # Templates
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Include API routes
    app.include_router(api_router)

    # ─── Health Endpoint ──────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        """Public health check endpoint."""
        from app.database.engine import test_connection as db_test
        db_ok = await db_test()

        from app.main import get_bot_instance
        bot = get_bot_instance()
        discord_ok = bot.is_ready() if bot else False

        yt_ok = False
        if bot:
            scheduler = getattr(bot, "youtube_scheduler", None)
            yt_ok = scheduler.is_healthy if scheduler else False

        status = "ok" if (db_ok and discord_ok) else "degraded"

        return {
            "status": status,
            "discord": discord_ok,
            "database": db_ok,
            "youtube": yt_ok,
        }

    # ─── Login Page ───────────────────────────────────────────────────────

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        """Render login page."""
        if not check_ip_allowlist(request):
            return HTMLResponse("Access denied", status_code=403)

        if (WEB_DIST_DIR / "index.html").exists():
            return FileResponse(WEB_DIST_DIR / "index.html")

        # Check if already logged in
        user = require_auth_redirect(request)
        if user:
            return RedirectResponse(url="/", status_code=302)

        return templates.TemplateResponse("login.html", {"request": request, "error": None})

    @app.post("/login")
    async def login_submit(request: Request):
        """Process login form."""
        if not check_ip_allowlist(request):
            return HTMLResponse("Access denied", status_code=403)

        form = await request.form()
        username = form.get("username", "").strip()
        password = form.get("password", "")

        client_ip = get_client_ip(request)

        # Rate limiting
        allowed, remaining = check_rate_limit(client_ip)
        if not allowed:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": f"Too many attempts. Try again in {remaining} seconds.",
            })

        # Validate credentials
        session = await get_session_direct()
        try:
            user = await AdminUserRepo.get_by_username(session, username)
            if user and verify_password(user.password_hash, password):
                clear_login_attempts(client_ip)

                # Create session
                token = session_manager.create_session(username)
                response = RedirectResponse(url="/", status_code=302)
                response.set_cookie(
                    key="pbhero_session",
                    value=token,
                    httponly=True,
                    secure=False,  # Set True when using HTTPS
                    samesite="lax",
                    max_age=86400,  # 24 hours
                    path="/",
                )
                logger.info("Admin login successful: %s from %s", username, client_ip)
                return response
            else:
                record_login_attempt(client_ip)
                logger.warning("Failed login attempt: %s from %s", username, client_ip)
                return templates.TemplateResponse("login.html", {
                    "request": request,
                    "error": "Invalid username or password.",
                })
        finally:
            await session.close()

    @app.get("/logout")
    async def logout():
        """Logout and clear session."""
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("pbhero_session", path="/")
        return response

    # ─── Dashboard Pages ──────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def dashboard_home(request: Request):
        """Main dashboard page."""
        if not check_ip_allowlist(request):
            return HTMLResponse("Access denied", status_code=403)

        if (WEB_DIST_DIR / "index.html").exists():
            return FileResponse(WEB_DIST_DIR / "index.html")

        user = require_auth_redirect(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)

        csrf = generate_csrf_token(request.cookies.get("pbhero_session", ""))
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "username": user,
            "csrf_token": csrf,
            "guild_id": settings.DISCORD_GUILD_ID,
        })

    @app.get("/{path:path}", response_class=HTMLResponse)
    async def catch_all(request: Request, path: str):
        """Catch-all route for SPA navigation."""
        # Don't catch API, static, assets or health routes
        if path.startswith("api/") or path.startswith("static/") or path.startswith("assets/") or path == "health":
            return JSONResponse({"error": "Not found"}, status_code=404)

        if not check_ip_allowlist(request):
            return HTMLResponse("Access denied", status_code=403)

        if (WEB_DIST_DIR / "index.html").exists():
            return FileResponse(WEB_DIST_DIR / "index.html")

        user = require_auth_redirect(request)
        if not user:
            return RedirectResponse(url="/login", status_code=302)

        csrf = generate_csrf_token(request.cookies.get("pbhero_session", ""))
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "username": user,
            "csrf_token": csrf,
            "guild_id": settings.DISCORD_GUILD_ID,
        })

    return app
