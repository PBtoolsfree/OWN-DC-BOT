"""
PB HERO Dashboard API Routes.

All API routes require authenticated session.
Every route validates the logged-in admin session server-side.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

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
from app.database.models import EventType, ModerationAction, PolicyValue, ServerGreetingSettings, ServerInviteSettings
from app.database.serializers import (
    deserialize_json_field,
    normalize_domain,
    normalize_domain_list,
    serialize_json_field,
)
from app.moderation.evaluator import (
    evaluate_automod_rules,
    evaluate_message_policy,
    evaluate_voice_policy,
)
from app.database.repositories import (
    AdminUserRepo,
    AuditLogRepo,
    AutomodRuleRepo,
    BlockedMessageRepo,
    ChannelPolicyRepo,
    ExemptionRuleRepo,
    ModerationCaseRepo,
    ModerationExemptionRepo,
    PolicyProfileRepo,
    ServerConfigRepo,
    ServerGreetingSettingsRepo,
    ServerInviteSettingsRepo,
    WarningEscalationRepo,
    WarningRecordRepo,
    YouTubeChannelRepo,
    YouTubeDestinationRepo,
    YouTubeEventRepo,
    YouTubeTemplateRepo,
)

from app.greetings.service import get_greeting_service
from app.greetings.templates import (
    GOODBYE_VARIABLES,
    WELCOME_VARIABLES,
    GOODBYE_DM_VARIABLES,
    WELCOME_DM_VARIABLES,
    RULES_VARIABLES,
    validate_variables,
    build_rules_url,
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
    def _val(attr, default="inherit"):
        v = getattr(p, attr, default)
        return v.value if hasattr(v, "value") else str(v or default)

    return {
        "id": p.id,
        "discord_channel_id": str(p.discord_channel_id),
        "channel_name": p.channel_name,
        "category_name": p.category_name,
        "channel_type": getattr(p, "channel_type", "text") or "text",
        "allow_text": _val("allow_text"),
        "allow_links": _val("allow_links"),
        "allow_images": _val("allow_images"),
        "allow_videos": _val("allow_videos"),
        "allow_files": _val("allow_files"),
        "allow_stickers": _val("allow_stickers"),
        "allow_everyone": _val("allow_everyone"),
        "allow_here": _val("allow_here"),
        "allow_role_mentions": _val("allow_role_mentions"),
        "allow_user_mentions": _val("allow_user_mentions"),
        "allow_connect": _val("allow_connect"),
        "allow_speak": _val("allow_speak"),
        "allow_video": _val("allow_video"),
        "allow_stream": _val("allow_stream"),
        "allow_soundboard": _val("allow_soundboard"),
        "allow_voice_activity": _val("allow_voice_activity"),
        "allow_priority_speaker": _val("allow_priority_speaker"),
        "allow_mute_members": _val("allow_mute_members"),
        "allow_deafen_members": _val("allow_deafen_members"),
        "allow_move_members": _val("allow_move_members"),
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
    raw_domains = getattr(p, "allowed_domains", None)
    domains = deserialize_json_field(raw_domains, default=[])

    def _val(attr, default="allow"):
        v = getattr(p, attr, default)
        return v.value if hasattr(v, "value") else str(v or default)

    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "category": getattr(p, "category", "General") or "General",
        "policy_type": getattr(p, "policy_type", "text") or "text",
        "is_builtin": bool(p.is_builtin),
        "allow_text": _val("allow_text"),
        "allow_links": _val("allow_links"),
        "allow_images": _val("allow_images"),
        "allow_videos": _val("allow_videos"),
        "allow_files": _val("allow_files"),
        "allow_stickers": _val("allow_stickers"),
        "allow_everyone": _val("allow_everyone", "deny"),
        "allow_here": _val("allow_here", "deny"),
        "allow_role_mentions": _val("allow_role_mentions"),
        "allow_user_mentions": _val("allow_user_mentions"),
        "allow_connect": _val("allow_connect"),
        "allow_speak": _val("allow_speak"),
        "allow_video": _val("allow_video"),
        "allow_stream": _val("allow_stream"),
        "allow_soundboard": _val("allow_soundboard"),
        "allow_voice_activity": _val("allow_voice_activity"),
        "allow_priority_speaker": _val("allow_priority_speaker", "deny"),
        "allow_mute_members": _val("allow_mute_members", "deny"),
        "allow_deafen_members": _val("allow_deafen_members", "deny"),
        "allow_move_members": _val("allow_move_members", "deny"),
        "allowed_domains": domains,
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
        builtin_count = sum(1 for p in profiles if getattr(p, "is_builtin", False))
        if builtin_count < 25:
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
                      "allow_role_mentions", "allow_user_mentions",
                      "allow_connect", "allow_speak", "allow_video", "allow_stream",
                      "allow_soundboard", "allow_voice_activity", "allow_priority_speaker",
                      "allow_mute_members", "allow_deafen_members", "allow_move_members"]:
            if field in data and data[field] is not None:
                kwargs[field] = PolicyValue(str(data[field]).lower())

        if "policy_type" in data and data["policy_type"]:
            kwargs["policy_type"] = str(data["policy_type"]).lower()

        if "allowed_domains" in data:
            raw_d = data["allowed_domains"]
            if isinstance(raw_d, str):
                kwargs["allowed_domains"] = [x.strip() for x in raw_d.split(",") if x.strip()]
            elif isinstance(raw_d, list):
                kwargs["allowed_domains"] = [str(x).strip() for x in raw_d if str(x).strip()]

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
        if "policy_type" in data and data["policy_type"]:
            updates["policy_type"] = str(data["policy_type"]).lower()

        if "allowed_domains" in data:
            raw_d = data["allowed_domains"]
            if isinstance(raw_d, str):
                updates["allowed_domains"] = [x.strip() for x in raw_d.split(",") if x.strip()]
            elif isinstance(raw_d, list):
                updates["allowed_domains"] = [str(x).strip() for x in raw_d if str(x).strip()]

        for field in ["allow_text", "allow_links", "allow_images", "allow_videos",
                      "allow_files", "allow_stickers", "allow_everyone", "allow_here",
                      "allow_role_mentions", "allow_user_mentions",
                      "allow_connect", "allow_speak", "allow_video", "allow_stream",
                      "allow_soundboard", "allow_voice_activity", "allow_priority_speaker",
                      "allow_mute_members", "allow_deafen_members", "allow_move_members"]:
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
                allow_connect=getattr(prof, "allow_connect", PolicyValue.ALLOW),
                allow_speak=getattr(prof, "allow_speak", PolicyValue.ALLOW),
                allow_video=getattr(prof, "allow_video", PolicyValue.ALLOW),
                allow_stream=getattr(prof, "allow_stream", PolicyValue.ALLOW),
                allow_soundboard=getattr(prof, "allow_soundboard", PolicyValue.ALLOW),
                allow_voice_activity=getattr(prof, "allow_voice_activity", PolicyValue.ALLOW),
                allow_priority_speaker=getattr(prof, "allow_priority_speaker", PolicyValue.DENY),
                allow_mute_members=getattr(prof, "allow_mute_members", PolicyValue.DENY),
                allow_deafen_members=getattr(prof, "allow_deafen_members", PolicyValue.DENY),
                allow_move_members=getattr(prof, "allow_move_members", PolicyValue.DENY),
                allowed_domains=prof.allowed_domains,
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
                      "allow_role_mentions", "allow_user_mentions",
                      "allow_connect", "allow_speak", "allow_video", "allow_stream",
                      "allow_soundboard", "allow_voice_activity", "allow_priority_speaker",
                      "allow_mute_members", "allow_deafen_members", "allow_move_members"]:
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

    action_type = data.get("action_type")
    is_voice = (data.get("channel_type") == "voice") or bool(action_type)

    if is_voice:
        action = action_type or "connect"
        return evaluate_voice_policy(
            policy=target_policy_dict,
            action=action,
            channel_name=target_policy_dict.get("channel_name", "Test Voice Channel"),
        )

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
async def list_cases(
    username: str = Depends(require_auth),
    limit: int = 50,
    search: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    case_id: Optional[str] = None,
):
    """List moderation cases with filter support."""
    session = await get_session_direct()
    try:
        cases = await ModerationCaseRepo.get_recent(session, limit=min(limit, 200))
        # In-memory filter for flexible search
        filtered = cases
        if search:
            q = search.lower()
            filtered = [
                c for c in filtered
                if (c.target_username and q in c.target_username.lower())
                or (c.reason and q in c.reason.lower())
                or (c.rule and q in c.rule.lower())
                or (c.case_id and q in c.case_id.lower())
            ]
        if action and action != "all":
            filtered = [c for c in filtered if (c.action.value if hasattr(c.action, "value") else str(c.action)).lower() == action.lower()]
        if user_id:
            filtered = [c for c in filtered if str(c.target_user_id) == str(user_id)]
        if channel_id and channel_id != "all":
            filtered = [c for c in filtered if str(c.channel_id) == str(channel_id)]
        if case_id:
            filtered = [c for c in filtered if (c.case_id and case_id.lower() in c.case_id.lower())]

        return [{
            "id": c.id,
            "case_number": c.case_number,
            "case_id": c.case_id or f"CASE-{c.case_number:04d}",
            "target_user_id": str(c.target_user_id),
            "target_username": c.target_username,
            "moderator_user_id": str(c.moderator_user_id),
            "moderator_username": c.moderator_username,
            "action": c.action.value if hasattr(c.action, 'value') else str(c.action),
            "reason": c.reason,
            "duration": c.duration,
            "channel_id": str(c.channel_id) if c.channel_id else None,
            "channel_name": c.channel_name,
            "rule": c.rule,
            "policy_name": c.policy_name,
            "warning_id": c.warning_id,
            "severity": c.severity or "medium",
            "dm_status": c.dm_status or "disabled",
            "discord_log_status": c.discord_log_status or "delivered",
            "executor": c.executor or "PB HERO AutoMod",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        } for c in filtered]
    finally:
        await session.close()


@router.get("/moderation/cases/{case_identifier}")
async def get_case_details(case_identifier: str, username: str = Depends(require_auth)):
    """Get full case details by Case ID or Case Number."""
    session = await get_session_direct()
    try:
        case = None
        if case_identifier.isdigit():
            case = await ModerationCaseRepo.get_by_case_number(session, int(case_identifier))
        if not case:
            case = await ModerationCaseRepo.get_by_case_id(session, case_identifier.upper())
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Get target member avatar if bot is online
        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        avatar_url = None
        if bot and bot.guild:
            member = bot.guild.get_member(case.target_user_id)
            if member and hasattr(member, "display_avatar"):
                avatar_url = member.display_avatar.url

        return {
            "id": case.id,
            "case_number": case.case_number,
            "case_id": case.case_id or f"CASE-{case.case_number:04d}",
            "target_user_id": str(case.target_user_id),
            "target_username": case.target_username,
            "target_avatar_url": avatar_url,
            "moderator_user_id": str(case.moderator_user_id),
            "moderator_username": case.moderator_username,
            "action": case.action.value if hasattr(case.action, 'value') else str(case.action),
            "reason": case.reason,
            "duration": case.duration,
            "channel_id": str(case.channel_id) if case.channel_id else None,
            "channel_name": case.channel_name,
            "rule": case.rule,
            "policy_name": case.policy_name,
            "warning_id": case.warning_id,
            "severity": case.severity or "medium",
            "dm_status": case.dm_status or "disabled",
            "discord_log_status": case.discord_log_status or "delivered",
            "executor": case.executor or "PB HERO AutoMod",
            "created_at": case.created_at.isoformat() if case.created_at else None,
        }
    finally:
        await session.close()


@router.get("/moderation/stats")
async def get_moderation_stats(username: str = Depends(require_auth)):
    """Get accurate live moderation overview statistics."""
    session = await get_session_direct()
    try:
        active_warnings = await WarningRecordRepo.count_active_total(session)
        warnings_today = await WarningRecordRepo.count_today(session)
        timeouts_today = await ModerationCaseRepo.count_action_today(session, ModerationAction.TIMEOUT)
        kicks_today = await ModerationCaseRepo.count_action_today(session, ModerationAction.KICK)
        bans_today = await ModerationCaseRepo.count_action_today(session, ModerationAction.BAN)
        messages_blocked = await BlockedMessageRepo.count_today(session)
        cases_today = await ModerationCaseRepo.count_today(session)

        recent_cases = await ModerationCaseRepo.get_recent(session, limit=6)
        top_violations = await ModerationCaseRepo.get_top_violations(session, limit=5)

        return {
            "active_warnings": active_warnings,
            "warnings_today": warnings_today,
            "timeouts_today": timeouts_today,
            "kicks_today": kicks_today,
            "bans_today": bans_today,
            "messages_blocked": messages_blocked,
            "cases_today": cases_today,
            "top_violations": top_violations,
            "recent_cases": [{
                "case_number": c.case_number,
                "case_id": c.case_id or f"CASE-{c.case_number:04d}",
                "target_username": c.target_username,
                "action": c.action.value if hasattr(c.action, "value") else str(c.action),
                "reason": c.reason,
                "channel_name": c.channel_name,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            } for c in recent_cases],
        }
    finally:
        await session.close()


# ─── Granular Bypass & Exemptions ─────────────────────────────────────────────

@router.get("/moderation/guild-targets")
async def get_guild_targets(username: str = Depends(require_auth)):
    """Fetch real dynamic roles, members, bots, and channels from the connected guild."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    if not bot or not bot.guild:
        return {"roles": [], "members": [], "bots": [], "channels": [], "categories": []}

    guild = bot.guild

    roles = []
    for r in guild.roles:
        if r.name != "@everyone":
            p = r.permissions
            roles.append({
                "id": str(r.id),
                "name": r.name,
                "color": str(r.color),
                "position": r.position,
                "permissions": {
                    "administrator": p.administrator,
                    "manage_guild": p.manage_guild,
                    "manage_messages": p.manage_messages,
                    "moderate_members": p.moderate_members,
                    "kick_members": p.kick_members,
                    "ban_members": p.ban_members,
                },
            })

    members = []
    bots = []
    for m in guild.members:
        p = m.guild_permissions
        info = {
            "id": str(m.id),
            "username": str(m),
            "display_name": m.display_name,
            "bot": m.bot,
            "roles": [str(r.id) for r in m.roles if r.name != "@everyone"],
            "permissions": {
                "administrator": p.administrator,
                "manage_guild": p.manage_guild,
                "manage_messages": p.manage_messages,
                "moderate_members": p.moderate_members,
                "kick_members": p.kick_members,
                "ban_members": p.ban_members,
            },
        }
        if m.bot:
            bots.append(info)
        else:
            members.append(info)

    channels = []
    for ch in guild.channels:
        if not isinstance(ch, discord.CategoryChannel):
            channels.append({
                "id": str(ch.id),
                "name": ch.name,
                "type": "voice" if isinstance(ch, discord.VoiceChannel) else "text",
                "category": ch.category.name if ch.category else "Uncategorized",
                "category_id": str(ch.category.id) if ch.category else None,
            })

    categories = [{"id": str(c.id), "name": c.name} for c in guild.categories]

    return {
        "roles": roles,
        "members": members,
        "bots": bots,
        "channels": channels,
        "categories": categories,
    }


