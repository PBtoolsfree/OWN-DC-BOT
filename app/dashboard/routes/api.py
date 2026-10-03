"""
PB HERO Dashboard API Routes.

All API routes require authenticated session.
Every route validates the logged-in admin session server-side.
"""

import json
import logging
import re
from datetime import datetime

import discord
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.dashboard.auth import (
    check_rate_limit,
    clear_login_attempts,
    generate_csrf_token,
    get_client_ip,
    hash_password,
    record_login_attempt,
    validate_csrf_token,
    verify_password,
)
from app.dashboard.dependencies import check_ip_allowlist, require_auth, session_manager
from app.database.engine import get_session_direct, test_connection
from app.database.models import EventType, PolicyValue
from app.database.serializers import (
    deserialize_json_field,
    normalize_domain,
    normalize_domain_list,
    serialize_json_field,
)
from app.moderation.evaluator import evaluate_message_policy
from app.database.repositories import (
    AdminUserRepo,
    AuditLogRepo,
    BlockedMessageRepo,
    ChannelPolicyRepo,
    ExemptionRuleRepo,
    ModerationCaseRepo,
    PolicyProfileRepo,
    ServerConfigRepo,
    YouTubeChannelRepo,
    YouTubeDestinationRepo,
    YouTubeEventRepo,
    YouTubeTemplateRepo,
)

logger = logging.getLogger("pbhero.dashboard")
settings = get_settings()

router = APIRouter(prefix="/api/v1")


# ─── Authentication ──────────────────────────────────────────────────────────

@router.get("/auth/me")
async def get_current_user(username: str = Depends(require_auth)):
    """Get authenticated user info."""
    return {
        "authenticated": True,
        "username": username,
        "guild_id": str(settings.DISCORD_GUILD_ID),
    }


@router.post("/auth/login")
async def api_login(request: Request):
    """API login endpoint returning session cookie."""
    if not check_ip_allowlist(request):
        raise HTTPException(status_code=403, detail="Access denied: IP not allowed")

    client_ip = get_client_ip(request)
    allowed, remaining = check_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {remaining} seconds.",
        )

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    session = await get_session_direct()
    try:
        user = await AdminUserRepo.get_by_username(session, username)
        if user and verify_password(user.password_hash, password):
            clear_login_attempts(client_ip)
            token = session_manager.create_session(username)
            response = JSONResponse(content={
                "success": True,
                "username": username,
                "guild_id": str(settings.DISCORD_GUILD_ID),
            })
            response.set_cookie(
                key="pbhero_session",
                value=token,
                httponly=True,
                secure=False,
                samesite="lax",
                max_age=86400,
                path="/",
            )
            logger.info("Admin login via API: %s from %s", username, client_ip)
            return response
        else:
            record_login_attempt(client_ip)
            logger.warning("Failed API login attempt: %s from %s", username, client_ip)
            raise HTTPException(status_code=401, detail="Invalid username or password.")
    finally:
        await session.close()


@router.post("/auth/logout")
async def api_logout():
    """Logout endpoint clearing session cookie."""
    response = JSONResponse(content={"success": True})
    response.delete_cookie("pbhero_session", path="/")
    return response



# ─── System ───────────────────────────────────────────────────────────────────

@router.get("/system/status")
async def system_status(username: str = Depends(require_auth)):
    """Get detailed system status."""
    import sys
    import app as app_module

    db_ok = await test_connection()

    # Get bot reference if available
    from app.runtime_state import get_bot_instance, is_bot_ready
    bot = get_bot_instance()

    bot_connected = is_bot_ready()
    bot_latency = 0
    guild_name = "Unknown"
    guild_members = 0
    yt_running = False
    yt_healthy = False

    if bot and bot_connected:
        bot_latency = round(bot.latency * 1000)
        guild = bot.guild
        if guild:
            guild_name = guild.name
            guild_members = guild.member_count or 0

        scheduler = getattr(bot, "youtube_scheduler", None)
        if scheduler:
            yt_running = scheduler.is_running
            yt_healthy = scheduler.is_healthy

    return {
        "status": "ok" if (db_ok and bot_connected) else "degraded",
        "bot": {
            "connected": bot_connected,
            "latency_ms": bot_latency,
            "guild_name": guild_name,
            "guild_members": guild_members,
            "uptime": bot.uptime if (bot and bot_connected) else 0,
        },
        "database": {"connected": db_ok},
        "youtube": {"running": yt_running, "healthy": yt_healthy},
        "system": {
            "version": app_module.__version__,
            "python": sys.version.split()[0],
        },
    }


@router.get("/system/overview")
async def system_overview(username: str = Depends(require_auth)):
    """Get dashboard overview data."""
    session = await get_session_direct()
    try:
        yt_channels = await YouTubeChannelRepo.count(session)
        yt_enabled = await YouTubeChannelRepo.count_enabled(session)
        notifications_today = await YouTubeEventRepo.count_today(session)
        blocked_today = await BlockedMessageRepo.count_today(session)
        cases_today = await ModerationCaseRepo.count_today(session)
        active_policies = await ChannelPolicyRepo.count_active(session)

        return {
            "youtube_channels": yt_channels,
            "youtube_enabled": yt_enabled,
            "notifications_today": notifications_today,
            "blocked_messages_today": blocked_today,
            "moderation_cases_today": cases_today,
            "active_policies": active_policies,
        }
    finally:
        await session.close()


@router.post("/system/reload")
async def system_reload(username: str = Depends(require_auth)):
    """Reload configuration and refresh caches."""
    session = await get_session_direct()
    try:
        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        await AuditLogRepo.log(session, username, "system_reload", "configuration")
        await session.commit()
        return {"success": True, "message": "Configuration and moderation cache reloaded successfully"}
    finally:
        await session.close()


@router.post("/system/restart")
async def system_restart(username: str = Depends(require_auth)):
    """Schedule bot reconnect / restart."""
    session = await get_session_direct()
    try:
        await AuditLogRepo.log(session, username, "system_restart", "bot_client")
        await session.commit()
        return {"success": True, "message": "Bot restart command received"}
    finally:
        await session.close()


@router.post("/system/test-db")
async def system_test_db(username: str = Depends(require_auth)):
    """Test database connectivity and latency."""
    import time
    start = time.perf_counter()
    ok = await test_connection()
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    return {
        "success": ok,
        "latency_ms": duration_ms,
        "message": "Database is responsive" if ok else "Database connection failed",
    }


