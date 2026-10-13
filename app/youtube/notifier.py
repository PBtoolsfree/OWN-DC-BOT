"""
PB HERO YouTube Notifier.

Creates professional Discord embeds for YouTube notifications.
Uses safe allowed_mentions to prevent unwanted pings.
Renders event-specific notification templates.
"""

import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import discord

from app.database.engine import get_session_direct
from app.database.models import EventType
from app.database.repositories import YouTubeTemplateRepo

logger = logging.getLogger("pbhero.youtube")

# Embed colors
COLORS = {
    EventType.UPLOAD: 0xFF0000,          # Red for new videos
    EventType.LIVE_STARTED: 0xFF0000,    # Red for live
    EventType.SCHEDULED_LIVE: 0xFFA500,  # Orange for scheduled
    EventType.PREMIERE: 0x9B59B6,        # Purple for premiere
}

# Emoji prefixes
EMOJIS = {
    EventType.UPLOAD: "🎬",
    EventType.LIVE_STARTED: "🔴",
    EventType.SCHEDULED_LIVE: "⏰",
    EventType.PREMIERE: "🎬",
}

# Status text
STATUS_TEXT = {
    EventType.UPLOAD: "NEW VIDEO",
    EventType.LIVE_STARTED: "LIVE NOW",
    EventType.SCHEDULED_LIVE: "SCHEDULED LIVE",
    EventType.PREMIERE: "PREMIERE",
}


class NotificationResult:
    """Result of a notification delivery attempt."""

    def __init__(self, success: bool, is_permanent: bool = False, error: str = ""):
        self.success = success
        self.is_permanent = is_permanent
        self.error = error

    def __bool__(self) -> bool:
        return self.success

    def __repr__(self) -> str:
        return f"NotificationResult(success={self.success}, permanent={self.is_permanent}, error={self.error!r})"


def extract_discord_error_details(exc: discord.HTTPException) -> tuple[int, int, str, bool]:
    """
    Safely extract HTTP status, error code, detailed error text, and whether the error is permanent.
    Never exposes sensitive credentials or tokens.
    """
    status = getattr(exc, "status", 0)
    code = getattr(exc, "code", 0)
    text = getattr(exc, "text", "") or str(exc)

    # Permanent client errors: 400 Bad Request (including 50035 Invalid Form Body),
    # 403 Forbidden, 404 Not Found, etc.
    # Transient errors: 429 Rate Limited, 408 Request Timeout, 5xx Server Errors.
    is_permanent = (status == 400 and code == 50035) or (400 <= status < 500 and status not in (429, 408))
    return status, code, text, is_permanent


def _parse_scheduled_datetime(val: Optional[str]) -> Optional[datetime]:
    """Safely parse scheduled start time from ISO string or unix timestamp."""
    if not val or not str(val).strip():
        return None
    val_str = str(val).strip()
    try:
        cleaned = val_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        ts = float(val_str)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        pass
    return None


def render_template_text(template_str: str, context: dict) -> str:
    """Safely replace template variables in string."""
    if not template_str:
        return ""
    result = template_str
    for key, val in context.items():
        placeholder = f"{{{key}}}"
        if placeholder in result:
            result = result.replace(placeholder, str(val) if val is not None else "")
    return result