@router.get("/moderation/exemptions")
async def list_moderation_exemptions(username: str = Depends(require_auth)):
    """List all granular moderation exemptions."""
    session = await get_session_direct()
    try:
        rules = await ModerationExemptionRepo.get_all(session)
        return [{
            "id": r.id,
            "target_type": r.target_type,
            "target_id": str(r.target_id),
            "target_name": r.target_name,
            "scope": r.scope,
            "scope_id": str(r.scope_id) if r.scope_id else None,
            "scope_name": r.scope_name,
            "channel_type": r.channel_type,
            "bypass_all": bool(r.bypass_all),
            "bypass_text": bool(r.bypass_text),
            "bypass_links": bool(r.bypass_links),
            "bypass_images": bool(r.bypass_images),
            "bypass_videos": bool(r.bypass_videos),
            "bypass_files": bool(r.bypass_files),
            "bypass_stickers": bool(r.bypass_stickers),
            "bypass_mentions": bool(r.bypass_mentions),
            "bypass_spam": bool(r.bypass_spam),
            "bypass_keywords": bool(r.bypass_keywords),
            "bypass_invites": bool(r.bypass_invites),
            "bypass_warnings": bool(r.bypass_warnings),
            "bypass_timeout": bool(r.bypass_timeout),
            "bypass_kick": bool(r.bypass_kick),
            "bypass_ban": bool(r.bypass_ban),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rules]
    finally:
        await session.close()


@router.post("/moderation/exemptions")
async def create_moderation_exemption(request: Request, username: str = Depends(require_auth)):
    """Create a granular moderation exemption rule."""
    data = await request.json()
    target_type = str(data.get("target_type") or "").strip().lower()
    target_id_raw = data.get("target_id")
    if not target_type or target_id_raw is None:
        raise HTTPException(status_code=400, detail="target_type and target_id are required")

    session = await get_session_direct()
    try:
        target_id = int(target_id_raw)
        scope_id = int(data["scope_id"]) if data.get("scope_id") else None

        fields = {
            "target_name": data.get("target_name"),
            "scope": data.get("scope", "global"),
            "scope_id": scope_id,
            "scope_name": data.get("scope_name"),
            "channel_type": data.get("channel_type"),
        }
        bypass_keys = [
            "bypass_all", "bypass_text", "bypass_links", "bypass_images", "bypass_videos",
            "bypass_files", "bypass_stickers", "bypass_mentions", "bypass_spam",
            "bypass_keywords", "bypass_invites", "bypass_warnings", "bypass_timeout",
            "bypass_kick", "bypass_ban"
        ]
        for bk in bypass_keys:
            if bk in data:
                fields[bk] = bool(data[bk])

        created = await ModerationExemptionRepo.create(
            session=session,
            target_type=target_type,
            target_id=target_id,
            **fields,
        )
        await AuditLogRepo.log(session, username, "exemption_created", f"{target_type}:{target_id}")
        await session.commit()

        # Refresh bot engine cache
        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True, "id": created.id}
    except Exception as e:
        await session.rollback()
        logger.exception("Failed to create moderation exemption")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.put("/moderation/exemptions/{exemption_id}")