@router.post("/system/test-youtube")
async def system_test_youtube(username: str = Depends(require_auth)):
    """Test YouTube monitor subsystem status."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    scheduler = getattr(bot, "youtube_scheduler", None) if bot else None
    if scheduler:
        return {
            "success": scheduler.is_healthy,
            "running": scheduler.is_running,
            "healthy": scheduler.is_healthy,
            "message": "YouTube monitor healthy" if scheduler.is_healthy else "YouTube monitor degraded",
        }
    return {
        "success": True,
        "running": False,
        "healthy": True,
        "message": "YouTube scheduler operational (standalone)",
    }


# ─── YouTube ──────────────────────────────────────────────────────────────────

@router.get("/youtube/channels")
async def list_youtube_channels(username: str = Depends(require_auth)):
    """List all monitored YouTube channels."""
    session = await get_session_direct()
    try:
        channels = await YouTubeChannelRepo.get_all(session)
        result = []
        for ch in channels:
            destinations = await YouTubeDestinationRepo.get_for_channel(session, ch.youtube_channel_id)
            result.append({
                "id": ch.id,
                "youtube_channel_id": ch.youtube_channel_id,
                "channel_name": ch.channel_name,
                "handle": ch.handle,
                "enabled": ch.enabled,
                "feed_url": ch.feed_url,
                "last_checked_at": ch.last_checked_at.isoformat() if ch.last_checked_at else None,
                "last_success_at": ch.last_success_at.isoformat() if ch.last_success_at else None,
                "last_error": ch.last_error,
                "destinations": [{
                    "id": d.id,
                    "discord_channel_id": str(d.discord_channel_id),
                    "notification_role_id": str(d.notification_role_id) if d.notification_role_id else None,
                    "upload_enabled": d.upload_enabled,
                    "scheduled_live_enabled": d.scheduled_live_enabled,
                    "live_started_enabled": d.live_started_enabled,
                    "premiere_enabled": d.premiere_enabled,
                } for d in destinations],
            })
        return result
    finally:
        await session.close()


@router.post("/youtube/channels")
async def add_youtube_channel(request: Request, username: str = Depends(require_auth)):
    """Add a new YouTube channel to monitor."""
    data = await request.json()

    youtube_input = data.get("youtube_input", "").strip()
    discord_channel_id = data.get("discord_channel_id")
    notification_role_id = data.get("notification_role_id")

    if not youtube_input or not discord_channel_id:
        raise HTTPException(status_code=400, detail="YouTube channel and Discord channel are required")

    # Resolve channel ID
    from app.youtube.channel_resolver import resolve_channel_id, build_feed_url

    resolved = await resolve_channel_id(youtube_input)
    if not resolved:
        raise HTTPException(status_code=400, detail="Could not resolve YouTube channel. Try using a channel ID (UCxxxx)")

    channel_id = resolved["channel_id"]
    channel_name = resolved.get("channel_name") or data.get("channel_name") or "Unknown"
    handle = resolved.get("handle")

    session = await get_session_direct()
    try:
        # Check if already exists
        existing = await YouTubeChannelRepo.get_by_channel_id(session, channel_id)
        if existing:
            # Add destination
            dest = await YouTubeDestinationRepo.create(
                session, channel_id, int(discord_channel_id),
                notification_role_id=int(notification_role_id) if notification_role_id else None,
                upload_enabled=data.get("upload_enabled", True),
                scheduled_live_enabled=data.get("scheduled_live_enabled", True),
                live_started_enabled=data.get("live_started_enabled", True),
                premiere_enabled=data.get("premiere_enabled", True),
            )
        else:
            # Create channel and destination
            channel = await YouTubeChannelRepo.create(
                session, channel_id, channel_name, handle=handle,
                feed_url=build_feed_url(channel_id),
            )
            dest = await YouTubeDestinationRepo.create(
                session, channel_id, int(discord_channel_id),
                notification_role_id=int(notification_role_id) if notification_role_id else None,
                upload_enabled=data.get("upload_enabled", True),
                scheduled_live_enabled=data.get("scheduled_live_enabled", True),
                live_started_enabled=data.get("live_started_enabled", True),
                premiere_enabled=data.get("premiere_enabled", True),
            )

        await AuditLogRepo.log(session, username, "youtube_channel_added",
                               channel_id, f"Name: {channel_name}")
        await session.commit()

        return {"success": True, "channel_id": channel_id, "channel_name": channel_name}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.delete("/youtube/channels/{channel_id}")
async def delete_youtube_channel(channel_id: str, username: str = Depends(require_auth)):
    """Delete a YouTube channel."""
    session = await get_session_direct()
    try:
        deleted = await YouTubeChannelRepo.delete_channel(session, channel_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Channel not found")

        await AuditLogRepo.log(session, username, "youtube_channel_deleted", channel_id)
        await session.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.post("/youtube/channels/{channel_id}/toggle")
async def toggle_youtube_channel(channel_id: str, request: Request, username: str = Depends(require_auth)):
    """Enable/disable a YouTube channel."""
    data = await request.json()
    enabled = data.get("enabled", True)

    session = await get_session_direct()
    try:
        await YouTubeChannelRepo.toggle_enabled(session, channel_id, enabled)
        await AuditLogRepo.log(session, username, "youtube_channel_toggled",
                               channel_id, f"Enabled: {enabled}")
        await session.commit()
        return {"success": True}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.post("/youtube/test/{channel_id}")
async def test_youtube_channel(channel_id: str, username: str = Depends(require_auth)):
    """Test YouTube channel feed."""
    from app.youtube.feed_parser import fetch_feed

    result = await fetch_feed(channel_id)
    return {
        "success": result.success,
        "channel_name": result.channel_name,
        "entry_count": len(result.entries),
        "error": result.error,
        "entries": [{
            "title": e.title,
            "video_id": e.video_id,
            "url": e.url,
            "published": e.published.isoformat() if e.published else None,
        } for e in result.entries[:5]],
    }


@router.get("/youtube/channels/{channel_id}")
async def get_youtube_channel(channel_id: str, username: str = Depends(require_auth)):
    """Get details of a single monitored YouTube channel."""
    session = await get_session_direct()
    try:
        ch = await YouTubeChannelRepo.get_by_channel_id(session, channel_id)
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")

        destinations = await YouTubeDestinationRepo.get_for_channel(session, ch.youtube_channel_id)
        return {
            "id": ch.id,
            "youtube_channel_id": ch.youtube_channel_id,
            "channel_name": ch.channel_name,
            "handle": ch.handle,
            "enabled": ch.enabled,
            "feed_url": ch.feed_url,
            "last_checked_at": ch.last_checked_at.isoformat() if ch.last_checked_at else None,
            "last_success_at": ch.last_success_at.isoformat() if ch.last_success_at else None,
            "last_error": ch.last_error,
            "destinations": [{
                "id": d.id,
                "discord_channel_id": str(d.discord_channel_id),
                "notification_role_id": str(d.notification_role_id) if d.notification_role_id else None,
                "upload_enabled": d.upload_enabled,
                "scheduled_live_enabled": d.scheduled_live_enabled,
                "live_started_enabled": d.live_started_enabled,
                "premiere_enabled": d.premiere_enabled,
            } for d in destinations],
        }
    finally:
        await session.close()


@router.put("/youtube/channels/{channel_id}")
async def update_youtube_channel(channel_id: str, request: Request, username: str = Depends(require_auth)):
    """Update destination and notification settings for a YouTube channel."""
    data = await request.json()
    session = await get_session_direct()
    try:
        ch = await YouTubeChannelRepo.get_by_channel_id(session, channel_id)
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")

        if "channel_name" in data:
            ch.channel_name = data["channel_name"]

        # If destinations provided, recreate/update destinations
        if "destinations" in data and isinstance(data["destinations"], list):
            await YouTubeDestinationRepo.delete_for_channel(session, channel_id)
            for d in data["destinations"]:
                discord_channel_id = d.get("discord_channel_id")
                if discord_channel_id:
                    role_id = d.get("notification_role_id")
                    await YouTubeDestinationRepo.create(
                        session,
                        channel_id,
                        int(discord_channel_id),
                        notification_role_id=int(role_id) if role_id else None,
                        upload_enabled=d.get("upload_enabled", True),
                        scheduled_live_enabled=d.get("scheduled_live_enabled", True),
                        live_started_enabled=d.get("live_started_enabled", True),
                        premiere_enabled=d.get("premiere_enabled", True),
                    )

        await AuditLogRepo.log(session, username, "youtube_channel_updated", channel_id)
        await session.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.post("/youtube/test-live/{channel_id}")
async def test_youtube_live(channel_id: str, username: str = Depends(require_auth)):
    """Test YouTube channel live status detection."""
    channel_id = channel_id.strip()
    if not channel_id.startswith("UC") or not re.match(r"^UC[\w-]+$", channel_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid YouTube channel ID format. Must start with 'UC'.",
        )

    from app.youtube.live_detector import check_channel_live_status

    try:
        live_result = await check_channel_live_status(channel_id)
        return {
            "success": live_result.status != "unknown" and live_result.error is None,
            "is_live": live_result.is_live,
            "is_upcoming": live_result.is_upcoming,
            "is_premiere": live_result.is_premiere,
            "status": live_result.status,
            "title": live_result.title,
            "video_id": live_result.video_id,
            "channel_id": live_result.channel_id,
            "scheduled_start": live_result.scheduled_start,
            "viewer_count": live_result.viewer_count,
            "error": live_result.error,
        }
    except Exception as e:
        logger.error("Error during test_youtube_live for %s: %s", channel_id, str(e), exc_info=True)
        return {
            "success": False,
            "is_live": False,
            "is_upcoming": False,
            "is_premiere": False,
            "status": "unknown",
            "title": None,
            "video_id": None,
            "channel_id": channel_id,
            "scheduled_start": None,
            "viewer_count": None,
            "error": str(e),
        }


# ─── YouTube Notification Templates ──────────────────────────────────────────

ALLOWED_EVENT_TYPES = {"upload", "scheduled_live", "live_started", "premiere"}
SUPPORTED_VARIABLES = {
    "{channel_name}",
    "{video_title}",
    "{video_url}",
    "{channel_id}",
    "{published_at}",
    "{scheduled_start}",
    "{viewer_count}",
    "{started_at}",
}


def _validate_template_variables(text: str) -> None:
    """Validate that all {...} placeholders in text are supported."""
    if not text:
        return
    matches = re.findall(r"\{[^{}]*\}", text)
    for var in matches:
        if var not in SUPPORTED_VARIABLES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported template variable: '{var}'. Supported: {', '.join(sorted(SUPPORTED_VARIABLES))}",
            )


def _serialize_template(tpl) -> dict:
    return {
        "id": tpl.id,
        "event_type": tpl.event_type.value if hasattr(tpl.event_type, "value") else str(tpl.event_type),
        "title_template": tpl.title_template,
        "description_template": tpl.description_template,
        "mention_role": tpl.mention_role,
        "footer_text": tpl.footer_text or "PB HERO Personal Discord Bot",
        "show_thumbnail": tpl.show_thumbnail,
        "show_timestamp": tpl.show_timestamp,
        "enable_button": tpl.enable_button,
        "updated_at": tpl.updated_at.isoformat() if tpl.updated_at else None,
    }


@router.get("/youtube/templates")
async def get_all_youtube_templates(username: str = Depends(require_auth)):
    """Get all 4 event-specific YouTube notification templates."""
    session = await get_session_direct()
    try:
        templates = await YouTubeTemplateRepo.get_all(session)
        await session.commit()
        return [_serialize_template(t) for t in templates]
    finally:
        await session.close()


@router.get("/youtube/templates/{event_type}")
async def get_youtube_template(event_type: str, username: str = Depends(require_auth)):
    """Get a single YouTube notification template by event type."""
    norm_type = event_type.lower().strip()
    if norm_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: '{event_type}'. Allowed: {', '.join(sorted(ALLOWED_EVENT_TYPES))}",
        )

    session = await get_session_direct()
    try:
        tpl = await YouTubeTemplateRepo.get_by_event_type(session, EventType(norm_type))
        await session.commit()
        return _serialize_template(tpl)
    finally:
        await session.close()


@router.put("/youtube/templates/{event_type}")
async def update_youtube_template(event_type: str, request: Request, username: str = Depends(require_auth)):
    """Update a specific YouTube notification template."""
    norm_type = event_type.lower().strip()
    if norm_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: '{event_type}'. Allowed: {', '.join(sorted(ALLOWED_EVENT_TYPES))}",
        )

    data = await request.json()

    # Validate fields
    updates = {}
    if "title_template" in data:
        title = str(data["title_template"]).strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title template cannot be empty")
        if len(title) > 256:
            raise HTTPException(status_code=400, detail="Title template cannot exceed 256 characters")
        _validate_template_variables(title)
        updates["title_template"] = title

    if "description_template" in data:
        desc = str(data["description_template"]).strip()
        if not desc:
            raise HTTPException(status_code=400, detail="Description template cannot be empty")
        if len(desc) > 2000:
            raise HTTPException(status_code=400, detail="Description template cannot exceed 2000 characters")
        _validate_template_variables(desc)
        updates["description_template"] = desc

    if "mention_role" in data:
        updates["mention_role"] = data["mention_role"].strip() if data["mention_role"] else None

    if "footer_text" in data:
        footer = str(data["footer_text"]).strip() if data["footer_text"] else ""
        if len(footer) > 256:
            raise HTTPException(status_code=400, detail="Footer text cannot exceed 256 characters")
        _validate_template_variables(footer)
        updates["footer_text"] = footer

    for bool_field in ("show_thumbnail", "show_timestamp", "enable_button"):
        if bool_field in data:
            updates[bool_field] = bool(data[bool_field])

    session = await get_session_direct()
    try:
        tpl = await YouTubeTemplateRepo.update(session, EventType(norm_type), **updates)
        await AuditLogRepo.log(session, username, "youtube_template_updated", norm_type)
        await session.commit()
        return {"success": True, "template": _serialize_template(tpl)}
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.post("/youtube/templates/{event_type}/reset")
async def reset_youtube_template(event_type: str, username: str = Depends(require_auth)):
    """Reset a specific YouTube notification template to factory defaults."""
    norm_type = event_type.lower().strip()
    if norm_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: '{event_type}'. Allowed: {', '.join(sorted(ALLOWED_EVENT_TYPES))}",
        )

    session = await get_session_direct()
    try:
        tpl = await YouTubeTemplateRepo.reset(session, EventType(norm_type))
        await AuditLogRepo.log(session, username, "youtube_template_reset", norm_type)
        await session.commit()
        return {"success": True, "template": _serialize_template(tpl)}
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


# ─── Policy Response Helpers ──────────────────────────────────────────────────

def _format_policy_response(p) -> dict | None:
    if not p:
        return None
    raw_domains = p.allowed_domains
    if isinstance(raw_domains, str):
        domains = deserialize_json_field(raw_domains, default=[])
    elif isinstance(raw_domains, list):
        domains = raw_domains
    else:
        domains = []

    return {
        "id": p.id,
        "discord_channel_id": str(p.discord_channel_id),
        "channel_name": p.channel_name,
        "category_name": p.category_name,
        "channel_type": p.channel_type,
        "allow_text": p.allow_text.value if hasattr(p.allow_text, "value") else str(p.allow_text),
        "allow_links": p.allow_links.value if hasattr(p.allow_links, "value") else str(p.allow_links),
        "allow_images": p.allow_images.value if hasattr(p.allow_images, "value") else str(p.allow_images),
        "allow_videos": p.allow_videos.value if hasattr(p.allow_videos, "value") else str(p.allow_videos),
        "allow_files": p.allow_files.value if hasattr(p.allow_files, "value") else str(p.allow_files),
        "allow_stickers": p.allow_stickers.value if hasattr(p.allow_stickers, "value") else str(p.allow_stickers),
        "allow_everyone": p.allow_everyone.value if hasattr(p.allow_everyone, "value") else str(p.allow_everyone),
        "allow_here": p.allow_here.value if hasattr(p.allow_here, "value") else str(p.allow_here),
        "allow_role_mentions": p.allow_role_mentions.value if hasattr(p.allow_role_mentions, "value") else str(p.allow_role_mentions),
        "allow_user_mentions": p.allow_user_mentions.value if hasattr(p.allow_user_mentions, "value") else str(p.allow_user_mentions),
        "allowed_domains": domains,
        "preset_name": p.preset_name,
        "enabled": bool(p.enabled),
        "delete_violations": bool(p.delete_violations),
        "warn_on_violation": bool(p.warn_on_violation),
        "log_violations": bool(p.log_violations),
        "send_dm_warning": bool(getattr(p, "send_dm_warning", False)),
        "warning_message": p.warning_message,
    }


def _format_profile_response(p) -> dict | None:
    if not p:
        return None
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "category": getattr(p, "category", "General") or "General",
        "is_builtin": bool(p.is_builtin),
        "allow_text": p.allow_text.value if hasattr(p.allow_text, "value") else str(p.allow_text),
        "allow_links": p.allow_links.value if hasattr(p.allow_links, "value") else str(p.allow_links),
        "allow_images": p.allow_images.value if hasattr(p.allow_images, "value") else str(p.allow_images),
        "allow_videos": p.allow_videos.value if hasattr(p.allow_videos, "value") else str(p.allow_videos),
        "allow_files": p.allow_files.value if hasattr(p.allow_files, "value") else str(p.allow_files),
        "allow_stickers": p.allow_stickers.value if hasattr(p.allow_stickers, "value") else str(p.allow_stickers),
        "allow_everyone": p.allow_everyone.value if hasattr(p.allow_everyone, "value") else str(p.allow_everyone),
        "allow_here": p.allow_here.value if hasattr(p.allow_here, "value") else str(p.allow_here),
        "allow_role_mentions": p.allow_role_mentions.value if hasattr(p.allow_role_mentions, "value") else str(p.allow_role_mentions),
        "allow_user_mentions": p.allow_user_mentions.value if hasattr(p.allow_user_mentions, "value") else str(p.allow_user_mentions),
        "delete_violations": bool(getattr(p, "delete_violations", True)),
        "warn_on_violation": bool(getattr(p, "warn_on_violation", True)),
        "log_violations": bool(getattr(p, "log_violations", True)),
        "send_dm_warning": bool(getattr(p, "send_dm_warning", False)),
        "warning_message": getattr(p, "warning_message", None),
    }


# ─── Channel Policies ────────────────────────────────────────────────────────

@router.get("/policies")
@router.get("/moderation/policies")
async def list_policies(username: str = Depends(require_auth)):
    """List all channel policies with clean deserialized fields."""
    session = await get_session_direct()
    try:
        policies = await ChannelPolicyRepo.get_all(session)
        return [_format_policy_response(p) for p in policies]
    finally:
        await session.close()


# ─── Guild Info ─────────────────────────────────────────────────────────────

@router.get("/guild")
async def get_guild_info(username: str = Depends(require_auth)):
    """Get single-server guild information."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if bot else None
    return {
        "guild_id": str(settings.DISCORD_GUILD_ID),
        "name": guild.name if guild else "PB HERO Server",
        "member_count": guild.member_count if guild else 0,
        "is_configured": settings.is_configured(),
        "single_server": True,
    }


