"""
Discord embed and claim button builder for Free Games & Deals Tracker.
"""

from datetime import datetime, timezone
import logging
from typing import Optional, Tuple

import discord

from app.freegames.schemas import FreeGameOffer, OfferType
from app.freegames.validator import validate_claim_url_security

logger = logging.getLogger("pbhero.freegames.notifier")

ACCENT_COLOR_NEW = 0x57F287      # Discord green
ACCENT_COLOR_ENDING = 0xFEE75C   # Discord yellow
ACCENT_COLOR_TEST = 0x5865F2     # Discord blurple


def format_offer_type_display(offer_type: str) -> str:
    mapping = {
        OfferType.FREE_TO_KEEP.value: "Free to Keep",
        OfferType.FREE_DLC.value: "Free DLC / Add-on",
        OfferType.FREE_TRIAL.value: "Free Playable Trial",
        OfferType.FREE_TO_PLAY.value: "Free to Play",
    }
    return mapping.get(offer_type, "Free Offer")


def format_price_display(price: Optional[float], currency: str = "USD") -> str:
    if price is None:
        return "N/A"
    if currency == "INR":
        return f"₹{price:,.2f}".rstrip("0").rstrip(".")
    if currency == "EUR":
        return f"€{price:.2f}"
    if currency == "GBP":
        return f"£{price:.2f}"
    return f"${price:.2f}"


def build_offer_embed(
    offer: FreeGameOffer,
    is_ending_soon: bool = False,
    is_test: bool = False,
    show_thumbnail: bool = True,
    show_description: bool = True,
    show_price: bool = True,
    show_expiry: bool = True,
) -> discord.Embed:
    """Build premium Discord embed for a free game offer."""
    if is_test:
        header = "🧪 FREE GAMES TRACKER TEST"
        color = ACCENT_COLOR_TEST
    elif is_ending_soon:
        header = "⚠️ FREE GAME ENDING SOON"
        color = ACCENT_COLOR_ENDING
    else:
        header = "🎁 FREE GAME ALERT"
        color = ACCENT_COLOR_NEW

    target_url = getattr(offer, "canonical_claim_url", None) or offer.claim_url
    embed = discord.Embed(
        title=f"🎮 {offer.title}",
        description=None,
        color=color,
        url=target_url,
    )
    embed.set_author(name=header)

    # Core metadata fields
    embed.add_field(name="🏪 Store", value=offer.store_name, inline=True)
    embed.add_field(name="💻 Platform", value=offer.platform, inline=True)
    embed.add_field(name="⏳ Offer", value=format_offer_type_display(offer.offer_type), inline=True)

    if show_price:
        norm_price = format_price_display(offer.original_price, offer.currency)
        embed.add_field(name="💰 Normal Price", value=norm_price, inline=True)
        embed.add_field(name="🔥 Current Price", value="**FREE** (100% OFF)", inline=True)

    if show_expiry and offer.ends_at:
        # Formatted end date and Discord relative timestamp if available
        ts_int = int(offer.ends_at.replace(tzinfo=timezone.utc).timestamp())
        date_str = offer.ends_at.strftime("%d %B %Y, %H:%M UTC")
        embed.add_field(name="🗓️ Ends", value=f"{date_str} (<t:{ts_int}:R>)", inline=False)
    elif show_expiry:
        embed.add_field(name="🗓️ Ends", value="Limited Time Offer", inline=False)

    if show_description and offer.description:
        desc = offer.description.strip()
        if len(desc) > 350:
            desc = desc[:347] + "..."
        embed.add_field(name="Description", value=desc, inline=False)

    if show_thumbnail and offer.thumbnail_url:
        embed.set_image(url=offer.thumbnail_url)

    embed.set_footer(text="PB HERO FREE GAMES")
    embed.timestamp = datetime.now(timezone.utc)

    return embed


def build_claim_button_view(claim_url: str, source: Optional[str] = None) -> Optional[discord.ui.View]:
    """
    Construct direct claim URL button with strict safety validation.
    Section 29: Assert that label == "🎁 CLAIM GAME", style == ButtonStyle.link, url == claim_url.
    Requirements:
    - Never use raw scraped URL if canonical_claim_url is available
    - Regression assertion: button.url == offer.canonical_claim_url
    """
    is_valid, reason = validate_claim_url_security(claim_url, source)
    if not is_valid:
        logger.error("Claim button construction aborted: %s (URL: %s)", reason, claim_url)
        return None

    view = discord.ui.View(timeout=None)
    btn = discord.ui.Button(
        label="🎁 CLAIM GAME",
        style=discord.ButtonStyle.link,
        url=claim_url,
    )
    view.add_item(btn)
    return view


def prepare_notification_payload(
    offer: FreeGameOffer,
    role_mention_id: Optional[int] = None,
    is_ending_soon: bool = False,
    is_test: bool = False,
    show_thumbnail: bool = True,
    show_description: bool = True,
    show_price: bool = True,
    show_expiry: bool = True,
) -> Tuple[Optional[str], discord.Embed, Optional[discord.ui.View], discord.AllowedMentions]:
    """Prepare content, embed, button view, and allowed mentions for Discord delivery."""
    content = f"<@&{role_mention_id}>" if role_mention_id else None
    mentions = discord.AllowedMentions(roles=True, users=False, everyone=False)

    canonical_url = getattr(offer, "canonical_claim_url", None) or offer.claim_url

    embed = build_offer_embed(
        offer,
        is_ending_soon=is_ending_soon,
        is_test=is_test,
        show_thumbnail=show_thumbnail,
        show_description=show_description,
        show_price=show_price,
        show_expiry=show_expiry,
    )
    view = build_claim_button_view(canonical_url, offer.source)
    return content, embed, view, mentions