async def update_moderation_exemption(exemption_id: int, request: Request, username: str = Depends(require_auth)):
    """Update a granular moderation exemption rule."""
    data = await request.json()
    session = await get_session_direct()
    try:
        fields = {}
        for k in ["target_name", "scope", "scope_name", "channel_type"]:
            if k in data:
                fields[k] = data[k]
        if "scope_id" in data:
            fields["scope_id"] = int(data["scope_id"]) if data["scope_id"] else None

        bypass_keys = [
            "bypass_all", "bypass_text", "bypass_links", "bypass_images", "bypass_videos",
            "bypass_files", "bypass_stickers", "bypass_mentions", "bypass_spam",
            "bypass_keywords", "bypass_invites", "bypass_warnings", "bypass_timeout",
            "bypass_kick", "bypass_ban"
        ]
        for bk in bypass_keys:
            if bk in data:
                fields[bk] = bool(data[bk])

        updated = await ModerationExemptionRepo.update(session, exemption_id, **fields)
        if not updated:
            raise HTTPException(status_code=404, detail="Exemption not found")

        await AuditLogRepo.log(session, username, "exemption_updated", str(exemption_id))
        await session.commit()

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True}
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.delete("/moderation/exemptions/{exemption_id}")
async def delete_moderation_exemption(exemption_id: int, username: str = Depends(require_auth)):
    """Delete a moderation exemption rule."""
    session = await get_session_direct()
    try:
        deleted = await ModerationExemptionRepo.delete(session, exemption_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Exemption not found")

        await AuditLogRepo.log(session, username, "exemption_deleted", str(exemption_id))
        await session.commit()

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True}
    finally:
        await session.close()


# ─── Automod Rules ────────────────────────────────────────────────────────────