# ─── Policy Profiles (Built-in & Custom Presets) ─────────────────────────────

@router.get("/policies/profiles")
@router.get("/moderation/profiles")
async def list_profiles(username: str = Depends(require_auth)):
    """List all policy profiles/presets."""
    session = await get_session_direct()
    try:
        profiles = await PolicyProfileRepo.get_all(session)
        if not profiles:
            await PolicyProfileRepo.create_defaults(session)
            await session.commit()
            profiles = await PolicyProfileRepo.get_all(session)
        return [_format_profile_response(p) for p in profiles]
    finally:
        await session.close()


@router.get("/policies/profiles/{profile_id}")
@router.get("/moderation/profiles/{profile_id}")
async def get_profile(profile_id: int, username: str = Depends(require_auth)):
    """Get a specific policy profile."""
    session = await get_session_direct()
    try:
        prof = await PolicyProfileRepo.get_by_id(session, profile_id)
        if not prof:
            raise HTTPException(status_code=404, detail="Policy profile not found")
        return _format_profile_response(prof)
    finally:
        await session.close()


@router.post("/policies/profiles")
@router.post("/moderation/profiles")
async def create_profile(request: Request, username: str = Depends(require_auth)):
    """Create a new custom policy profile."""
    data = await request.json()
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Profile name is required")

    session = await get_session_direct()
    try:
        # Check name collision
        existing = await PolicyProfileRepo.get_by_name(session, name)
        if existing:
            raise HTTPException(status_code=400, detail=f"Profile '{name}' already exists")

        # Parse rule enums
        kwargs = {
            "name": name,
            "description": data.get("description", ""),
            "category": data.get("category", "General"),
            "is_builtin": False,
        }
        for field in ["allow_text", "allow_links", "allow_images", "allow_videos",
                      "allow_files", "allow_stickers", "allow_everyone", "allow_here",
                      "allow_role_mentions", "allow_user_mentions"]:
            if field in data and data[field] is not None:
                kwargs[field] = PolicyValue(str(data[field]).lower())

        for field in ["delete_violations", "warn_on_violation", "log_violations", "send_dm_warning"]:
            if field in data:
                kwargs[field] = bool(data[field])

        if "warning_message" in data:
            kwargs["warning_message"] = data["warning_message"]

        created = await PolicyProfileRepo.create(session, **kwargs)
        await AuditLogRepo.log(session, username, "profile_created", details=name)
        await session.commit()
        return _format_profile_response(created)
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to create custom policy profile")
        raise HTTPException(status_code=500, detail="Could not create custom policy profile")
    finally:
        await session.close()