def create_notification_embed(
    event_type: EventType,
    title: str,
    video_url: str,
    channel_name: str,
    thumbnail_url: str = None,
    description: str = None,
    template: Optional[dict] = None,
    channel_id: str = "",
    published_at: Optional[datetime] = None,
    scheduled_start: Optional[str] = None,
    viewer_count: Optional[int] = None,
    started_at: Optional[datetime] = None,
) -> discord.Embed:
    """Create a professional Discord embed for a YouTube notification using event-specific template."""

    emoji = EMOJIS.get(event_type, "📺")
    status = STATUS_TEXT.get(event_type, "NEW")
    color = COLORS.get(event_type, 0xFF0000)

    # Template fallback from defaults if not provided
    tpl = template or YouTubeTemplateRepo.DEFAULTS.get(event_type, {})

    # Safely parse scheduled start time
    sched_dt = _parse_scheduled_datetime(scheduled_start)
    formatted_sched = None
    if sched_dt:
        unix_ts = int(sched_dt.timestamp())
        formatted_sched = f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"
    elif scheduled_start and str(scheduled_start).strip():
        formatted_sched = str(scheduled_start).strip()

    context = {
        "channel_name": channel_name,
        "video_title": title,
        "video_url": video_url,
        "channel_id": channel_id,
        "published_at": published_at.strftime("%Y-%m-%d %H:%M UTC") if published_at else "Recently",
        "scheduled_start": formatted_sched or "Soon",
        "viewer_count": f"{viewer_count:,}" if viewer_count is not None else "—",
        "started_at": started_at.strftime("%Y-%m-%d %H:%M UTC") if started_at else "Just now",
    }

    raw_title = tpl.get("title_template") or f"{emoji} {channel_name} - {status}"
    raw_desc = tpl.get("description_template") or f"**{title}**"
    footer = tpl.get("footer_text") or "PB HERO Personal Discord Bot"
    show_thumbnail = tpl.get("show_thumbnail", True)
    show_timestamp = tpl.get("show_timestamp", True)

    embed_title = render_template_text(raw_title, context).strip()
    if not embed_title:
        embed_title = f"{emoji} {channel_name} - {status}"
    embed_title = embed_title[:256]

    embed_description = render_template_text(raw_desc, context).strip()
    if description and "{description}" not in raw_desc:
        clean_desc = description.strip()
        if clean_desc:
            embed_description += f"\n\n> {clean_desc[:200]}..."
    if not embed_description:
        embed_description = f"**{title}**"
    embed_description = embed_description[:4096]

    # Timestamp handling: if scheduled stream has a verified scheduled datetime, use it; otherwise fallback safely
    embed_timestamp = None
    if show_timestamp:
        if event_type == EventType.SCHEDULED_LIVE and sched_dt:
            embed_timestamp = sched_dt
        elif published_at:
            embed_timestamp = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
        else:
            embed_timestamp = datetime.now(timezone.utc)

    # Preflight-clean video URL
    clean_video_url = None
    if video_url and " " not in video_url.strip() and video_url.strip().startswith(("http://", "https://")):
        clean_video_url = video_url.strip()

    embed = discord.Embed(
        title=embed_title,
        description=embed_description,
        url=clean_video_url,
        color=color,
        timestamp=embed_timestamp,
    )

    # Scheduled livestream field: if scheduled_start is missing, omit the field completely
    if event_type == EventType.SCHEDULED_LIVE and formatted_sched:
        embed.add_field(name="⏰ Scheduled Start", value=formatted_sched, inline=True)

    # Thumbnail validation: strictly require valid HTTP(S) URL without spaces
    if thumbnail_url and show_thumbnail:
        clean_thumb = thumbnail_url.strip()
        if clean_thumb.startswith(("http://", "https://")) and " " not in clean_thumb:
            embed.set_image(url=clean_thumb)

    # Author URL: must NOT contain unencoded spaces!
    author_name = (channel_name or "YouTube").strip()[:256]
    clean_cid = channel_id.strip() if channel_id else ""
    if clean_cid and (clean_cid.startswith("UC") or clean_cid.startswith("HC")) and " " not in clean_cid:
        author_url = f"https://www.youtube.com/channel/{clean_cid}"
    elif channel_name and channel_name.strip():
        author_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(channel_name.strip())}"
    else:
        author_url = None

    embed.set_author(name=author_name, url=author_url)

    footer_text = (footer or "PB HERO Personal Discord Bot").strip()[:2048]
    embed.set_footer(text=footer_text, icon_url="https://www.youtube.com/s/desktop/f506bd45/img/favicon_32.png")

    return embed


def create_notification_view(video_url: str, event_type: EventType) -> Optional[discord.ui.View]:
    """Create a view with action buttons matching the specific event type."""
    clean_url = video_url.strip() if video_url and " " not in video_url.strip() and video_url.strip().startswith(("http://", "https://")) else None
    if not clean_url:
        return None

    view = discord.ui.View(timeout=None)

    if event_type == EventType.LIVE_STARTED:
        label = "▶ WATCH LIVE"
    elif event_type == EventType.SCHEDULED_LIVE:
        label = "📅 SET REMINDER"
    elif event_type == EventType.PREMIERE:
        label = "▶ WATCH PREMIERE"
    else:
        label = "▶ WATCH VIDEO"

    button = discord.ui.Button(
        label=label,
        url=clean_url,
        style=discord.ButtonStyle.link,
    )
    view.add_item(button)
    return view