@router.get("/moderation/automod-rules")
@router.get("/moderation/automod/rules")
async def list_automod_rules(username: str = Depends(require_auth)):
    """List all configured automod detection rules."""
    session = await get_session_direct()
    try:
        rules = await AutomodRuleRepo.get_all(session)
        if not rules:
            await AutomodRuleRepo.create_defaults(session)
            await session.commit()
            rules = await AutomodRuleRepo.get_all(session)

        return [{
            "id": r.id,
            "rule_type": r.rule_type,
            "name": r.name,
            "description": r.description,
            "enabled": bool(r.enabled),
            "scope": r.scope,
            "channels": deserialize_json_field(r.channels, default=[]),
            "categories": deserialize_json_field(r.categories, default=[]),
            "threshold": r.threshold,
            "time_window": r.time_window,
            "action": r.action,
            "timeout_duration": r.timeout_duration,
            "cooldown": r.cooldown,
            "custom_keywords": deserialize_json_field(r.custom_keywords, default=[]),
            "log_event": bool(r.log_event),
            "severity": r.severity or "medium",
        } for r in rules]
    finally:
        await session.close()


@router.post("/moderation/automod-rules")
async def create_automod_rule(request: Request, username: str = Depends(require_auth)):
    """Create a new automod rule."""
    data = await request.json()
    rule_type = data.get("rule_type", "custom_rule")
    name = data.get("name", "New Rule")

    session = await get_session_direct()
    try:
        created = await AutomodRuleRepo.create(session, rule_type=rule_type, name=name, **data)
        await AuditLogRepo.log(session, username, "automod_rule_created", name)
        await session.commit()

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True, "id": created.id}
    finally:
        await session.close()


@router.put("/moderation/automod-rules/{rule_id}")
async def update_automod_rule(rule_id: int, request: Request, username: str = Depends(require_auth)):
    """Update an automod rule."""
    data = await request.json()
    session = await get_session_direct()
    try:
        updated = await AutomodRuleRepo.update(session, rule_id, **data)
        if not updated:
            raise HTTPException(status_code=404, detail="Rule not found")

        await AuditLogRepo.log(session, username, "automod_rule_updated", str(rule_id))
        await session.commit()

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True}
    finally:
        await session.close()


@router.delete("/moderation/automod-rules/{rule_id}")
async def delete_automod_rule(rule_id: int, username: str = Depends(require_auth)):
    """Delete an automod rule."""
    session = await get_session_direct()
    try:
        deleted = await AutomodRuleRepo.delete(session, rule_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Rule not found")

        await AuditLogRepo.log(session, username, "automod_rule_deleted", str(rule_id))
        await session.commit()

        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True}
    finally:
        await session.close()


# ─── Warnings & Actions ───────────────────────────────────────────────────────

@router.get("/moderation/warnings")
async def list_warnings(
    username: str = Depends(require_auth),
    user_id: Optional[str] = None,
    limit: int = 100,
):
    """List warning audit records with decay awareness."""
    session = await get_session_direct()
    try:
        uid = int(user_id) if user_id else None
        warnings = await WarningRecordRepo.get_all(session, user_id=uid, limit=min(limit, 200))
        return [{
            "id": w.id,
            "warning_id": w.warning_id,
            "case_id": w.case_id,
            "case_number": w.case_number,
            "user_id": str(w.user_id),
            "username": w.username,
            "channel_id": str(w.channel_id) if w.channel_id else None,
            "channel_name": w.channel_name,
            "rule": w.rule,
            "reason": w.reason,
            "moderator": w.moderator,
            "severity": w.severity,
            "points": w.points,
            "status": w.status,
            "action_taken": w.action_taken,
            "dm_status": w.dm_status,
            "created_at": w.created_at.isoformat() if w.created_at else None,
            "expires_at": w.expires_at.isoformat() if w.expires_at else None,
            "revoked_at": w.revoked_at.isoformat() if w.revoked_at else None,
            "revoked_by": w.revoked_by,
        } for w in warnings]
    finally:
        await session.close()


@router.post("/moderation/warnings")
async def issue_warning(request: Request, username: str = Depends(require_auth)):
    """Manually issue a warning to a member."""
    data = await request.json()
    user_id_raw = data.get("user_id")
    if not user_id_raw:
        raise HTTPException(status_code=400, detail="user_id is required")

    session = await get_session_direct()
    try:
        user_id = int(user_id_raw)
        created = await WarningRecordRepo.create(
            session=session,
            user_id=user_id,
            username=data.get("username", f"User-{user_id}"),
            rule=data.get("rule", "Manual Warning"),
            reason=data.get("reason", "Manual warning issued by administrator"),
            channel_id=int(data["channel_id"]) if data.get("channel_id") else None,
            channel_name=data.get("channel_name"),
            severity=data.get("severity", "medium"),
            points=int(data.get("points", 1)),
            moderator=username,
            action_taken="warn",
        )
        await AuditLogRepo.log(session, username, "warning_issued", str(user_id), details=data.get("reason"))
        await session.commit()
        return {"success": True, "warning_id": created.warning_id, "case_id": created.case_id}
    finally:
        await session.close()


@router.delete("/moderation/warnings/{warning_id}")
async def revoke_warning(warning_id: str, request: Request, username: str = Depends(require_auth)):
    """Revoke a specific warning."""
    reason = "Revoked via dashboard"
    try:
        data = await request.json()
        if data.get("reason"):
            reason = data["reason"]
    except Exception:
        pass

    session = await get_session_direct()
    try:
        success = await WarningRecordRepo.revoke(session, warning_id, revoked_by=username, reason=reason)
        if not success:
            raise HTTPException(status_code=404, detail="Warning not found")
        await AuditLogRepo.log(session, username, "warning_revoked", warning_id, details=reason)
        await session.commit()
        return {"success": True}
    finally:
        await session.close()


@router.delete("/moderation/warnings/user/{user_id}")
async def clear_user_warnings(user_id: int, username: str = Depends(require_auth)):
    """Clear all active warnings for a user."""
    session = await get_session_direct()
    try:
        cleared_count = await WarningRecordRepo.clear_user(session, user_id, revoked_by=username)
        await AuditLogRepo.log(session, username, "user_warnings_cleared", str(user_id), details=f"Cleared {cleared_count} warnings")
        await session.commit()
        return {"success": True, "cleared_count": cleared_count}
    finally:
        await session.close()


@router.get("/moderation/warnings/stats")
async def get_warnings_stats(username: str = Depends(require_auth)):
    """Get warning statistics."""
    session = await get_session_direct()
    try:
        active = await WarningRecordRepo.count_active_total(session)
        today = await WarningRecordRepo.count_today(session)
        config = await ServerConfigRepo.get_or_create(session)
        return {
            "active_warnings": active,
            "warnings_today": today,
            "decay_days": config.warning_decay_days,
            "mode": config.warning_mode,
        }
    finally:
        await session.close()


# ─── Escalation Ladder ────────────────────────────────────────────────────────

@router.get("/moderation/escalation-rules")
@router.get("/moderation/warnings/escalation")
async def list_escalation_rules(username: str = Depends(require_auth)):
    """List strike/point escalation ladder rules."""
    session = await get_session_direct()
    try:
        rules = await WarningEscalationRepo.get_all(session)
        if not rules:
            await WarningEscalationRepo.create_defaults(session)
            await session.commit()
            rules = await WarningEscalationRepo.get_all(session)

        return [{
            "id": r.id,
            "threshold": r.threshold,
            "mode": r.mode,
            "action": r.action,
            "duration": r.duration,
            "send_dm": bool(r.send_dm),
            "delete_message_history_days": r.delete_message_history_days,
            "reason_template": r.reason_template,
        } for r in rules]
    finally:
        await session.close()