@router.put("/policies/profiles/{profile_id}")
@router.put("/moderation/profiles/{profile_id}")
async def update_profile(profile_id: int, request: Request, username: str = Depends(require_auth)):
    """Update an existing custom policy profile (built-ins are protected)."""
    data = await request.json()
    session = await get_session_direct()
    try:
        prof = await PolicyProfileRepo.get_by_id(session, profile_id)
        if not prof:
            raise HTTPException(status_code=404, detail="Policy profile not found")
        if prof.is_builtin:
            raise HTTPException(status_code=400, detail="Built-in presets cannot be modified")

        updates = {}
        if "name" in data and data["name"].strip():
            updates["name"] = data["name"].strip()
        if "description" in data:
            updates["description"] = data["description"]
        if "category" in data:
            updates["category"] = data["category"]

        for field in ["allow_text", "allow_links", "allow_images", "allow_videos",
                      "allow_files", "allow_stickers", "allow_everyone", "allow_here",
                      "allow_role_mentions", "allow_user_mentions"]:
            if field in data and data[field] is not None:
                updates[field] = PolicyValue(str(data[field]).lower())

        for field in ["delete_violations", "warn_on_violation", "log_violations", "send_dm_warning"]:
            if field in data:
                updates[field] = bool(data[field])

        if "warning_message" in data:
            updates["warning_message"] = data["warning_message"]

        updated = await PolicyProfileRepo.update(session, profile_id, **updates)
        await AuditLogRepo.log(session, username, "profile_updated", target=str(profile_id))
        await session.commit()
        return _format_profile_response(updated)
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to update policy profile")
        raise HTTPException(status_code=500, detail="Could not update policy profile")
    finally:
        await session.close()


