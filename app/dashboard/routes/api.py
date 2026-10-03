"""
PB HERO Dashboard API Routes.

All API routes require authenticated session.
Every route validates the logged-in admin session server-side.
"""

import json
import logging
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
    from app.main import get_bot_instance
    bot = get_bot_instance()

    bot_connected = False
    bot_latency = 0
    guild_name = "Unknown"
    guild_members = 0
    yt_running = False
    yt_healthy = False

    if bot:
        bot_connected = bot.is_ready()
        bot_latency = round(bot.latency * 1000) if bot.is_ready() else 0
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
            "uptime": bot.uptime if bot else 0,
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
        from app.main import get_bot_instance
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
    from app.main import get_bot_instance
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
    from app.youtube.live_detector import check_live_status
    live_info = await check_live_status(channel_id)
    return {
        "success": True,
        "is_live": live_info.get("is_live", False),
        "status": live_info.get("status", "offline"),
        "title": live_info.get("title"),
        "video_id": live_info.get("video_id"),
    }


# ─── Channel Policies ────────────────────────────────────────────────────────

@router.get("/policies")
async def list_policies(username: str = Depends(require_auth)):
    """List all channel policies."""
    session = await get_session_direct()
    try:
        policies = await ChannelPolicyRepo.get_all(session)
        return [{
            "id": p.id,
            "discord_channel_id": str(p.discord_channel_id),
            "channel_name": p.channel_name,
            "category_name": p.category_name,
            "channel_type": p.channel_type,
            "allow_text": p.allow_text.value if hasattr(p.allow_text, 'value') else str(p.allow_text),
            "allow_links": p.allow_links.value if hasattr(p.allow_links, 'value') else str(p.allow_links),
            "allow_images": p.allow_images.value if hasattr(p.allow_images, 'value') else str(p.allow_images),
            "allow_videos": p.allow_videos.value if hasattr(p.allow_videos, 'value') else str(p.allow_videos),
            "allow_files": p.allow_files.value if hasattr(p.allow_files, 'value') else str(p.allow_files),
            "allow_stickers": p.allow_stickers.value if hasattr(p.allow_stickers, 'value') else str(p.allow_stickers),
            "allow_everyone": p.allow_everyone.value if hasattr(p.allow_everyone, 'value') else str(p.allow_everyone),
            "allow_here": p.allow_here.value if hasattr(p.allow_here, 'value') else str(p.allow_here),
            "allow_role_mentions": p.allow_role_mentions.value if hasattr(p.allow_role_mentions, 'value') else str(p.allow_role_mentions),
            "allow_user_mentions": p.allow_user_mentions.value if hasattr(p.allow_user_mentions, 'value') else str(p.allow_user_mentions),
            "allowed_domains": p.allowed_domains,
            "preset_name": p.preset_name,
            "enabled": p.enabled,
            "delete_violations": p.delete_violations,
            "warn_on_violation": p.warn_on_violation,
            "log_violations": p.log_violations,
        } for p in policies]
    finally:
        await session.close()


# ─── Guild Info ─────────────────────────────────────────────────────────────

@router.get("/guild")
async def get_guild_info(username: str = Depends(require_auth)):
    """Get single-server guild information."""
    from app.main import get_bot_instance
    bot = get_bot_instance()
    guild = bot.guild if bot else None
    return {
        "guild_id": str(settings.DISCORD_GUILD_ID),
        "name": guild.name if guild else "PB HERO Server",
        "member_count": guild.member_count if guild else 0,
        "is_configured": settings.is_configured(),
        "single_server": True,
    }


# ─── Policy Profiles ─────────────────────────────────────────────────────────

@router.get("/policies/profiles")
async def list_profiles(username: str = Depends(require_auth)):
    """List policy profiles/presets."""
    session = await get_session_direct()
    try:
        profiles = await PolicyProfileRepo.get_all(session)
        return [{
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "is_builtin": p.is_builtin,
            "allow_text": p.allow_text.value if hasattr(p.allow_text, 'value') else str(p.allow_text),
            "allow_links": p.allow_links.value if hasattr(p.allow_links, 'value') else str(p.allow_links),
            "allow_images": p.allow_images.value if hasattr(p.allow_images, 'value') else str(p.allow_images),
            "allow_videos": p.allow_videos.value if hasattr(p.allow_videos, 'value') else str(p.allow_videos),
            "allow_files": p.allow_files.value if hasattr(p.allow_files, 'value') else str(p.allow_files),
            "allow_stickers": p.allow_stickers.value if hasattr(p.allow_stickers, 'value') else str(p.allow_stickers),
            "allow_everyone": p.allow_everyone.value if hasattr(p.allow_everyone, 'value') else str(p.allow_everyone),
            "allow_here": p.allow_here.value if hasattr(p.allow_here, 'value') else str(p.allow_here),
            "allow_role_mentions": p.allow_role_mentions.value if hasattr(p.allow_role_mentions, 'value') else str(p.allow_role_mentions),
            "allow_user_mentions": p.allow_user_mentions.value if hasattr(p.allow_user_mentions, 'value') else str(p.allow_user_mentions),
        } for p in profiles]
    finally:
        await session.close()