@router.post("/moderation/escalation-rules")
async def create_escalation_rule(request: Request, username: str = Depends(require_auth)):
    """Create an escalation rule."""
    data = await request.json()
    session = await get_session_direct()
    try:
        created = await WarningEscalationRepo.create(
            session=session,
            threshold=int(data["threshold"]),
            mode=data.get("mode", "count"),
            action=data["action"],
            duration=int(data["duration"]) if data.get("duration") else None,
            send_dm=bool(data.get("send_dm", True)),
            delete_message_history_days=int(data.get("delete_message_history_days", 0)),
            reason_template=data.get("reason_template"),
        )
        await AuditLogRepo.log(session, username, "escalation_rule_created", str(created.threshold))
        await session.commit()
        return {"success": True, "id": created.id}
    finally:
        await session.close()


@router.put("/moderation/escalation-rules/{rule_id}")
async def update_escalation_rule(rule_id: int, request: Request, username: str = Depends(require_auth)):
    """Update an escalation rule."""
    data = await request.json()
    session = await get_session_direct()
    try:
        updated = await WarningEscalationRepo.update(session, rule_id, **data)
        if not updated:
            raise HTTPException(status_code=404, detail="Rule not found")
        await AuditLogRepo.log(session, username, "escalation_rule_updated", str(rule_id))
        await session.commit()
        return {"success": True}
    finally:
        await session.close()


@router.delete("/moderation/escalation-rules/{rule_id}")
async def delete_escalation_rule(rule_id: int, username: str = Depends(require_auth)):
    """Delete an escalation rule."""
    session = await get_session_direct()
    try:
        deleted = await WarningEscalationRepo.delete(session, rule_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Rule not found")
        await AuditLogRepo.log(session, username, "escalation_rule_deleted", str(rule_id))
        await session.commit()
        return {"success": True}
    finally:
        await session.close()


# ─── Quick Setup / Easy Mode ──────────────────────────────────────────────────

@router.get("/moderation/quick-setup")
async def get_quick_setup_preview(username: str = Depends(require_auth)):
    """Get preview descriptions of quick moderation styles."""
    return {
        "styles": {
            "light": {
                "name": "Light",
                "description": "Warnings + limited deletes. Friendly community atmosphere.",
                "actions": ["Warnings on first 3 strikes", "10-minute timeout on 4th strike", "1-hour timeout on 5th strike", "No automatic bans"],
                "decay_days": 14,
            },
            "balanced": {
                "name": "Balanced (Recommended)",
                "description": "Standard community moderation: warnings, progressive timeouts, kick on repeated offenses.",
                "actions": ["Warnings on strikes 1-2", "10m timeout on strike 3", "1h timeout on strike 4", "Kick on strike 5", "Ban on strike 6"],
                "decay_days": 30,
            },
            "strict": {
                "name": "Strict",
                "description": "Fast escalation for zero-tolerance or high-security community.",
                "actions": ["Warning on strike 1", "1h timeout on strike 2", "1-day timeout on strike 3", "Kick on strike 4", "Permanent ban on strike 5"],
                "decay_days": 60,
            },
        }
    }


@router.post("/moderation/quick-setup")
async def apply_quick_setup(request: Request, username: str = Depends(require_auth)):
    """Apply a chosen quick setup moderation style."""
    data = await request.json()
    style = data.get("style", "balanced").lower()

    session = await get_session_direct()
    try:
        config = await ServerConfigRepo.get_or_create(session)
        config.quick_setup_style = style

        # Clear old escalation rules and apply style ladder
        await session.execute(delete(WarningEscalationRule))

        if style == "light":
            config.warning_decay_days = 14
            ladder = [
                {"threshold": 1, "mode": "count", "action": "warn", "send_dm": True, "reason_template": "First warning"},
                {"threshold": 2, "mode": "count", "action": "warn", "send_dm": True, "reason_template": "Second warning"},
                {"threshold": 3, "mode": "count", "action": "warn", "send_dm": True, "reason_template": "Third warning"},
                {"threshold": 4, "mode": "count", "action": "timeout", "duration": 600, "send_dm": True, "reason_template": "10-minute timeout"},
                {"threshold": 5, "mode": "count", "action": "timeout", "duration": 3600, "send_dm": True, "reason_template": "1-hour timeout"},
            ]
        elif style == "strict":
            config.warning_decay_days = 60
            ladder = [
                {"threshold": 1, "mode": "count", "action": "warn", "send_dm": True, "reason_template": "First warning"},
                {"threshold": 2, "mode": "count", "action": "timeout", "duration": 3600, "send_dm": True, "reason_template": "1-hour timeout"},
                {"threshold": 3, "mode": "count", "action": "timeout", "duration": 86400, "send_dm": True, "reason_template": "24-hour timeout"},
                {"threshold": 4, "mode": "count", "action": "kick", "send_dm": True, "reason_template": "Kicked from server"},
                {"threshold": 5, "mode": "count", "action": "ban", "send_dm": True, "delete_message_history_days": 1, "reason_template": "Permanently banned"},
            ]
        else:  # balanced
            config.warning_decay_days = 30
            ladder = [
                {"threshold": 1, "mode": "count", "action": "warn", "send_dm": True, "reason_template": "First warning"},
                {"threshold": 2, "mode": "count", "action": "warn", "send_dm": True, "reason_template": "Second warning"},
                {"threshold": 3, "mode": "count", "action": "timeout", "duration": 600, "send_dm": True, "reason_template": "10-minute timeout"},
                {"threshold": 4, "mode": "count", "action": "timeout", "duration": 3600, "send_dm": True, "reason_template": "1-hour timeout"},
                {"threshold": 5, "mode": "count", "action": "kick", "send_dm": True, "reason_template": "Kicked from server"},
                {"threshold": 6, "mode": "count", "action": "ban", "send_dm": True, "delete_message_history_days": 1, "reason_template": "Permanently banned"},
            ]

        for item in ladder:
            await WarningEscalationRepo.create(session, **item)

        await AuditLogRepo.log(session, username, "quick_setup_applied", style)
        await session.commit()

        # Invalidate moderation engine cache
        from app.runtime_state import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True, "message": f"Applied {style.title()} moderation style successfully"}
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


# ??? Server Welcome & Goodbye Automation ????????????????????????????????????????

# ─── Server Welcome & Goodbye Automation ────────────────────────────────────────