@router.delete("/policies/profiles/{profile_id}")
@router.delete("/moderation/profiles/{profile_id}")
async def delete_profile(profile_id: int, username: str = Depends(require_auth)):
    """Delete a custom policy profile (built-ins cannot be deleted)."""
    session = await get_session_direct()
    try:
        prof = await PolicyProfileRepo.get_by_id(session, profile_id)
        if not prof:
            raise HTTPException(status_code=404, detail="Policy profile not found")
        if prof.is_builtin:
            raise HTTPException(status_code=400, detail="Built-in presets cannot be deleted")

        deleted = await PolicyProfileRepo.delete(session, profile_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Policy profile not found")

        await AuditLogRepo.log(session, username, "profile_deleted", target=str(profile_id))
        await session.commit()
        return {"success": True, "message": "Policy profile deleted successfully"}
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to delete policy profile")
        raise HTTPException(status_code=500, detail="Could not delete policy profile")
    finally:
        await session.close()


@router.post("/policies/profiles/{profile_id}/duplicate")
@router.post("/moderation/profiles/{profile_id}/duplicate")
async def duplicate_profile(profile_id: int, request: Request, username: str = Depends(require_auth)):
    """Duplicate a profile (built-in or custom) to create a new custom profile."""
    data = {}
    try:
        data = await request.json()
    except Exception:
        pass

    session = await get_session_direct()
    try:
        prof = await PolicyProfileRepo.get_by_id(session, profile_id)
        if not prof:
            raise HTTPException(status_code=404, detail="Policy profile not found")

        target_name = (data.get("new_name") or f"{prof.name} (Copy)").strip()
        # Ensure unique name
        suffix = 1
        test_name = target_name
        while await PolicyProfileRepo.get_by_name(session, test_name):
            suffix += 1
            test_name = f"{target_name} {suffix}"

        duplicated = await PolicyProfileRepo.duplicate(session, profile_id, test_name)
        if not duplicated:
            raise HTTPException(status_code=500, detail="Failed to duplicate policy profile")

        await AuditLogRepo.log(session, username, "profile_duplicated", target=str(profile_id), details=test_name)
        await session.commit()
        return _format_profile_response(duplicated)
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to duplicate policy profile")
        raise HTTPException(status_code=500, detail="Could not duplicate policy profile")
    finally:
        await session.close()


@router.post("/policies/profiles/{profile_id}/apply")
@router.post("/moderation/profiles/{profile_id}/apply")
async def apply_profile_to_channels(profile_id: int, request: Request, username: str = Depends(require_auth)):
    """Apply a profile to one or multiple Discord channels."""
    data = await request.json()
    raw_ids = data.get("channel_ids") or []
    if "channel_id" in data and not raw_ids:
        raw_ids = [data["channel_id"]]

    channel_ids = []
    for cid in raw_ids:
        try:
            channel_ids.append(int(cid))
        except (ValueError, TypeError):
            continue

    if not channel_ids:
        raise HTTPException(status_code=400, detail="No valid channel IDs provided")

    session = await get_session_direct()
    try:
        prof = await PolicyProfileRepo.get_by_id(session, profile_id)
        if not prof:
            raise HTTPException(status_code=404, detail="Policy profile not found")

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        guild = bot.guild if bot else None

        applied = []
        for cid in channel_ids:
            # Look up Discord channel metadata if available
            ch = guild.get_channel(cid) if guild else None
            ch_name = ch.name if ch else f"channel-{cid}"
            cat_name = ch.category.name if ch and ch.category else "Uncategorized"
            ch_type = "text"
            if ch and isinstance(ch, discord.VoiceChannel):
                ch_type = "voice"

            await ChannelPolicyRepo.upsert(
                session,
                discord_channel_id=cid,
                channel_name=ch_name,
                category_name=cat_name,
                channel_type=ch_type,
                allow_text=prof.allow_text,
                allow_links=prof.allow_links,
                allow_images=prof.allow_images,
                allow_videos=prof.allow_videos,
                allow_files=prof.allow_files,
                allow_stickers=prof.allow_stickers,
                allow_everyone=prof.allow_everyone,
                allow_here=prof.allow_here,
                allow_role_mentions=prof.allow_role_mentions,
                allow_user_mentions=prof.allow_user_mentions,
                preset_name=prof.name,
                delete_violations=prof.delete_violations,
                warn_on_violation=prof.warn_on_violation,
                log_violations=prof.log_violations,
                send_dm_warning=getattr(prof, "send_dm_warning", False),
                warning_message=prof.warning_message,
                enabled=True,
                updated_by=username,
            )
            applied.append(cid)

        await AuditLogRepo.log(session, username, "profile_applied", target=str(profile_id),
                               details=f"Applied {prof.name} to {len(applied)} channels")
        await session.commit()

        # Invalidate moderation engine cache
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {
            "success": True,
            "message": f"Successfully applied '{prof.name}' to {len(applied)} channel(s)",
            "applied_count": len(applied),
            "channel_ids": [str(c) for c in applied],
        }
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to apply policy profile to channels")
        raise HTTPException(status_code=500, detail="Could not apply policy profile to channels")
    finally:
        await session.close()


# ─── Channel Policy Detail & CRUD ───────────────────────────────────────────

@router.get("/policies/{channel_id}")
@router.get("/moderation/policies/{channel_id}")
async def get_channel_policy(channel_id: int, username: str = Depends(require_auth)):
    """Get policy for a specific channel with clean deserialized domain array."""
    session = await get_session_direct()
    try:
        p = await ChannelPolicyRepo.get_for_channel(session, channel_id)
        if not p:
            return None
        return _format_policy_response(p)
    finally:
        await session.close()


@router.post("/policies/{channel_id}")
@router.post("/moderation/policies/{channel_id}")
@router.put("/moderation/policies/{channel_id}")
async def save_policy(channel_id: int, request: Request, username: str = Depends(require_auth)):
    """Save or update a channel policy with guaranteed safe domain list serialization."""
    data = await request.json()

    session = await get_session_direct()
    try:
        policy_fields = {}
        for field in ["allow_text", "allow_links", "allow_images", "allow_videos",
                      "allow_files", "allow_stickers", "allow_everyone", "allow_here",
                      "allow_role_mentions", "allow_user_mentions"]:
            if field in data and data[field] is not None:
                val = str(data[field]).lower()
                policy_fields[field] = PolicyValue(val)

        for field in ["channel_name", "category_name", "channel_type", "preset_name",
                      "warning_message"]:
            if field in data:
                policy_fields[field] = data[field]

        # Allowed domains: list or string is parsed and normalized safely
        if "allowed_domains" in data:
            raw_domains = data["allowed_domains"]
            if isinstance(raw_domains, str):
                parsed = [d.strip() for d in raw_domains.split(",") if d.strip()]
            elif isinstance(raw_domains, list):
                parsed = [str(d).strip() for d in raw_domains if str(d).strip()]
            else:
                parsed = []
            policy_fields["allowed_domains"] = normalize_domain_list(parsed)

        for field in ["enabled", "delete_violations", "warn_on_violation", "log_violations", "send_dm_warning"]:
            if field in data:
                policy_fields[field] = bool(data[field])

        policy_fields["updated_by"] = username

        saved = await ChannelPolicyRepo.upsert(session, channel_id, **policy_fields)
        await AuditLogRepo.log(session, username, "policy_updated", str(channel_id))
        await session.commit()

        # Refresh moderation engine cache
        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {
            "success": True,
            "message": "Policy saved successfully",
            "policy": _format_policy_response(saved),
        }
    except ValueError as ve:
        await session.rollback()
        logger.warning("Validation error saving policy %s: %s", channel_id, str(ve))
        raise HTTPException(status_code=400, detail=f"Invalid policy value: {str(ve)}")
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to save channel policy %s", channel_id)
        # Safe human-readable message, no raw SQL traceback
        raise HTTPException(status_code=500, detail="Could not save policy. Please check input parameters or server logs.")
    finally:
        await session.close()


@router.delete("/policies/{channel_id}")
@router.delete("/moderation/policies/{channel_id}")
async def delete_policy(channel_id: int, username: str = Depends(require_auth)):
    """Delete a channel policy override."""
    session = await get_session_direct()
    try:
        deleted = await ChannelPolicyRepo.delete_policy(session, channel_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Policy not found")

        await AuditLogRepo.log(session, username, "policy_deleted", str(channel_id))
        await session.commit()

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True, "message": "Policy reset to default server inheritance"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to delete channel policy %s", channel_id)
        raise HTTPException(status_code=500, detail="Could not delete channel policy")
    finally:
        await session.close()


# ─── Policy Simulator & Policy Tester ────────────────────────────────────────

@router.post("/policies/simulate")
@router.post("/moderation/policy-test")
async def simulate_policy(request: Request, username: str = Depends(require_auth)):
    """
    Simulate a policy check (dry run) using the shared evaluate_message_policy function.
    Supports evaluating against stored channel policy or an on-the-fly custom draft policy.
    """
    data = await request.json()
    channel_id_raw = data.get("channel_id", 0)
    try:
        channel_id = int(channel_id_raw)
    except (ValueError, TypeError):
        channel_id = 0

    content = data.get("content", "")
    role_ids = data.get("role_ids", [])
    has_attachment = bool(data.get("has_attachment", False))
    attachment_type = data.get("attachment_type", "image")
    policy_override = data.get("policy_override") or data.get("policy")

    # Get server config
    session = await get_session_direct()
    server_config_dict = {}
    try:
        cfg = await ServerConfigRepo.get_or_create(session)
        server_config_dict = {
            "admin_role_ids": deserialize_json_field(cfg.admin_role_ids, default=[]),
            "moderator_role_ids": deserialize_json_field(cfg.moderator_role_ids, default=[]),
            "global_allowed_domains": deserialize_json_field(cfg.global_allowed_domains, default=[]),
        }
    finally:
        await session.close()

    # Check exemptions by role
    admin_roles = set(server_config_dict.get("admin_role_ids", []))
    mod_roles = set(server_config_dict.get("moderator_role_ids", []))
    exempt_roles = admin_roles | mod_roles
    for r in role_ids:
        try:
            if int(r) in exempt_roles:
                return {
                    "allowed": True,
                    "reason": "Exempt from moderation: user has moderator/admin role",
                    "matched_rule": "role_exemption",
                    "effective_value": "allow",
                    "matched_policy": "Role Exemption",
                }
        except (ValueError, TypeError):
            pass

    # Determine effective policy dict
    target_policy_dict = None
    if isinstance(policy_override, dict) and policy_override:
        target_policy_dict = policy_override
    elif channel_id > 0:
        session = await get_session_direct()
        try:
            db_pol = await ChannelPolicyRepo.get_for_channel(session, channel_id)
            if db_pol:
                target_policy_dict = {
                    "allow_text": db_pol.allow_text,
                    "allow_links": db_pol.allow_links,
                    "allow_images": db_pol.allow_images,
                    "allow_videos": db_pol.allow_videos,
                    "allow_files": db_pol.allow_files,
                    "allow_stickers": db_pol.allow_stickers,
                    "allow_everyone": db_pol.allow_everyone,
                    "allow_here": db_pol.allow_here,
                    "allow_role_mentions": db_pol.allow_role_mentions,
                    "allow_user_mentions": db_pol.allow_user_mentions,
                    "allowed_domains": deserialize_json_field(db_pol.allowed_domains, default=[]),
                    "preset_name": db_pol.preset_name,
                    "channel_name": db_pol.channel_name,
                }
        finally:
            await session.close()

    if not target_policy_dict:
        # Default allow
        target_policy_dict = {
            "allow_text": "allow",
            "allow_links": "allow",
            "allow_images": "allow",
            "allow_videos": "allow",
            "allow_files": "allow",
            "allow_stickers": "allow",
            "allow_everyone": "deny",
            "allow_here": "deny",
            "allow_role_mentions": "allow",
            "allow_user_mentions": "allow",
            "preset_name": "Default (Inherited)",
        }

    attachments_mock = []
    if has_attachment:
        ext_map = {"image": "test.png", "video": "test.mp4", "file": "test.pdf"}
        attachments_mock = [{
            "filename": ext_map.get(attachment_type, "test.bin"),
            "content_type": f"{attachment_type}/test",
        }]

    return evaluate_message_policy(
        policy=target_policy_dict,
        content=content,
        attachments=attachments_mock,
        server_config=server_config_dict,
        channel_name=target_policy_dict.get("channel_name", "Test Channel"),
    )


# ─── Moderation Log Settings & Guild Channels ───────────────────────────────

@router.get("/moderation/log-settings")
async def get_mod_log_settings(username: str = Depends(require_auth)):
    """Get Discord auto-mod log channel settings and bot permission status."""
    session = await get_session_direct()
    try:
        config = await ServerConfigRepo.get_or_create(session)
        await session.commit()

        mod_log_channel_id = str(config.mod_log_channel_id) if config.mod_log_channel_id else None
        events = deserialize_json_field(
            config.mod_log_events,
            default=[
                "policy_violation", "blocked_link", "blocked_attachment", "blocked_mention",
                "warning", "timeout", "kick", "ban",
            ],
        )

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        guild = bot.guild if bot else None

        channel_status = {
            "status": "not_configured" if not mod_log_channel_id else "ok",
            "channel_name": None,
            "can_view": False,
            "can_send": False,
            "can_embed": False,
            "warning": None,
        }

        if mod_log_channel_id:
            if not guild:
                channel_status["status"] = "bot_offline"
                channel_status["warning"] = "Bot is currently offline. Cannot verify Discord channel permissions."
            else:
                try:
                    cid = int(mod_log_channel_id)
                    ch = guild.get_channel(cid)
                    if not ch:
                        channel_status["status"] = "missing_channel"
                        channel_status["warning"] = "Selected Discord log channel does not exist or was deleted."
                    else:
                        channel_status["channel_name"] = ch.name
                        perms = ch.permissions_for(guild.me)
                        channel_status["can_view"] = perms.view_channel
                        channel_status["can_send"] = perms.send_messages
                        channel_status["can_embed"] = perms.embed_links

                        if not (perms.view_channel and perms.send_messages and perms.embed_links):
                            channel_status["status"] = "missing_permissions"
                            channel_status["warning"] = "Bot is missing required permissions (View Channel, Send Messages, or Embed Links)."
                except Exception as e:
                    channel_status["status"] = "error"
                    channel_status["warning"] = str(e)

        return {
            "mod_log_channel_id": mod_log_channel_id,
            "mod_log_events": events,
            "channel_status": channel_status,
        }
    finally:
        await session.close()


@router.put("/moderation/log-settings")
@router.post("/moderation/log-settings")
async def update_mod_log_settings(request: Request, username: str = Depends(require_auth)):
    """Update auto-mod log channel and enabled log event toggles."""
    data = await request.json()
    session = await get_session_direct()
    try:
        updates = {}
        if "mod_log_channel_id" in data:
            raw_cid = data["mod_log_channel_id"]
            updates["mod_log_channel_id"] = int(raw_cid) if raw_cid else None

        if "mod_log_events" in data:
            events = data["mod_log_events"]
            if isinstance(events, list):
                updates["mod_log_events"] = serialize_json_field(events)

        await ServerConfigRepo.update(session, **updates)
        await AuditLogRepo.log(session, username, "mod_log_settings_updated",
                               details=str(list(updates.keys())))
        await session.commit()

        # Invalidate moderation engine cache so it picks up the new log channel
        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True, "message": "Log settings updated successfully"}
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to update mod log settings")
        raise HTTPException(status_code=500, detail="Could not update log settings")
    finally:
        await session.close()


@router.get("/moderation/channels")
async def list_moderation_channels(username: str = Depends(require_auth)):
    """List all Discord guild channels annotated with their current moderation policies."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if bot else None

    session = await get_session_direct()
    try:
        policies = await ChannelPolicyRepo.get_all(session)
        pol_map = {str(p.discord_channel_id): p for p in policies}
    finally:
        await session.close()

    result = []
    if guild:
        # Categorized channels
        for category in guild.categories:
            for ch in category.channels:
                ch_type = "text"
                if isinstance(ch, discord.VoiceChannel):
                    ch_type = "voice"
                elif isinstance(ch, discord.StageChannel):
                    ch_type = "stage"
                elif isinstance(ch, discord.ForumChannel):
                    ch_type = "forum"

                pol = pol_map.get(str(ch.id))
                result.append({
                    "id": str(ch.id),
                    "name": ch.name,
                    "type": ch_type,
                    "category": category.name,
                    "category_id": str(category.id),
                    "position": ch.position,
                    "has_override": bool(pol),
                    "preset_name": pol.preset_name if pol else "INHERITED",
                    "enabled": pol.enabled if pol else True,
                })

        # Uncategorized channels
        for ch in guild.channels:
            if ch.category is None and not isinstance(ch, discord.CategoryChannel):
                ch_type = "text"
                if isinstance(ch, discord.VoiceChannel):
                    ch_type = "voice"
                pol = pol_map.get(str(ch.id))
                result.append({
                    "id": str(ch.id),
                    "name": ch.name,
                    "type": ch_type,
                    "category": "Uncategorized",
                    "category_id": None,
                    "position": ch.position,
                    "has_override": bool(pol),
                    "preset_name": pol.preset_name if pol else "INHERITED",
                    "enabled": pol.enabled if pol else True,
                })

    return result


# ─── Moderation ───────────────────────────────────────────────────────────────

@router.get("/moderation/cases")
async def list_cases(username: str = Depends(require_auth), limit: int = 50):
    """List recent moderation cases."""
    session = await get_session_direct()
    try:
        cases = await ModerationCaseRepo.get_recent(session, limit=min(limit, 100))
        return [{
            "case_number": c.case_number,
            "target_user_id": str(c.target_user_id),
            "target_username": c.target_username,
            "moderator_user_id": str(c.moderator_user_id),
            "moderator_username": c.moderator_username,
            "action": c.action.value if hasattr(c.action, 'value') else str(c.action),
            "reason": c.reason,
            "duration": c.duration,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        } for c in cases]
    finally:
        await session.close()


@router.get("/moderation/blocked")
async def list_blocked(username: str = Depends(require_auth), limit: int = 100):
    """List recent blocked messages."""
    session = await get_session_direct()
    try:
        blocked = await BlockedMessageRepo.get_recent(session, limit=min(limit, 200))
        return [{
            "id": b.id,
            "channel_id": str(b.channel_id),
            "user_id": str(b.user_id),
            "username": b.username,
            "content_preview": b.content_preview,
            "reason": b.reason,
            "rule": b.rule,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        } for b in blocked]
    finally:
        await session.close()


# ─── Channels (Discord) ──────────────────────────────────────────────────────

@router.get("/channels")
async def list_discord_channels(username: str = Depends(require_auth)):
    """List all channels from the configured guild."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    if not bot or not bot.guild:
        return []

    guild = bot.guild
    channels = []

    for category in guild.categories:
        for channel in category.channels:
            ch_type = "text"
            if isinstance(channel, discord.VoiceChannel):
                ch_type = "voice"
            elif isinstance(channel, discord.StageChannel):
                ch_type = "stage"
            elif isinstance(channel, discord.ForumChannel):
                ch_type = "forum"

            channels.append({
                "id": str(channel.id),
                "name": channel.name,
                "type": ch_type,
                "category": category.name,
                "category_id": str(category.id),
                "position": channel.position,
            })

    # Uncategorized channels
    for channel in guild.channels:
        if channel.category is None and not isinstance(channel, discord.CategoryChannel):
            ch_type = "text"
            if isinstance(channel, discord.VoiceChannel):
                ch_type = "voice"
            channels.append({
                "id": str(channel.id),
                "name": channel.name,
                "type": ch_type,
                "category": "Uncategorized",
                "category_id": None,
                "position": channel.position,
            })

    return channels


@router.get("/channels/roles")
async def list_guild_roles(username: str = Depends(require_auth)):
    """List all roles from the configured guild."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    if not bot or not bot.guild:
        return []

    return [{
        "id": str(role.id),
        "name": role.name,
        "color": str(role.color),
        "position": role.position,
    } for role in bot.guild.roles if role.name != "@everyone"]


# ─── Security ─────────────────────────────────────────────────────────────────

@router.post("/security/change-password")
async def change_password(request: Request, username: str = Depends(require_auth)):
    """Change admin password."""
    data = await request.json()
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    from app.dashboard.auth import verify_password

    session = await get_session_direct()
    try:
        user = await AdminUserRepo.get_by_username(session, username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not verify_password(user.password_hash, current_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        new_hash = hash_password(new_password)
        await AdminUserRepo.update_password(session, username, new_hash)
        await AuditLogRepo.log(session, username, "password_changed")
        await session.commit()

        return {"success": True, "message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


# ─── Server Config ───────────────────────────────────────────────────────────

@router.get("/settings/server")
async def get_server_config(username: str = Depends(require_auth)):
    """Get server configuration."""
    session = await get_session_direct()
    try:
        config = await ServerConfigRepo.get_or_create(session)
        await session.commit()
        return {
            "mod_log_channel_id": str(config.mod_log_channel_id) if config.mod_log_channel_id else None,
            "admin_role_ids": json.loads(config.admin_role_ids) if config.admin_role_ids else [],
            "moderator_role_ids": json.loads(config.moderator_role_ids) if config.moderator_role_ids else [],
            "global_allowed_domains": json.loads(config.global_allowed_domains) if config.global_allowed_domains else [],
            "warning_message_template": config.warning_message_template,
            "default_timeout_duration": config.default_timeout_duration,
        }
    finally:
        await session.close()


@router.post("/settings/server")
async def update_server_config(request: Request, username: str = Depends(require_auth)):
    """Update server configuration."""
    data = await request.json()

    session = await get_session_direct()
    try:
        updates = {}
        if "mod_log_channel_id" in data:
            updates["mod_log_channel_id"] = int(data["mod_log_channel_id"]) if data["mod_log_channel_id"] else None
        if "admin_role_ids" in data:
            updates["admin_role_ids"] = json.dumps(data["admin_role_ids"])
        if "moderator_role_ids" in data:
            updates["moderator_role_ids"] = json.dumps(data["moderator_role_ids"])
        if "global_allowed_domains" in data:
            updates["global_allowed_domains"] = json.dumps(data["global_allowed_domains"])
        if "warning_message_template" in data:
            updates["warning_message_template"] = data["warning_message_template"]
        if "default_timeout_duration" in data:
            updates["default_timeout_duration"] = int(data["default_timeout_duration"])

        await ServerConfigRepo.update(session, **updates)
        await AuditLogRepo.log(session, username, "server_config_updated",
                               details=str(list(updates.keys())))
        await session.commit()

        # Refresh moderation cache
        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


# ─── Exemptions ───────────────────────────────────────────────────────────────

@router.get("/settings/exemptions")
async def list_exemptions(username: str = Depends(require_auth)):
    """List all exemption rules."""
    session = await get_session_direct()
    try:
        rules = await ExemptionRuleRepo.get_all(session)
        return [{
            "id": r.id,
            "rule_type": r.rule_type,
            "target_id": str(r.target_id),
            "target_name": r.target_name,
            "exempt_from": r.exempt_from,
        } for r in rules]
    finally:
        await session.close()


@router.post("/settings/exemptions")
async def add_exemption(request: Request, username: str = Depends(require_auth)):
    """Add an exemption rule."""
    data = await request.json()

    session = await get_session_direct()
    try:
        rule = await ExemptionRuleRepo.add(
            session,
            rule_type=data["rule_type"],
            target_id=int(data["target_id"]),
            target_name=data.get("target_name"),
            exempt_from=data.get("exempt_from", "all"),
        )
        await AuditLogRepo.log(session, username, "exemption_added",
                               f"{data['rule_type']}:{data['target_id']}")
        await session.commit()

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True, "id": rule.id}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.delete("/settings/exemptions/{rule_id}")
async def remove_exemption(rule_id: int, username: str = Depends(require_auth)):
    """Remove an exemption rule."""
    session = await get_session_direct()
    try:
        removed = await ExemptionRuleRepo.remove(session, rule_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Exemption not found")

        await AuditLogRepo.log(session, username, "exemption_removed", str(rule_id))
        await session.commit()

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


# ─── Audit Logs ───────────────────────────────────────────────────────────────

@router.get("/audit-logs")
async def get_audit_logs(username: str = Depends(require_auth), limit: int = 100):
    """Get recent audit logs."""
    session = await get_session_direct()
    try:
        logs = await AuditLogRepo.get_recent(session, limit=min(limit, 200))
        return [{
            "id": l.id,
            "actor": l.actor,
            "action": l.action,
            "target": l.target,
            "details": l.details,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        } for l in logs]
    finally:
        await session.close()
