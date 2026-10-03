"""
PB HERO YouTube Notifier.

Creates professional Discord embeds for YouTube notifications.
Uses safe allowed_mentions to prevent unwanted pings.
"""

import logging
from datetime import datetime
from typing import Optional

import discord

from app.database.models import EventType

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
    EventType.SCHEDULED_LIVE: "📅",
    EventType.PREMIERE: "🎬",
}

# Status text
STATUS_TEXT = {
    EventType.UPLOAD: "NEW VIDEO",
    EventType.LIVE_STARTED: "LIVE NOW",
    EventType.SCHEDULED_LIVE: "SCHEDULED LIVE",
    EventType.PREMIERE: "PREMIERE",
}


def create_notification_embed(
    event_type: EventType,
    title: str,
    video_url: str,
    channel_name: str,
    thumbnail_url: str = None,
    description: str = None,
) -> discord.Embed:
    """Create a professional Discord embed for a YouTube notification."""

    emoji = EMOJIS.get(event_type, "📺")
    status = STATUS_TEXT.get(event_type, "NEW")
    color = COLORS.get(event_type, 0xFF0000)

    if event_type == EventType.LIVE_STARTED:
        embed_title = f"{emoji} {channel_name} IS LIVE!"
        embed_description = f"**{title}**\n\n🔴 **LIVE NOW** — Watch the stream!"
    elif event_type == EventType.SCHEDULED_LIVE:
        embed_title = f"{emoji} UPCOMING LIVE STREAM"
        embed_description = f"**{title}**\n\n📅 A live stream has been scheduled."
    elif event_type == EventType.PREMIERE:
        embed_title = f"{emoji} PREMIERE"
        embed_description = f"**{title}**\n\n🎬 A new premiere is starting!"
    else:
        embed_title = f"{emoji} NEW VIDEO"
        embed_description = f"**{title}**\n\nA new video has been uploaded."

    if description:
        embed_description += f"\n\n> {description[:200]}..."

    embed = discord.Embed(
        title=embed_title,
        description=embed_description,
        url=video_url,
        color=color,
        timestamp=datetime.utcnow(),
    )

    if thumbnail_url:
        embed.set_image(url=thumbnail_url)

    embed.set_author(name=channel_name, url=f"https://www.youtube.com/results?search_query={channel_name}")
    embed.set_footer(text=f"YouTube • {status}", icon_url="https://www.youtube.com/s/desktop/f506bd45/img/favicon_32.png")

    return embed


def create_notification_view(video_url: str, event_type: EventType) -> discord.ui.View:
    """Create a view with action buttons."""
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
) -> bool:
    """
    Send a YouTube notification to a Discord channel.

    Uses safe allowed_mentions to prevent mass pings.

    Returns True if sent successfully.
    """
    try:
        channel = bot.get_channel(discord_channel_id)
        if not channel:
            logger.error("Discord channel %d not found", discord_channel_id)
            return False

        embed = create_notification_embed(
            event_type=event_type,
            title=title,
            video_url=video_url,
            channel_name=channel_name,
            thumbnail_url=thumbnail_url,
            description=description,
        )
        view = create_notification_view(video_url, event_type)

        # Role mention content (safe)
        content = None
        allowed_mentions = discord.AllowedMentions.none()
        if role_id:
            content = f"<@&{role_id}>"
            allowed_mentions = discord.AllowedMentions(roles=[discord.Object(id=role_id)])

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