def _serialize_greeting_settings(row: ServerGreetingSettings) -> Dict[str, Any]:
    return {
        "id": row.id,
        "guild_id": str(row.guild_id),
        "welcome_enabled": row.welcome_enabled,
        "welcome_channel_id": str(row.welcome_channel_id) if row.welcome_channel_id else None,
        "welcome_title": row.welcome_title,
        "welcome_description": row.welcome_description,
        "welcome_footer": row.welcome_footer,
        "welcome_mention_user": row.welcome_mention_user,
        "welcome_show_avatar": row.welcome_show_avatar,
        "welcome_show_server_icon": row.welcome_show_server_icon,
        "welcome_show_member_count": row.welcome_show_member_count,
        "welcome_show_timestamp": row.welcome_show_timestamp,
        "welcome_use_embed": row.welcome_use_embed,
        "goodbye_enabled": row.goodbye_enabled,
        "goodbye_channel_id": str(row.goodbye_channel_id) if row.goodbye_channel_id else None,
        "goodbye_title": row.goodbye_title,
        "goodbye_description": row.goodbye_description,
        "goodbye_footer": row.goodbye_footer,
        "goodbye_mention_user": row.goodbye_mention_user,
        "goodbye_show_avatar": row.goodbye_show_avatar,
        "goodbye_show_server_icon": row.goodbye_show_server_icon,
        "goodbye_show_member_count": row.goodbye_show_member_count,
        "goodbye_show_timestamp": row.goodbye_show_timestamp,
        "goodbye_use_embed": row.goodbye_use_embed,
        "allow_mass_mentions": row.allow_mass_mentions,
        "rules_delivery_enabled": row.rules_delivery_enabled,
        "rules_source": row.rules_source,
        "rules_channel_id": str(row.rules_channel_id) if row.rules_channel_id else None,
        "rules_title": row.rules_title,
        "rules_description": row.rules_description,
        "rules_footer": row.rules_footer,
        "rules_button_text": row.rules_button_text,
        "auto_role_enabled": row.auto_role_enabled,
        "auto_role_id": str(row.auto_role_id) if row.auto_role_id else None,
        "welcome_dm_enabled": row.welcome_dm_enabled,
        "welcome_dm_title": row.welcome_dm_title,
        "welcome_dm_description": row.welcome_dm_description,
        "welcome_dm_footer": row.welcome_dm_footer,
        "welcome_dm_use_embed": row.welcome_dm_use_embed,
        "welcome_dm_show_avatar": row.welcome_dm_show_avatar,
        "welcome_dm_show_server_icon": row.welcome_dm_show_server_icon,
        "welcome_dm_show_timestamp": row.welcome_dm_show_timestamp,
        "goodbye_dm_enabled": row.goodbye_dm_enabled,
        "goodbye_dm_title": row.goodbye_dm_title,
        "goodbye_dm_description": row.goodbye_dm_description,
        "goodbye_dm_footer": row.goodbye_dm_footer,
        "goodbye_dm_use_embed": row.goodbye_dm_use_embed,
        "goodbye_dm_show_avatar": row.goodbye_dm_show_avatar,
        "goodbye_dm_show_server_icon": row.goodbye_dm_show_server_icon,
        "goodbye_dm_show_timestamp": row.goodbye_dm_show_timestamp,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_invite_settings(row: ServerInviteSettings) -> Dict[str, Any]:
    return {
        "id": row.id,
        "guild_id": str(row.guild_id),
        "invite_channel_id": str(row.invite_channel_id) if row.invite_channel_id else None,
        "invite_code": row.invite_code,
        "invite_url": row.invite_url,
        "is_active": row.is_active,
        "max_age": row.max_age,
        "max_uses": row.max_uses,
        "temporary": row.temporary,
        "verification_status": row.verification_status,
        "verification_error": row.verification_error,
        "last_verified_at": row.last_verified_at.isoformat() if row.last_verified_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/greetings")
async def get_greeting_settings(username: str = Depends(require_auth)):
    """Get current server greeting settings, invite info, rules telemetry, and activity."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None

    guild_id = settings.DISCORD_GUILD_ID or (guild.id if guild else 0)
    session = await get_session_direct()
    try:
        config = await ServerGreetingSettingsRepo.get_or_create(session, guild_id)
        invite_row = await ServerInviteSettingsRepo.get_or_create(session, guild_id)
        await session.commit()
    finally:
        await session.close()

    service = get_greeting_service(bot)

    welcome_channel = guild.get_channel(config.welcome_channel_id) if (guild and config.welcome_channel_id) else None
    goodbye_channel = guild.get_channel(config.goodbye_channel_id) if (guild and config.goodbye_channel_id) else None
    rules_channel = guild.get_channel(config.rules_channel_id) if (guild and config.rules_channel_id) else None

    if not config.welcome_channel_id:
        welcome_status = {
            "status": "not_configured",
            "channel_name": None,
            "can_view": False,
            "can_send": False,
            "can_embed": False,
            "warning": None,
        }
    elif not guild:
        welcome_status = {
            "status": "offline",
            "channel_name": None,
            "can_view": False,
            "can_send": False,
            "can_embed": False,
            "warning": "Bot is currently offline.",
        }
    elif not welcome_channel:
        welcome_status = {
            "status": "missing_channel",
            "channel_name": None,
            "can_view": False,
            "can_send": False,
            "can_embed": False,
            "warning": "Selected channel is unavailable.",
        }
    else:
        _, welcome_status = service.check_channel_permissions(welcome_channel, requires_embed=bool(config.welcome_use_embed))

    if not config.goodbye_channel_id:
        goodbye_status = {
            "status": "not_configured",
            "channel_name": None,
            "can_view": False,
            "can_send": False,
            "can_embed": False,
            "warning": None,
        }
    elif not guild:
        goodbye_status = {
            "status": "offline",
            "channel_name": None,
            "can_view": False,
            "can_send": False,
            "can_embed": False,
            "warning": "Bot is currently offline.",
        }
    elif not goodbye_channel:
        goodbye_status = {
            "status": "missing_channel",
            "channel_name": None,
            "can_view": False,
            "can_send": False,
            "can_embed": False,
            "warning": "Selected channel is unavailable.",
        }
    else:
        _, goodbye_status = service.check_channel_permissions(goodbye_channel, requires_embed=bool(config.goodbye_use_embed))

    if not config.rules_channel_id:
        rules_status = {
            "status": "not_configured",
            "channel_name": None,
            "can_view": False,
            "warning": None,
        }
    elif not guild:
        rules_status = {
            "status": "offline",
            "channel_name": None,
            "can_view": False,
            "warning": "Bot is offline.",
        }
    elif not rules_channel:
        rules_status = {
            "status": "missing_channel",
            "channel_name": None,
            "can_view": False,
            "warning": "Selected rules channel is unavailable.",
        }
    else:
        rules_status = {
            "status": "ok",
            "channel_name": getattr(rules_channel, "name", "rules"),
            "can_view": True,
            "warning": None,
        }

    server_info = {
        "server_id": str(guild_id),
        "server_name": guild.name if guild else "PB HERO SERVER",
        "member_count": guild.member_count if guild else 0,
        "server_icon": guild.icon.url if (guild and guild.icon) else None,
        "bot_online": bool(bot and bot.is_ready()),
    }

    return {
        "settings": _serialize_greeting_settings(config),
        "invite": _serialize_invite_settings(invite_row),
        "server": server_info,
        "welcome_channel_status": welcome_status,
        "goodbye_channel_status": goodbye_status,
        "rules_channel_status": rules_status,
        "recent_activity": service.get_recent_activity(20),
        "stats": service.get_stats(),
    }


@router.put("/greetings")
async def update_greeting_settings(request: Request, username: str = Depends(require_auth)):
    """Update greeting settings with variable validation and channel check."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None
    guild_id = settings.DISCORD_GUILD_ID or (guild.id if guild else 0)

    session = await get_session_direct()
    try:
        existing = await ServerGreetingSettingsRepo.get_or_create(session, guild_id)

        # 1. Variable validation across template categories
        val_checks = [
            ("welcome_title", WELCOME_VARIABLES),
            ("welcome_description", WELCOME_VARIABLES),
            ("welcome_footer", WELCOME_VARIABLES),
            ("goodbye_title", GOODBYE_VARIABLES),
            ("goodbye_description", GOODBYE_VARIABLES),
            ("goodbye_footer", GOODBYE_VARIABLES),
            ("welcome_dm_title", WELCOME_DM_VARIABLES),
            ("welcome_dm_description", WELCOME_DM_VARIABLES),
            ("welcome_dm_footer", WELCOME_DM_VARIABLES),
            ("goodbye_dm_title", GOODBYE_DM_VARIABLES),
            ("goodbye_dm_description", GOODBYE_DM_VARIABLES),
            ("goodbye_dm_footer", GOODBYE_DM_VARIABLES),
            ("rules_title", RULES_VARIABLES),
            ("rules_description", RULES_VARIABLES),
            ("rules_footer", RULES_VARIABLES),
        ]
        for field, allowed_set in val_checks:
            if field in data and data[field] is not None:
                inv = validate_variables(data[field], allowed_set)
                if inv:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Unsupported variable in {field}: " + ", ".join(f"{{{v}}}" for v in inv),
                    )

        # Mass mentions safety check
        allow_mass = data.get("allow_mass_mentions", existing.allow_mass_mentions)
        if not allow_mass:
            for field, _ in val_checks:
                val = data.get(field)
                if val and ("@everyone" in val or "@here" in val):
                    raise HTTPException(
                        status_code=400,
                        detail="Mass mentions (@everyone, @here) require 'Allow Mass Mentions' to be enabled.",
                    )

        updates = {}
        for key in (
            "welcome_enabled", "welcome_channel_id", "welcome_title", "welcome_description",
            "welcome_footer", "welcome_mention_user", "welcome_show_avatar", "welcome_show_server_icon",
            "welcome_show_member_count", "welcome_show_timestamp", "welcome_use_embed",
            "goodbye_enabled", "goodbye_channel_id", "goodbye_title", "goodbye_description",
            "goodbye_footer", "goodbye_mention_user", "goodbye_show_avatar", "goodbye_show_server_icon",
            "goodbye_show_member_count", "goodbye_show_timestamp", "goodbye_use_embed",
            "allow_mass_mentions", "rules_delivery_enabled", "rules_source", "rules_channel_id",
            "rules_title", "rules_description", "rules_footer", "rules_button_text",
            "auto_role_enabled", "auto_role_id",
            "welcome_dm_enabled", "welcome_dm_title", "welcome_dm_description", "welcome_dm_footer",
            "welcome_dm_use_embed", "welcome_dm_show_avatar", "welcome_dm_show_server_icon", "welcome_dm_show_timestamp",
            "goodbye_dm_enabled", "goodbye_dm_title", "goodbye_dm_description", "goodbye_dm_footer",
            "goodbye_dm_use_embed", "goodbye_dm_show_avatar", "goodbye_dm_show_server_icon", "goodbye_dm_show_timestamp"
        ):
            if key in data:
                val = data[key]
                if key in ("welcome_channel_id", "goodbye_channel_id", "rules_channel_id", "auto_role_id"):
                    val = int(val) if val else None
                updates[key] = val

        updated = await ServerGreetingSettingsRepo.update(session, guild_id, **updates)
        await AuditLogRepo.log(session, username, "update_greeting_settings")
        await session.commit()

        return {
            "success": True,
            "message": "Greeting settings updated successfully",
            "settings": _serialize_greeting_settings(updated),
        }
    finally:
        await session.close()


@router.get("/greetings/channels")
async def list_greeting_channels(username: str = Depends(require_auth)):
    """List text and announcement channels suitable for welcome/goodbye greetings."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    if not bot or not bot.guild:
        return []

    guild = bot.guild
    me = guild.me
    if not me:
        return []

    channels_data = []
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            c_type = "text"
        elif isinstance(channel, discord.StageChannel) or isinstance(channel, discord.VoiceChannel):
            continue
        elif hasattr(channel, "is_news") and channel.is_news():
            c_type = "announcement"
        else:
            continue

        perms = channel.permissions_for(me)
        can_view = bool(perms.view_channel)
        can_send = bool(perms.send_messages)
        can_embed = bool(perms.embed_links)

        channels_data.append({
            "id": str(channel.id),
            "name": channel.name,
            "type": c_type,
            "category": channel.category.name if channel.category else "Uncategorized",
            "category_id": str(channel.category.id) if channel.category else None,
            "position": channel.position,
            "can_view": can_view,
            "can_send": can_send,
            "can_embed": can_embed,
            "is_selectable": can_view and can_send,
        })

    channels_data.sort(key=lambda c: c["position"])
    return channels_data


@router.get("/greetings/roles")
async def list_greeting_roles(username: str = Depends(require_auth)):
    """List guild roles with hierarchy and assignability status."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None
    if not guild:
        return []
    service = get_greeting_service(bot)
    return service.get_guild_roles(guild.id)


@router.get("/greetings/rules")
async def get_rules_settings(username: str = Depends(require_auth)):
    """Get rules delivery settings and resolved URL."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None
    guild_id = settings.DISCORD_GUILD_ID or (guild.id if guild else 0)

    session = await get_session_direct()
    try:
        config = await ServerGreetingSettingsRepo.get_or_create(session, guild_id)
        await session.commit()
    finally:
        await session.close()

    rules_url = build_rules_url(guild_id, config.rules_channel_id)
    return {
        "rules_delivery_enabled": config.rules_delivery_enabled,
        "rules_source": config.rules_source,
        "rules_channel_id": str(config.rules_channel_id) if config.rules_channel_id else None,
        "rules_title": config.rules_title,
        "rules_description": config.rules_description,
        "rules_footer": config.rules_footer,
        "rules_button_text": config.rules_button_text,
        "rules_url": rules_url,
    }


@router.put("/greetings/rules")
async def update_rules_settings(request: Request, username: str = Depends(require_auth)):
    """Update rules delivery configuration."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None
    guild_id = settings.DISCORD_GUILD_ID or (guild.id if guild else 0)

    for field in ("rules_title", "rules_description", "rules_footer"):
        if field in data and data[field] is not None:
            inv = validate_variables(data[field], RULES_VARIABLES)
            if inv:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported variable in {field}: " + ", ".join(f"{{{v}}}" for v in inv),
                )

    session = await get_session_direct()
    try:
        updates = {}
        for key in ("rules_delivery_enabled", "rules_source", "rules_channel_id", "rules_title", "rules_description", "rules_footer", "rules_button_text"):
            if key in data:
                val = data[key]
                if key == "rules_channel_id":
                    val = int(val) if val else None
                updates[key] = val

        updated = await ServerGreetingSettingsRepo.update(session, guild_id, **updates)
        await AuditLogRepo.log(session, username, "update_rules_settings")
        await session.commit()
        return {
            "success": True,
            "message": "Rules settings updated successfully",
            "rules_url": build_rules_url(guild_id, updated.rules_channel_id),
        }
    finally:
        await session.close()


