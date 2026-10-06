"""
PB HERO Free Games & Deals Tracker Cog.

Provides Discord slash and prefix commands for managing and inspecting
the automated free games tracker.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.permissions import admin_only, guild_only
from app.config import get_settings
from app.freegames.notifier import build_claim_button_view
from app.freegames.schemas import FreeGameOffer, OfferType
from app.freegames.service import get_freegame_service
from app.freegames.sources import get_all_sources

logger = logging.getLogger("pbhero.bot.freegames")
settings = get_settings()


class FreeGamesCog(commands.Cog, name="FreeGames"):
    """Free Games & Deals Tracker commands and controls."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = get_freegame_service(bot)

    freegames_group = app_commands.Group(
        name="freegames",
        description="PB HERO Free Games & Deals Tracker commands",
    )

    # ─── Slash: /freegames status ───────────────────────────────────────────────

    @freegames_group.command(name="status", description="Check Free Games Tracker operational status")
    @guild_only()
    async def status_slash(self, interaction: discord.Interaction):
        """Display free games tracker health, settings, and stats."""
        await interaction.response.defer(ephemeral=True)
        scheduler = getattr(self.bot, "freegames_scheduler", None)
        cfg = await self.service.get_settings(interaction.guild_id)

        embed = discord.Embed(
            title="🎁 Free Games Tracker Status",
            color=0x57F287 if (scheduler and scheduler.is_healthy) else 0xFEE75C,
        )

        sched_status = "🟢 Running" if (scheduler and scheduler.is_running) else "🔴 Stopped"
        sched_health = "🟢 Healthy" if (scheduler and scheduler.is_healthy) else "🟡 Degraded"
        embed.add_field(name="Scheduler", value=f"{sched_status}\n{sched_health}", inline=True)

        feature_status = "🟢 Enabled" if cfg.enabled else "🔴 Disabled"
        embed.add_field(name="Tracker Master", value=feature_status, inline=True)

        dest_ch_val = f"<#{cfg.destination_channel_id}>" if cfg.destination_channel_id else "*Not configured*"
        embed.add_field(name="Destination Channel", value=dest_ch_val, inline=True)

        # Sources
        try:
            enabled_sources = json.loads(cfg.enabled_sources_json or "[]")
        except Exception:
            enabled_sources = []
        embed.add_field(
            name="Enabled Sources",
            value=", ".join(s.upper() for s in enabled_sources) if enabled_sources else "None",
            inline=True,
        )

        # Polling & Stats
        poll_min = round(cfg.poll_interval_seconds / 60)
        embed.add_field(name="Poll Interval", value=f"{poll_min} minutes ({cfg.poll_interval_seconds}s)", inline=True)

        stats = await self.service.get_stats(interaction.guild_id)
        embed.add_field(
            name="Offers In DB",
            value=f"Active: **{stats.get('active_offers', 0)}**\nTotal: **{stats.get('total_offers', 0)}**\nPosted: **{stats.get('total_notifications', 0)}**",
            inline=True,
        )

        if scheduler and scheduler.last_check:
            ts_str = scheduler.last_check.strftime("%Y-%m-%d %H:%M:%S UTC")
            embed.set_footer(text=f"Last scanned: {ts_str}")
        else:
            embed.set_footer(text="PB HERO Free Games")

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ─── Slash: /freegames latest ───────────────────────────────────────────────

    @freegames_group.command(name="latest", description="View currently active free game offers")
    @guild_only()
    async def latest_slash(self, interaction: discord.Interaction):
        """List active free game offers tracked by PB HERO."""
        await interaction.response.defer(ephemeral=True)
        offers = await self.service.get_active_offers(limit=10)

        if not offers:
            await interaction.followup.send("ℹ️ No active free game offers found currently in database.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎮 Currently Active Free Games",
            description=f"Showing top {len(offers)} active offers:",
            color=0x5865F2,
        )

        for offer in offers:
            ends_str = offer.ends_at.strftime("%d %b %Y") if offer.ends_at else "Limited Time"
            store_badge = offer.store_name
            embed.add_field(
                name=f"🎁 {offer.title}",
                value=f"**Store:** {store_badge} | **Platform:** {offer.platform}\n**Ends:** {ends_str}\n🔗 [Claim Offer]({offer.claim_url})",
                inline=False,
            )

        embed.set_footer(text="PB HERO Free Games")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ─── Slash: /freegames sources ──────────────────────────────────────────────

    @freegames_group.command(name="sources", description="View source adapters health and metrics")
    @guild_only()
    async def sources_slash(self, interaction: discord.Interaction):
        """View health status of all free game sources."""
        await interaction.response.defer(ephemeral=True)
        health_data = await self.service.get_sources_health()

        embed = discord.Embed(
            title="📡 Free Games Source Adapters",
            description="Operational status and metrics for supported store feeds:",
            color=0x5865F2,
        )

        for src in health_data:
            name = src.get("source_name", "Unknown").upper()
            status = src.get("status", "UNKNOWN")
            status_icon = "🟢" if status == "HEALTHY" else ("🟡" if status == "DEGRADED" else "🔴")
            count = src.get("offer_count", 0)
            latency = f"{src.get('response_latency_ms', 0):.1f}ms" if src.get("response_latency_ms") else "N/A"
            failures = src.get("consecutive_failures", 0)

            embed.add_field(
                name=f"{status_icon} {name} ({src.get('category', 'pc').upper()})",
                value=f"Status: **{status}**\nOffers Found: **{count}**\nLatency: **{latency}**\nFailures: **{failures}**",
                inline=True,
            )

        embed.set_footer(text="PB HERO Free Games")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ─── Slash: /freegames sync ─────────────────────────────────────────────────

    @freegames_group.command(name="sync", description="Trigger an immediate scan for free games (Admin)")
    @guild_only()
    @admin_only()
    async def sync_slash(self, interaction: discord.Interaction):
        """Manually trigger offer synchronization across all sources."""
        await interaction.response.defer(ephemeral=True)
        scheduler = getattr(self.bot, "freegames_scheduler", None)
        if scheduler:
            res = await scheduler.trigger_immediate_sync()
        else:
            res = await self.service.sync_offers()

        new_offers = res.get("new_offers", 0)
        total_processed = res.get("processed", 0)
        status_text = res.get("status", "completed")

        embed = discord.Embed(
            title="🔄 Free Games Sync Completed",
            color=0x57F287 if status_text == "completed" else 0xFEE75C,
        )
        embed.add_field(name="Status", value=status_text.capitalize(), inline=True)
        embed.add_field(name="Discovered Offers", value=str(total_processed), inline=True)
        embed.add_field(name="Newly Posted", value=str(new_offers), inline=True)

        sources_summary = res.get("sources", {})
        if sources_summary:
            src_lines = [
                f"• **{k.upper()}**: {'✅' if v.get('success') else '❌'} ({v.get('count', 0)} offers, {v.get('latency_ms', 0):.0f}ms)"
                for k, v in sources_summary.items()
            ]
            embed.add_field(name="Source Breakdown", value="\n".join(src_lines), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ─── Slash: /freegames test ─────────────────────────────────────────────────

    @freegames_group.command(name="test", description="Send a test free game notification with claim button (Admin)")
    @guild_only()
    @admin_only()
    async def test_slash(self, interaction: discord.Interaction):
        """
        Send a test embed to the configured destination channel.
        Section 24: Must NOT create a real offer database record.
        Must contain a safe test claim URL and [ 🎁 CLAIM GAME ] button.
        """
        await interaction.response.defer(ephemeral=True)
        res = await self.service.send_test_notification(interaction.guild_id)

        if res.get("success"):
            embed = discord.Embed(
                title="✅ Test Notification Sent",
                description=f"A test free game notification with `[ 🎁 CLAIM GAME ]` button was dispatched to <#{res.get('channel_id')}>.",
                color=0x57F287,
            )
            embed.add_field(name="Message ID", value=str(res.get("message_id")), inline=True)
            embed.add_field(name="Claim URL", value=res.get("claim_url", ""), inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Test Notification Failed",
                description=f"Error: {res.get('error', 'Unknown failure')}",
                color=0xED4245,
            )
            if "permissions" in res:
                embed.add_field(name="Permissions Detail", value=str(res["permissions"]), inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)

    # ─── Prefix Command Equivalents: !freegames ────────────────────────────────

    @commands.group(name="freegames", invoke_without_command=True)
    async def freegames_prefix(self, ctx: commands.Context):
        """Prefix command for Free Games tracker overview."""
        embed = discord.Embed(
            title="🎁 PB HERO Free Games & Deals Tracker",
            description=(
                "Discover and claim free games from Epic Games, Steam, GOG, Google Play, and App Store.\n\n"
                "**Available Commands:**\n"
                "`!freegames status` — Operational status and settings\n"
                "`!freegames latest` — View active free games\n"
                "`!freegames sources` — Health of game feeds\n"
                "`!freegames sync` — Trigger immediate scan (Admin)\n"
                "`!freegames test` — Send a test notification (Admin)"
            ),
            color=0x5865F2,
        )
        embed.set_footer(text="PB HERO Free Games")
        await ctx.send(embed=embed)

    @freegames_prefix.command(name="status")
    async def status_prefix(self, ctx: commands.Context):
        """Prefix: Check free games status."""
        scheduler = getattr(self.bot, "freegames_scheduler", None)
        cfg = await self.service.get_settings(ctx.guild.id if ctx.guild else None)

        embed = discord.Embed(title="🎁 Free Games Tracker Status", color=0x57F287)
        sched_status = "🟢 Running" if (scheduler and scheduler.is_running) else "🔴 Stopped"
        embed.add_field(name="Scheduler", value=sched_status, inline=True)
        embed.add_field(name="Enabled", value="Yes" if cfg.enabled else "No", inline=True)
        dest_ch_val = f"<#{cfg.destination_channel_id}>" if cfg.destination_channel_id else "None"
        embed.add_field(name="Channel", value=dest_ch_val, inline=True)
        await ctx.send(embed=embed)

    @freegames_prefix.command(name="latest")
    async def latest_prefix(self, ctx: commands.Context):
        """Prefix: View latest active free games."""
        offers = await self.service.get_active_offers(limit=5)
        if not offers:
            return await ctx.send("ℹ️ No active free game offers currently available.")

        embed = discord.Embed(title="🎮 Active Free Games", color=0x5865F2)
        for o in offers:
            embed.add_field(
                name=f"🎁 {o.title}",
                value=f"**Store:** {o.store_name} | **Platform:** {o.platform}\n🔗 [Claim]({o.claim_url})",
                inline=False,
            )
        await ctx.send(embed=embed)

    @freegames_prefix.command(name="sync")
    async def sync_prefix(self, ctx: commands.Context):
        """Prefix: Trigger immediate sync (Admin only)."""
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send("❌ Administrator permissions required.")

        msg = await ctx.send("🔄 Scanning game sources...")
        res = await self.service.sync_offers()
        await msg.edit(content=f"✅ Sync complete: **{res.get('new_offers', 0)}** new offers posted.")

    @freegames_prefix.command(name="test")
    async def test_prefix(self, ctx: commands.Context):
        """Prefix: Send test notification (Admin only)."""
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send("❌ Administrator permissions required.")

        res = await self.service.send_test_notification(ctx.guild.id if ctx.guild else None)
        if res.get("success"):
            await ctx.send(f"✅ Test notification sent to <#{res.get('channel_id')}>!")
        else:
            await ctx.send(f"❌ Test failed: {res.get('error')}")


async def setup(bot: commands.Bot):
    """Setup FreeGames cog."""
    await bot.add_cog(FreeGamesCog(bot))