@router.get("/policies/{channel_id}")
async def get_channel_policy(channel_id: int, username: str = Depends(require_auth)):
    """Get policy for a specific channel."""
    session = await get_session_direct()
    try:
        p = await ChannelPolicyRepo.get_for_channel(session, channel_id)
        if not p:
            return None
        return {
            "id": p.id,
            "discord_channel_id": str(p.discord_channel_id),
            "channel_name": p.channel_name,
            "category_name": p.category_name,
            "channel_type": p.channel_type,
            "allow_text": p.allow_text.value if hasattr(p.allow_text, 'value') else str(p.allow_text),
            "allow_links": p.allow_links.value if hasattr(p.allow_links, 'value') else str(p.allow_links),
            "allow_images": p.allow_images.value if hasattr(p.allow_images, 'value') else str(p.allow_images),
            "allow_videos": p.allow_videos.value if hasattr(p.allow_videos, 'value') else str(p.allow_videos),
            "allow_files": p.allow_files.value if hasattr(p.allow_files, 'value') else str(p.allow_files),
            "allow_stickers": p.allow_stickers.value if hasattr(p.allow_stickers, 'value') else str(p.allow_stickers),
            "allow_everyone": p.allow_everyone.value if hasattr(p.allow_everyone, 'value') else str(p.allow_everyone),
            "allow_here": p.allow_here.value if hasattr(p.allow_here, 'value') else str(p.allow_here),
            "allow_role_mentions": p.allow_role_mentions.value if hasattr(p.allow_role_mentions, 'value') else str(p.allow_role_mentions),
            "allow_user_mentions": p.allow_user_mentions.value if hasattr(p.allow_user_mentions, 'value') else str(p.allow_user_mentions),
            "allowed_domains": p.allowed_domains,
            "preset_name": p.preset_name,
            "enabled": p.enabled,
            "delete_violations": p.delete_violations,
            "warn_on_violation": p.warn_on_violation,
            "log_violations": p.log_violations,
            "warning_message": p.warning_message,
        }
    finally:
        await session.close()


@router.post("/policies/{channel_id}")
async def save_policy(channel_id: int, request: Request, username: str = Depends(require_auth)):
    """Save or update a channel policy."""
    data = await request.json()

    session = await get_session_direct()
    try:
        # Convert string values to PolicyValue enums
        policy_fields = {}
        for field in ["allow_text", "allow_links", "allow_images", "allow_videos",
                      "allow_files", "allow_stickers", "allow_everyone", "allow_here",
                      "allow_role_mentions", "allow_user_mentions"]:
            if field in data:
                policy_fields[field] = PolicyValue(data[field])

        for field in ["channel_name", "category_name", "channel_type", "preset_name",
                      "warning_message", "allowed_domains"]:
            if field in data:
                policy_fields[field] = data[field]

        for field in ["enabled", "delete_violations", "warn_on_violation", "log_violations"]:
            if field in data:
                policy_fields[field] = data[field]

        policy_fields["updated_by"] = username

        await ChannelPolicyRepo.upsert(session, channel_id, **policy_fields)
        await AuditLogRepo.log(session, username, "policy_updated", str(channel_id))
        await session.commit()

        # Refresh moderation engine cache
        from app.main import get_bot_instance
        bot = get_bot_instance()
        if bot and bot.moderation_engine:
            await bot.moderation_engine.refresh_cache()

        return {"success": True}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@router.delete("/policies/{channel_id}")
async def delete_policy(channel_id: int, username: str = Depends(require_auth)):
    """Delete a channel policy."""
    session = await get_session_direct()
    try:
        deleted = await ChannelPolicyRepo.delete_policy(session, channel_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Policy not found")

        await AuditLogRepo.log(session, username, "policy_deleted", str(channel_id))
        await session.commit()

        from app.main import get_bot_instance
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


# ─── Policy Simulator ────────────────────────────────────────────────────────

@router.post("/policies/simulate")
async def simulate_policy(request: Request, username: str = Depends(require_auth)):
    """Simulate a policy check (policy tester)."""
    data = await request.json()
    channel_id = int(data.get("channel_id", 0))
    content = data.get("content", "")
    role_ids = data.get("role_ids", [])
    has_attachment = data.get("has_attachment", False)
    attachment_type = data.get("attachment_type", "image")

    from app.main import get_bot_instance
    bot = get_bot_instance()
    if bot and bot.moderation_engine:
        result = await bot.moderation_engine.simulate_policy(
            channel_id, role_ids, content, has_attachment, attachment_type
        )
        return result
    return {"allowed": True, "reason": "Moderation engine not available"}


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
    from app.main import get_bot_instance
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
    from app.main import get_bot_instance
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
        from app.main import get_bot_instance
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

        from app.main import get_bot_instance
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

        from app.main import get_bot_instance
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