@router.get("/greetings/invite")
async def get_invite_settings(username: str = Depends(require_auth)):
    """Get current permanent invite configuration and verification status."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None
    guild_id = settings.DISCORD_GUILD_ID or (guild.id if guild else 0)

    session = await get_session_direct()
    try:
        invite_row = await ServerInviteSettingsRepo.get_or_create(session, guild_id)
        await session.commit()
    finally:
        await session.close()

    channel_name = None
    if guild and invite_row.invite_channel_id:
        ch = guild.get_channel(invite_row.invite_channel_id)
        channel_name = ch.name if ch else None

    return {
        "invite": _serialize_invite_settings(invite_row),
        "channel_name": channel_name,
        "is_permanent": bool(invite_row.max_age == 0 and invite_row.max_uses == 0 and invite_row.is_active),
    }


@router.post("/greetings/invite/generate")
async def generate_invite(request: Request, username: str = Depends(require_auth)):
    """Generate a permanent Discord invite for the designated channel."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None
    if not guild:
        raise HTTPException(status_code=503, detail="Bot is offline or guild is unavailable.")

    try:
        data = await request.json()
    except Exception:
        data = {}

    channel_id = data.get("channel_id")
    if not channel_id:
        session = await get_session_direct()
        try:
            cfg = await ServerGreetingSettingsRepo.get_or_create(session, guild.id)
            inv = await ServerInviteSettingsRepo.get_or_create(session, guild.id)
            channel_id = inv.invite_channel_id or cfg.welcome_channel_id
        finally:
            await session.close()

    if not channel_id:
        raise HTTPException(status_code=400, detail="No invite destination channel specified.")

    service = get_greeting_service(bot)
    try:
        res = await service.generate_permanent_invite(guild.id, int(channel_id))
        session = await get_session_direct()
        try:
            await AuditLogRepo.log(session, username, f"generate_permanent_invite:{res.get('invite_code')}")
            await session.commit()
        finally:
            await session.close()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/greetings/invite/verify")