async def send_notification(
    bot: discord.Client,
    discord_channel_id: int,
    event_type: EventType,
    title: str,
    video_url: str,
    channel_name: str,
    thumbnail_url: str = None,
    description: str = None,
    role_id: Optional[int] = None,
    channel_id: str = "",
    published_at: Optional[datetime] = None,
    scheduled_start: Optional[str] = None,
    viewer_count: Optional[int] = None,
    started_at: Optional[datetime] = None,
) -> NotificationResult:
    """
    Send a YouTube notification to a Discord channel using its event-specific template.

    Uses safe allowed_mentions to prevent mass pings.
    Returns NotificationResult (evaluates as boolean).
    """
    try:
        channel = bot.get_channel(discord_channel_id)
        if not channel and hasattr(bot, "fetch_channel"):
            try:
                channel = await bot.fetch_channel(discord_channel_id)
            except Exception as e:
                logger.warning("Could not fetch Discord channel %d from API: %s", discord_channel_id, e)

        if not channel:
            logger.error("Discord channel %d not found (cache and API fetch failed)", discord_channel_id)
            return NotificationResult(success=False, is_permanent=True, error="Channel not found")

        # Fetch event-specific template from DB
        template_data = None
        try:
            session = await get_session_direct()
            try:
                tpl = await YouTubeTemplateRepo.get_by_event_type(session, event_type)
                template_data = {
                    "title_template": tpl.title_template,
                    "description_template": tpl.description_template,
                    "mention_role": tpl.mention_role,
                    "footer_text": tpl.footer_text,
                    "show_thumbnail": tpl.show_thumbnail,
                    "show_timestamp": tpl.show_timestamp,
                    "enable_button": tpl.enable_button,
                }
            finally:
                await session.close()
        except Exception as e:
            logger.warning("Could not load template from DB for event %s: %s; using defaults", event_type, e)
            template_data = YouTubeTemplateRepo.DEFAULTS.get(event_type, {})

        embed = create_notification_embed(
            event_type=event_type,
            title=title,
            video_url=video_url,
            channel_name=channel_name,
            thumbnail_url=thumbnail_url,
            description=description,
            template=template_data,
            channel_id=channel_id,
            published_at=published_at,
            scheduled_start=scheduled_start,
            viewer_count=viewer_count,
            started_at=started_at,
        )

        enable_btn = template_data.get("enable_button", True) if template_data else True
        view = create_notification_view(video_url, event_type) if enable_btn else None

        send_kwargs = {
            "embed": embed,
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        if view:
            send_kwargs["view"] = view

        # Role mention content (safe)
        mention_role_id = role_id
        if not mention_role_id and template_data and template_data.get("mention_role"):
            val = str(template_data.get("mention_role")).strip()
            if val.isdigit():
                mention_role_id = int(val)

        if mention_role_id:
            send_kwargs["content"] = f"<@&{mention_role_id}>"
            send_kwargs["allowed_mentions"] = discord.AllowedMentions(
                everyone=False,
                users=False,
                roles=[discord.Object(id=mention_role_id)],
            )

        await channel.send(**send_kwargs)

        logger.info("Sent %s notification to channel %d: %s", event_type.value, discord_channel_id, title)
        return NotificationResult(success=True)

    except discord.Forbidden as e:
        logger.error("Missing permissions to send notification to channel %d: %s", discord_channel_id, e)
        return NotificationResult(success=False, is_permanent=True, error=str(e))
    except discord.HTTPException as e:
        status, code, err_text, is_permanent = extract_discord_error_details(e)
        logger.error(
            "Discord API error sending to channel %d [status=%s, code=%s, permanent=%s]: %s",
            discord_channel_id, status, code, is_permanent, err_text
        )
        return NotificationResult(success=False, is_permanent=is_permanent, error=f"HTTP {status} ({code}): {err_text}")
    except Exception as e:
        logger.exception("Failed to send notification to channel %d: %s", discord_channel_id, e)
        return NotificationResult(success=False, is_permanent=False, error=str(e))
