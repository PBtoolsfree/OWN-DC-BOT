"""
PB HERO YouTube Notifier.

Creates professional Discord embeds for YouTube notifications.
Uses safe allowed_mentions to prevent unwanted pings.
Renders event-specific notification templates.
"""

import logging
from datetime import datetime
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

    context = {
        "channel_name": channel_name,
        "video_title": title,
        "video_url": video_url,
        "channel_id": channel_id,
        "published_at": published_at.strftime("%Y-%m-%d %H:%M UTC") if published_at else "Recently",
        "scheduled_start": str(scheduled_start) if scheduled_start else "Soon",
        "viewer_count": f"{viewer_count:,}" if viewer_count is not None else "—",
        "started_at": started_at.strftime("%Y-%m-%d %H:%M UTC") if started_at else "Just now",
    }

    raw_title = tpl.get("title_template") or f"{emoji} {channel_name} - {status}"
    raw_desc = tpl.get("description_template") or f"**{title}**"
    footer = tpl.get("footer_text") or "PB HERO Personal Discord Bot"
    show_thumbnail = tpl.get("show_thumbnail", True)
    show_timestamp = tpl.get("show_timestamp", True)

    embed_title = render_template_text(raw_title, context)
    embed_description = render_template_text(raw_desc, context)

    if description and "{description}" not in raw_desc:
        embed_description += f"\n\n> {description[:200]}..."

    embed = discord.Embed(
        title=embed_title,
        description=embed_description,
        url=video_url,
        color=color,
        timestamp=datetime.utcnow() if show_timestamp else None,
    )

    if thumbnail_url and show_thumbnail:
        embed.set_image(url=thumbnail_url)

    embed.set_author(name=channel_name, url=f"https://www.youtube.com/results?search_query={channel_name}")
    embed.set_footer(text=footer, icon_url="https://www.youtube.com/s/desktop/f506bd45/img/favicon_32.png")

    return embed


def create_notification_view(video_url: str, event_type: EventType) -> discord.ui.View:
    """Create a view with action buttons matching the specific event type."""
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
        url=video_url,
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
) -> bool:
    """
    Send a YouTube notification to a Discord channel using its event-specific template.

    Uses safe allowed_mentions to prevent mass pings.
    Returns True if sent successfully.
    """
    try:
        channel = bot.get_channel(discord_channel_id)
        if not channel:
            logger.error("Discord channel %d not found", discord_channel_id)
            return False

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

        # Role mention content (safe)
        content = None
        allowed_mentions = discord.AllowedMentions.none()
        mention_role_id = role_id
        if not mention_role_id and template_data and template_data.get("mention_role"):
            val = str(template_data.get("mention_role")).strip()
            if val.isdigit():
                mention_role_id = int(val)

        if mention_role_id:
            content = f"<@&{mention_role_id}>"
            allowed_mentions = discord.AllowedMentions(roles=[discord.Object(id=mention_role_id)])

        await channel.send(
            content=content,
            embed=embed,
            view=view,
            allowed_mentions=allowed_mentions,
        )

        logger.info("Sent %s notification to channel %d: %s", event_type.value, discord_channel_id, title)
        return True

    except discord.Forbidden:
        logger.error("Missing permissions to send to channel %d", discord_channel_id)
        return False
    except discord.HTTPException as e:
        logger.error("Discord API error sending to %d: %s", discord_channel_id, str(e))
        return False
    except Exception as e:
        logger.error("Failed to send notification to %d: %s", discord_channel_id, str(e))
        return False