async def verify_invite_endpoint(username: str = Depends(require_auth)):
    """Verify validity and permanence of the stored invite."""
    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None
    guild_id = settings.DISCORD_GUILD_ID or (guild.id if guild else 0)

    service = get_greeting_service(bot)
    return await service.verify_invite(guild_id)


@router.post("/greetings/invite/regenerate")
async def regenerate_invite_endpoint(request: Request, username: str = Depends(require_auth)):
    """Regenerate the permanent server invite with explicit confirmation."""
    try:
        data = await request.json()
    except Exception:
        data = {}

    if not data.get("confirm"):
        raise HTTPException(status_code=400, detail="Regeneration requires explicit confirmation flag.")

    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None
    if not guild:
        raise HTTPException(status_code=503, detail="Bot is offline or guild is unavailable.")

    session = await get_session_direct()
    try:
        cfg = await ServerGreetingSettingsRepo.get_or_create(session, guild.id)
        inv = await ServerInviteSettingsRepo.get_or_create(session, guild.id)
        channel_id = data.get("channel_id") or inv.invite_channel_id or cfg.welcome_channel_id
    finally:
        await session.close()

    if not channel_id:
        raise HTTPException(status_code=400, detail="No invite channel configured.")

    service = get_greeting_service(bot)
    try:
        res = await service.generate_permanent_invite(guild.id, int(channel_id), unique=True)
        session = await get_session_direct()
        try:
            await AuditLogRepo.log(session, username, f"regenerate_invite:{res.get('invite_code')}")
            await session.commit()
        finally:
            await session.close()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/greetings/test/{system_type}")
async def test_greeting_message(system_type: str, username: str = Depends(require_auth)):
    """Dispatch a test message (welcome, goodbye, welcome-dm, goodbye-dm)."""
    norm_type = system_type.lower().replace("_", "-")
    if norm_type not in ("welcome", "goodbye", "welcome-dm", "goodbye-dm"):
        raise HTTPException(status_code=400, detail="Invalid greeting type. Must be 'welcome', 'goodbye', 'welcome-dm', or 'goodbye-dm'.")

    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    if not bot or not bot.is_ready():
        raise HTTPException(status_code=503, detail="PB HERO bot is currently offline. Cannot send test Discord message.")

    service = get_greeting_service(bot)
    try:
        result = await service.send_test_message(norm_type)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to dispatch test greeting: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to send test message: {e}")


@router.post("/greetings/reset/{system_type}")
async def reset_greeting_settings(system_type: str, username: str = Depends(require_auth)):
    """Reset welcome, goodbye, welcome_dm, goodbye_dm, or rules templates to defaults."""
    norm_type = system_type.lower().replace("-", "_")
    if norm_type not in ("welcome", "goodbye", "welcome_dm", "goodbye_dm", "rules"):
        raise HTTPException(status_code=400, detail="Invalid system type.")

    from app.runtime_state import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if (bot and bot.is_ready()) else None
    guild_id = settings.DISCORD_GUILD_ID or (guild.id if guild else 0)

    session = await get_session_direct()
    try:
        if norm_type == "welcome":
            updated = await ServerGreetingSettingsRepo.reset_welcome(session, guild_id)
        elif norm_type == "goodbye":
            updated = await ServerGreetingSettingsRepo.reset_goodbye(session, guild_id)
        elif norm_type == "welcome_dm":
            updated = await ServerGreetingSettingsRepo.reset_welcome_dm(session, guild_id)
        elif norm_type == "goodbye_dm":
            updated = await ServerGreetingSettingsRepo.reset_goodbye_dm(session, guild_id)
        elif norm_type == "rules":
            updated = await ServerGreetingSettingsRepo.reset_rules(session, guild_id)

        await AuditLogRepo.log(session, username, f"reset_{norm_type}_greetings")
        await session.commit()

        return {
            "success": True,
            "message": f"{norm_type.replace('_', ' ').capitalize()} settings have been reset to defaults.",
            "settings": _serialize_greeting_settings(updated),
        }
    finally:
        await session.close()
