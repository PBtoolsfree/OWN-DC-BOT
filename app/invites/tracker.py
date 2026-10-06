"""
PB HERO Discord Invite Tracking & Attribution Service.

Production-grade invite tracking, caching, reconciliation, concurrency control,
and join attribution for the single-server PB HERO Discord Bot.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import discord
from discord.ext import commands

from app.config import get_settings
from app.database.engine import get_session_direct
from app.database.models import InviteJoin
from app.database.repositories import (
    DiscordInviteRepo,
    InviteActivitySettingsRepo,
    InviteJoinRepo,
    ServerConfigRepo,
    ServerInviteSettingsRepo,
)

logger = logging.getLogger("pbhero.invites.tracker")
settings = get_settings()


@dataclass
class CachedInvite:
    """In-memory cached representation of an active Discord guild invite."""
    guild_id: int
    invite_code: str
    inviter_id: Optional[int]
    inviter_name: str
    channel_id: Optional[int]
    channel_name: str
    uses: int
    max_uses: int
    max_age: int
    temporary: bool
    created_at: Optional[datetime]
    revoked: bool
    last_seen_at: datetime
    is_vanity: bool = False
    is_permanent_config: bool = False


@dataclass
class AttributionResult:
    """Result of an invite attribution for a member join event."""
    member_id: int
    member_name: str
    invite_code: Optional[str]
    inviter_id: Optional[int]
    inviter_name: Optional[str]
    source_type: str  # NORMAL_INVITE, VANITY_URL, UNKNOWN, SYSTEM
    channel_id: Optional[int]
    channel_name: Optional[str]
    joined_at: datetime
    is_ambiguous: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


class InviteTracker:
    """
    Centralized Invite Tracking Engine for PB HERO.

    Maintains in-memory cache, performs serialized join attribution with
    delta reconciliation, handles vanity URLs, and logs events to Discord.
    """

    def __init__(self, bot: Optional[commands.Bot] = None):
        self.bot = bot
        self.guild_id = settings.DISCORD_GUILD_ID
        self._cache: Dict[str, CachedInvite] = {}
        self._lock = asyncio.Lock()
        self._recent_joins: Dict[int, float] = {}  # member_id -> timestamp for debouncing
        self._last_sync_at: Optional[datetime] = None
        self._last_attribution_at: Optional[datetime] = None
        self._sync_status: str = "UNINITIALIZED"
        self._sync_error: Optional[str] = None
        self._permission_status: Dict[str, Any] = {
            "has_manage_guild": False,
            "can_read_invites": False,
            "intents_ok": False,
            "details": "Tracker not initialized",
        }

    def set_bot(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ========================================================
    # Permissions and Gateway Checks
    # ========================================================

    def verify_permissions(self) -> Tuple[bool, Dict[str, Any]]:
        """Verify required Discord permissions and gateway intents."""
        if not self.bot or not self.bot.is_ready():
            res = {
                "has_manage_guild": False,
                "can_read_invites": False,
                "intents_ok": False,
                "details": "Discord bot is offline or not ready.",
            }
            self._permission_status = res
            return False, res

        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            res = {
                "has_manage_guild": False,
                "can_read_invites": False,
                "intents_ok": False,
                "details": f"Configured guild {self.guild_id} not found in bot session.",
            }
            self._permission_status = res
            return False, res

        me = guild.me
        if not me:
            res = {
                "has_manage_guild": False,
                "can_read_invites": False,
                "intents_ok": False,
                "details": "Bot guild member object unavailable.",
            }
            self._permission_status = res
            return False, res

        perms = me.guild_permissions
        has_manage_guild = bool(perms.manage_guild or perms.administrator)
        can_read = has_manage_guild  # Discord requires Manage Server or Admin to inspect guild invites
        intents_ok = bool(getattr(self.bot.intents, "members", False))

        details = "Permissions verified."
        if not can_read:
            details = "Bot lacks 'Manage Server' permission to read guild invites."
        elif not intents_ok:
            details = "Server Members Gateway Intent is disabled."

        res = {
            "has_manage_guild": has_manage_guild,
            "can_read_invites": can_read,
            "intents_ok": intents_ok,
            "details": details,
        }
        self._permission_status = res
        return (can_read and intents_ok), res

    # ========================================================
    # Startup Sync & Reconciliation
    # ========================================================

    async def sync_invites(self, force: bool = False) -> Dict[str, Any]:
        """
        Synchronize Discord guild invites with in-memory cache and database.

        CRITICAL: Does NOT count historical uses as joins.
        """
        async with self._lock:
            if not self.bot or not self.bot.is_ready():
                self._sync_status = "DEGRADED"
                self._sync_error = "Bot is currently offline"
                return {
                    "status": "DEGRADED",
                    "error": self._sync_error,
                    "tracked_invites": len(self._cache),
                }

            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                self._sync_status = "ERROR"
                self._sync_error = f"Guild {self.guild_id} not found"
                return {
                    "status": "ERROR",
                    "error": self._sync_error,
                    "tracked_invites": len(self._cache),
                }

            can_read, perm_info = self.verify_permissions()
            if not can_read:
                self._sync_status = "DEGRADED"
                self._sync_error = perm_info.get("details")
                logger.warning("Invite tracking degraded: %s", self._sync_error)
                return {
                    "status": "DEGRADED",
                    "error": self._sync_error,
                    "tracked_invites": len(self._cache),
                }

            # Check permanent invite configured in database
            session = await get_session_direct()
            perm_code = None
            try:
                perm_row = await ServerInviteSettingsRepo.get(session, self.guild_id)
                if perm_row and perm_row.invite_code:
                    perm_code = perm_row.invite_code
            except Exception as e:
                logger.warning("Failed to fetch permanent invite config: %s", e)
            finally:
                await session.close()

            # Fetch fresh guild invites from Discord
            try:
                discord_invites: List[discord.Invite] = await guild.invites()
            except discord.Forbidden:
                self._sync_status = "DEGRADED"
                self._sync_error = "Discord rejected invite fetch: Missing 'Manage Server' permission"
                logger.error(self._sync_error)
                return {
                    "status": "DEGRADED",
                    "error": self._sync_error,
                    "tracked_invites": len(self._cache),
                }
            except Exception as e:
                self._sync_status = "ERROR"
                self._sync_error = f"Failed to fetch invites from Discord: {e}"
                logger.exception("Error syncing guild invites: %s", e)
                return {
                    "status": "ERROR",
                    "error": self._sync_error,
                    "tracked_invites": len(self._cache),
                }

            # Fetch vanity invite if server has vanity feature
            vanity_invite = None
            if "VANITY_URL" in guild.features:
                try:
                    vanity_invite = await guild.vanity_invite()
                except Exception as e:
                    logger.debug("Guild has vanity feature but vanity_invite() call failed: %s", e)

            now = datetime.now(timezone.utc)
            now_naive = datetime.utcnow()
            active_codes: Set[str] = set()

            session = await get_session_direct()
            try:
                for inv in discord_invites:
                    active_codes.add(inv.code)
                    inviter_id = inv.inviter.id if inv.inviter else None
                    inviter_name = str(inv.inviter) if inv.inviter else "Unknown"

                    is_perm = bool(perm_code and inv.code == perm_code)
                    if is_perm:
                        inviter_name = "PB HERO SERVER"

                    channel_id = inv.channel.id if inv.channel else None
                    channel_name = getattr(inv.channel, "name", "unknown") if inv.channel else "unknown"

                    # Calculate status
                    status = "ACTIVE"
                    if inv.max_uses and inv.uses >= inv.max_uses:
                        status = "MAX_USES_REACHED"
                    elif getattr(inv, "expires_at", None) and inv.expires_at < now:
                        status = "EXPIRED"

                    # Update in-memory cache
                    self._cache[inv.code] = CachedInvite(
                        guild_id=self.guild_id,
                        invite_code=inv.code,
                        inviter_id=inviter_id,
                        inviter_name=inviter_name,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        uses=inv.uses or 0,
                        max_uses=inv.max_uses or 0,
                        max_age=inv.max_age or 0,
                        temporary=bool(inv.temporary),
                        created_at=inv.created_at,
                        revoked=False,
                        last_seen_at=now,
                        is_vanity=False,
                        is_permanent_config=is_perm,
                    )

                    # Persist in DB (WITHOUT creating joins)
                    await DiscordInviteRepo.upsert(
                        session,
                        guild_id=self.guild_id,
                        invite_code=inv.code,
                        inviter_id=inviter_id,
                        inviter_name=inviter_name,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        uses=inv.uses or 0,
                        max_uses=inv.max_uses or 0,
                        max_age=inv.max_age or 0,
                        temporary=bool(inv.temporary),
                        status=status,
                        last_seen_at=now_naive,
                        is_vanity=False,
                        is_permanent_config=is_perm,
                    )

                # Process vanity URL if present
                if vanity_invite:
                    active_codes.add(vanity_invite.code)
                    self._cache[vanity_invite.code] = CachedInvite(
                        guild_id=self.guild_id,
                        invite_code=vanity_invite.code,
                        inviter_id=None,
                        inviter_name="Vanity URL / Server",
                        channel_id=vanity_invite.channel.id if vanity_invite.channel else None,
                        channel_name=getattr(vanity_invite.channel, "name", "vanity") if vanity_invite.channel else "vanity",
                        uses=vanity_invite.uses or 0,
                        max_uses=0,
                        max_age=0,
                        temporary=False,
                        created_at=vanity_invite.created_at,
                        revoked=False,
                        last_seen_at=now,
                        is_vanity=True,
                        is_permanent_config=False,
                    )
                    await DiscordInviteRepo.upsert(
                        session,
                        guild_id=self.guild_id,
                        invite_code=vanity_invite.code,
                        inviter_id=None,
                        inviter_name="Vanity URL / Server",
                        channel_id=vanity_invite.channel.id if vanity_invite.channel else None,
                        channel_name=getattr(vanity_invite.channel, "name", "vanity") if vanity_invite.channel else "vanity",
                        uses=vanity_invite.uses or 0,
                        max_uses=0,
                        max_age=0,
                        temporary=False,
                        status="ACTIVE",
                        last_seen_at=now_naive,
                        is_vanity=True,
                        is_permanent_config=False,
                    )

                # Identify cached invites no longer present in Discord
                for code, cached in list(self._cache.items()):
                    if code not in active_codes and not cached.revoked:
                        cached.revoked = True
                        new_status = "REVOKED"
                        if cached.max_uses and cached.uses >= cached.max_uses:
                            new_status = "MAX_USES_REACHED"
                        await DiscordInviteRepo.upsert(
                            session,
                            guild_id=self.guild_id,
                            invite_code=code,
                            status=new_status,
                            revoked_at=now_naive if new_status == "REVOKED" else None,
                            last_seen_at=now_naive,
                        )

                await session.commit()
                self._last_sync_at = now
                self._sync_status = "HEALTHY"
                self._sync_error = None
                logger.info(
                    "Invite tracking startup sync complete: %d active invites tracked (guild %d)",
                    len(active_codes),
                    self.guild_id,
                )
            except Exception as e:
                logger.exception("Error persisting invite sync: %s", e)
                self._sync_status = "ERROR"
                self._sync_error = str(e)
            finally:
                await session.close()

            return {
                "status": self._sync_status,
                "error": self._sync_error,
                "tracked_invites": len(self._cache),
                "active_invites": len(active_codes),
                "last_sync": self._last_sync_at.isoformat() if self._last_sync_at else None,
            }

    # ========================================================
    # Member Join Attribution Pipeline
    # ========================================================

    async def attribute_member_join(self, member: discord.Member) -> AttributionResult:
        """
        Execute reliable join attribution when on_member_join triggers.

        Uses async lock to serialize concurrent joins and accurately compute
        deltas. Handles unknown, vanity, and permanent invites safely.
        """
        now = datetime.now(timezone.utc)
        now_naive = datetime.utcnow()

        # Deduplication check: ignore duplicate join events within 60s
        member_id = member.id
        last_seen = self._recent_joins.get(member_id)
        if last_seen and (time.time() - last_seen) < 60.0:
            logger.info("Ignoring duplicate join attribution for member %s (%d)", member, member_id)
            return AttributionResult(
                member_id=member_id,
                member_name=str(member),
                invite_code=None,
                inviter_id=None,
                inviter_name=None,
                source_type="UNKNOWN",
                channel_id=None,
                channel_name=None,
                joined_at=now_naive,
                is_ambiguous=False,
                details={"reason": "duplicate_event_debounce"},
            )

        self._recent_joins[member_id] = time.time()
        # Clean up old recent joins cache (> 300s)
        old_cutoff = time.time() - 300.0
        self._recent_joins = {mid: ts for mid, ts in self._recent_joins.items() if ts > old_cutoff}

        async with self._lock:
            self._last_attribution_at = now
            guild = member.guild

            if not self.bot or not self.bot.is_ready() or not guild:
                return await self._record_unknown_join(
                    member, "Bot not ready or guild missing", now_naive
                )

            can_read, _ = self.verify_permissions()
            if not can_read:
                return await self._record_unknown_join(
                    member, "Missing Discord permissions to inspect invites", now_naive
                )

            # Check configured server permanent invite
            session = await get_session_direct()
            perm_code = None
            try:
                perm_row = await ServerInviteSettingsRepo.get(session, guild.id)
                if perm_row and perm_row.invite_code:
                    perm_code = perm_row.invite_code
            except Exception as e:
                logger.warning("Failed to fetch permanent invite config: %s", e)
            finally:
                await session.close()

            # Fetch fresh guild invites
            try:
                fresh_invites = await guild.invites()
            except Exception as e:
                logger.warning("Failed to fetch fresh invites during member join: %s", e)
                return await self._record_unknown_join(
                    member, f"Discord API error: {e}", now_naive
                )

            fresh_vanity = None
            if "VANITY_URL" in guild.features:
                try:
                    fresh_vanity = await guild.vanity_invite()
                except Exception:
                    fresh_vanity = None

            fresh_map = {inv.code: inv for inv in fresh_invites}
            if fresh_vanity:
                fresh_map[fresh_vanity.code] = fresh_vanity

            # Calculate Deltas
            delta_candidates: List[Tuple[Any, int, bool]] = []
            # (invite_obj, delta_uses, is_vanity)

            for code, fresh_inv in fresh_map.items():
                is_vanity = (fresh_vanity is not None and code == fresh_vanity.code)
                cached = self._cache.get(code)
                if cached is None:
                    # New invite created and used
                    if (fresh_inv.uses or 0) > 0:
                        delta_candidates.append((fresh_inv, fresh_inv.uses or 0, is_vanity))
                else:
                    delta = (fresh_inv.uses or 0) - cached.uses
                    if delta > 0:
                        delta_candidates.append((fresh_inv, delta, is_vanity))

            # Check if any invite disappeared (e.g. max_uses reached)
            for cached_code, cached_inv in self._cache.items():
                if cached_code not in fresh_map and not cached_inv.revoked:
                    if cached_inv.max_uses > 0 and cached_inv.uses == (cached_inv.max_uses - 1):
                        delta_candidates.append((cached_inv, 1, cached_inv.is_vanity))

            chosen_code: Optional[str] = None
            chosen_inviter_id: Optional[int] = None
            chosen_inviter_name: Optional[str] = None
            chosen_channel_id: Optional[int] = None
            chosen_channel_name: Optional[str] = None
            source_type = "UNKNOWN"
            is_ambiguous = False

            if len(delta_candidates) == 1:
                # Exactly one candidate matched!
                target_obj, delta, is_vanity = delta_candidates[0]
                chosen_code = getattr(target_obj, "code", None) or getattr(target_obj, "invite_code", None)

                if is_vanity:
                    source_type = "VANITY_URL"
                    chosen_inviter_id = None
                    chosen_inviter_name = "Vanity URL / Server"
                    chosen_channel_id = getattr(getattr(target_obj, "channel", None), "id", None)
                    chosen_channel_name = getattr(getattr(target_obj, "channel", None), "name", "vanity")
                else:
                    is_perm = bool(perm_code and chosen_code == perm_code)
                    if is_perm:
                        source_type = "NORMAL_INVITE"
                        chosen_inviter_id = None
                        chosen_inviter_name = "PB HERO SERVER"
                        chosen_channel_id = getattr(getattr(target_obj, "channel", None), "id", None)
                        chosen_channel_name = getattr(getattr(target_obj, "channel", None), "name", None)
                    else:
                        source_type = "NORMAL_INVITE"
                        inviter = getattr(target_obj, "inviter", None)
                        if inviter:
                            chosen_inviter_id = inviter.id
                            chosen_inviter_name = str(inviter)
                        else:
                            cached_record = self._cache.get(chosen_code)
                            chosen_inviter_id = cached_record.inviter_id if cached_record else None
                            chosen_inviter_name = cached_record.inviter_name if cached_record else "Unknown"

                        chosen_channel = getattr(target_obj, "channel", None)
                        chosen_channel_id = chosen_channel.id if chosen_channel else None
                        chosen_channel_name = getattr(chosen_channel, "name", None) if chosen_channel else None

                # For delta > 1, update cached uses by +1 so next concurrent join consumes the remainder
                cached = self._cache.get(chosen_code)
                if cached:
                    cached.uses += 1
                    cached.last_seen_at = now
            elif len(delta_candidates) > 1:
                # Multiple invites increased simultaneously: ambiguous!
                is_ambiguous = True
                source_type = "UNKNOWN"
                logger.warning(
                    "Ambiguous join attribution for %s: %d invites increased uses simultaneously: %s",
                    member,
                    len(delta_candidates),
                    [getattr(c[0], "code", getattr(c[0], "invite_code", "??")) for c in delta_candidates],
                )
            else:
                # No invite increased uses (e.g. widget, integration, bot, or untracked join)
                source_type = "UNKNOWN"
                logger.info("Join source could not be identified for %s: no invite usage delta", member)

            # Reconcile all fresh invites into cache and DB
            session = await get_session_direct()
            try:
                for code, fresh_inv in fresh_map.items():
                    is_vanity = (fresh_vanity is not None and code == fresh_vanity.code)
                    is_perm = bool(perm_code and code == perm_code)
                    inviter = getattr(fresh_inv, "inviter", None)
                    inviter_name = "PB HERO SERVER" if is_perm else (str(inviter) if inviter else "Unknown")
                    inviter_id = None if (is_vanity or is_perm) else (inviter.id if inviter else None)
                    chan = getattr(fresh_inv, "channel", None)
                    chan_id = chan.id if chan else None
                    chan_name = getattr(chan, "name", "unknown") if chan else "unknown"

                    cached = self._cache.get(code)
                    new_uses = fresh_inv.uses or 0
                    if cached and cached.uses > new_uses:
                        # Retain incremented uses if we advanced it for a concurrent join
                        new_uses = cached.uses

                    status = "ACTIVE"
                    if getattr(fresh_inv, "max_uses", 0) and new_uses >= fresh_inv.max_uses:
                        status = "MAX_USES_REACHED"

                    self._cache[code] = CachedInvite(
                        guild_id=guild.id,
                        invite_code=code,
                        inviter_id=inviter_id,
                        inviter_name=inviter_name,
                        channel_id=chan_id,
                        channel_name=chan_name,
                        uses=new_uses,
                        max_uses=getattr(fresh_inv, "max_uses", 0) or 0,
                        max_age=getattr(fresh_inv, "max_age", 0) or 0,
                        temporary=bool(getattr(fresh_inv, "temporary", False)),
                        created_at=getattr(fresh_inv, "created_at", None),
                        revoked=False,
                        last_seen_at=now,
                        is_vanity=is_vanity,
                        is_permanent_config=is_perm,
                    )

                    await DiscordInviteRepo.upsert(
                        session,
                        guild_id=guild.id,
                        invite_code=code,
                        inviter_id=inviter_id,
                        inviter_name=inviter_name,
                        channel_id=chan_id,
                        channel_name=chan_name,
                        uses=new_uses,
                        max_uses=getattr(fresh_inv, "max_uses", 0) or 0,
                        max_age=getattr(fresh_inv, "max_age", 0) or 0,
                        temporary=bool(getattr(fresh_inv, "temporary", False)),
                        status=status,
                        last_seen_at=now_naive,
                        is_vanity=is_vanity,
                        is_permanent_config=is_perm,
                    )

                # Persist join attribution record
                join_record = await InviteJoinRepo.record_join(
                    session,
                    guild_id=guild.id,
                    member_id=member.id,
                    member_name=str(member),
                    invite_code=chosen_code,
                    inviter_id=chosen_inviter_id,
                    inviter_name=chosen_inviter_name,
                    source_type=source_type,
                    channel_id=chosen_channel_id,
                    channel_name=chosen_channel_name,
                    joined_at=now_naive,
                )
                join_record_id = join_record.id if join_record else None
                await session.commit()
            except Exception as e:
                logger.exception("Failed to persist join attribution in database: %s", e)
                join_record_id = None
            finally:
                await session.close()

            result = AttributionResult(
                member_id=member.id,
                member_name=str(member),
                invite_code=chosen_code,
                inviter_id=chosen_inviter_id,
                inviter_name=chosen_inviter_name,
                source_type=source_type,
                channel_id=chosen_channel_id,
                channel_name=chosen_channel_name,
                joined_at=now_naive,
                is_ambiguous=is_ambiguous,
            )

            # Dispatch Discord moderation log embed if configured
            try:
                await self._dispatch_join_log(member, result)
            except Exception as e:
                logger.warning("Failed to send invite join log embed: %s", e)

            # Dispatch Dedicated Discord Invite Activity Log
            try:
                await self._dispatch_activity_log(member, result, join_record_id=join_record_id)
            except Exception as e:
                logger.warning("Failed to send dedicated invite activity embed: %s", e)

            return result

    async def _record_unknown_join(
        self, member: discord.Member, reason: str, joined_at: datetime
    ) -> AttributionResult:
        """Record join with UNKNOWN attribution."""
        join_record_id = None
        session = await get_session_direct()
        try:
            join_record = await InviteJoinRepo.record_join(
                session,
                guild_id=member.guild.id,
                member_id=member.id,
                member_name=str(member),
                invite_code=None,
                inviter_id=None,
                inviter_name=None,
                source_type="UNKNOWN",
                channel_id=None,
                channel_name=None,
                joined_at=joined_at,
            )
            join_record_id = join_record.id if join_record else None
            await session.commit()
        except Exception as e:
            logger.warning("Failed to store unknown join record: %s", e)
        finally:
            await session.close()

        res = AttributionResult(
            member_id=member.id,
            member_name=str(member),
            invite_code=None,
            inviter_id=None,
            inviter_name=None,
            source_type="UNKNOWN",
            channel_id=None,
            channel_name=None,
            joined_at=joined_at,
            is_ambiguous=False,
            details={"reason": reason},
        )
        try:
            await self._dispatch_join_log(member, res)
        except Exception:
            pass

        # Dispatch Dedicated Discord Invite Activity Log
        try:
            await self._dispatch_activity_log(member, res, join_record_id=join_record_id)
        except Exception as e:
            logger.warning("Failed to send dedicated unknown invite activity embed: %s", e)

        return res

    # ========================================================
    # Member Leave Tracking
    # ========================================================

    async def handle_member_leave(
        self, member: Union[discord.Member, discord.User], guild_id: Optional[int] = None
    ) -> None:
        """
        Record member leave while PRESERVING original historical attribution.

        Updates is_still_member=False so analytics can report current vs former referrals.
        """
        target_guild_id = (
            guild_id
            or (getattr(member, "guild", None).id if getattr(member, "guild", None) else None)
            or self.guild_id
        )
        user_id = getattr(member, "id", None)
        if not user_id or not target_guild_id:
            return

        session = await get_session_direct()
        try:
            await InviteJoinRepo.record_leave(session, target_guild_id, user_id)
            await session.commit()
            logger.info("Recorded member leave for invite attribution history: %s (%d)", member, user_id)
        except Exception as e:
            logger.warning("Failed to record member leave in invite tracker: %s", e)
        finally:
            await session.close()

    # ========================================================
    # Invite Lifecycle Events (Create / Delete)
    # ========================================================

    async def handle_invite_create(self, invite: discord.Invite) -> None:
        """Handle on_invite_create event."""
        if not invite.guild or invite.guild.id != self.guild_id:
            return

        now = datetime.now(timezone.utc)
        now_naive = datetime.utcnow()
        inviter_id = invite.inviter.id if invite.inviter else None
        inviter_name = str(invite.inviter) if invite.inviter else "Unknown"
        channel_id = invite.channel.id if invite.channel else None
        channel_name = getattr(invite.channel, "name", "unknown") if invite.channel else "unknown"

        self._cache[invite.code] = CachedInvite(
            guild_id=self.guild_id,
            invite_code=invite.code,
            inviter_id=inviter_id,
            inviter_name=inviter_name,
            channel_id=channel_id,
            channel_name=channel_name,
            uses=invite.uses or 0,
            max_uses=invite.max_uses or 0,
            max_age=invite.max_age or 0,
            temporary=bool(invite.temporary),
            created_at=invite.created_at or now,
            revoked=False,
            last_seen_at=now,
        )

        session = await get_session_direct()
        try:
            await DiscordInviteRepo.upsert(
                session,
                guild_id=self.guild_id,
                invite_code=invite.code,
                inviter_id=inviter_id,
                inviter_name=inviter_name,
                channel_id=channel_id,
                channel_name=channel_name,
                uses=invite.uses or 0,
                max_uses=invite.max_uses or 0,
                max_age=invite.max_age or 0,
                temporary=bool(invite.temporary),
                status="ACTIVE",
                last_seen_at=now_naive,
            )
            await session.commit()
            logger.info("Recorded invite creation for %s by %s", invite.code, inviter_name)
        except Exception as e:
            logger.warning("Failed to persist invite creation for %s: %s", invite.code, e)
        finally:
            await session.close()

        # Discord Mod Log
        try:
            await self._dispatch_lifecycle_log("invite_create", invite)
        except Exception as e:
            logger.warning("Failed to dispatch invite_create log: %s", e)

        # Dedicated Invite Activity Log
        try:
            await self._dispatch_activity_lifecycle("invite_create", invite)
        except Exception as e:
            logger.warning("Failed to dispatch activity invite_create: %s", e)

    async def handle_invite_delete(self, invite: discord.Invite) -> None:
        """Handle on_invite_delete event. Marks revoked, preserves history."""
        if not invite.guild or invite.guild.id != self.guild_id:
            return

        cached = self._cache.get(invite.code)
        if cached:
            cached.revoked = True

        session = await get_session_direct()
        try:
            await DiscordInviteRepo.mark_revoked(session, invite.code)
            await session.commit()
            logger.info("Recorded invite revocation for %s (preserved historical joins)", invite.code)
        except Exception as e:
            logger.warning("Failed to mark invite %s as revoked: %s", invite.code, e)
        finally:
            await session.close()

        # Discord Mod Log
        try:
            await self._dispatch_lifecycle_log("invite_revoke", invite)
        except Exception as e:
            logger.warning("Failed to dispatch invite_revoke log: %s", e)

        # Dedicated Invite Activity Log
        try:
            await self._dispatch_activity_lifecycle("invite_revoke", invite)
        except Exception as e:
            logger.warning("Failed to dispatch activity invite_revoke: %s", e)

    # ========================================================
    # Administrative Actions (Revoke)
    # ========================================================

    async def revoke_invite(self, invite_code: str) -> Dict[str, Any]:
        """Revoke an invite via Discord API and update database."""
        if not self.bot or not self.bot.is_ready():
            raise RuntimeError("Bot is offline; cannot contact Discord to delete invite.")

        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            raise RuntimeError(f"Configured guild {self.guild_id} not available.")

        # Try to find invite on Discord and delete it
        deleted_from_discord = False
        try:
            invites = await guild.invites()
            target = next((i for i in invites if i.code == invite_code), None)
            if target:
                await target.delete(reason="Revoked via PB HERO Invite Management")
                deleted_from_discord = True
            else:
                # Try fetching directly
                try:
                    fetched = await self.bot.fetch_invite(invite_code)
                    await fetched.delete(reason="Revoked via PB HERO Invite Management")
                    deleted_from_discord = True
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Could not delete invite %s directly on Discord: %s", invite_code, e)

        # Mark revoked in cache and database
        cached = self._cache.get(invite_code)
        if cached:
            cached.revoked = True

        session = await get_session_direct()
        try:
            await DiscordInviteRepo.mark_revoked(session, invite_code)
            await session.commit()
        finally:
            await session.close()

        return {
            "success": True,
            "invite_code": invite_code,
            "deleted_from_discord": deleted_from_discord,
            "status": "REVOKED",
        }

    # ========================================================
    # Diagnostics & Health
    # ========================================================

    def get_health(self) -> Dict[str, Any]:
        """Get real-time diagnostics and status for dashboard."""
        can_read, perms = self.verify_permissions()
        status = "HEALTHY"
        if not self.bot or not self.bot.is_ready():
            status = "DEGRADED"
        elif not can_read:
            status = "DEGRADED"
        elif self._sync_status == "ERROR":
            status = "ERROR"

        return {
            "status": status,
            "sync_status": self._sync_status,
            "sync_error": self._sync_error,
            "last_sync": self._last_sync_at.isoformat() if self._last_sync_at else None,
            "last_attribution": self._last_attribution_at.isoformat() if self._last_attribution_at else None,
            "tracked_invites_cached": len(self._cache),
            "permissions": perms,
        }

    # ========================================================
    # Discord Mod Logging Helpers
    # ========================================================

    async def _get_mod_log_channel(self) -> Optional[discord.TextChannel]:
        if not self.bot or not self.bot.is_ready():
            return None
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return None

        session = await get_session_direct()
        try:
            config = await ServerConfigRepo.get_or_create(session)
            if not config.mod_log_channel_id:
                return None
            channel = guild.get_channel(int(config.mod_log_channel_id))
            if not isinstance(channel, discord.TextChannel):
                return None

            # Check permissions
            me = guild.me
            if me:
                perms = channel.permissions_for(me)
                if not (perms.view_channel and perms.send_messages and perms.embed_links):
                    return None
            return channel
        finally:
            await session.close()

    async def _is_event_enabled(self, event_name: str) -> bool:
        session = await get_session_direct()
        try:
            config = await ServerConfigRepo.get_or_create(session)
            events_json = getattr(config, "mod_log_events", None)
            if not events_json:
                return True
            try:
                events = json.loads(events_json) if isinstance(events_json, str) else events_json
                return event_name in events
            except Exception:
                return True
        finally:
            await session.close()

    async def _dispatch_join_log(
        self, member: discord.Member, result: AttributionResult
    ) -> None:
        """Send rich embed to moderation log channel when a member joins."""
        if not await self._is_event_enabled("invite_join"):
            return

        channel = await self._get_mod_log_channel()
        if not channel:
            return

        if result.source_type == "NORMAL_INVITE":
            embed = discord.Embed(
                title="✅ Member Joined via Invite",
                color=0x2ECC71,  # Green
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Member", value=f"{member.mention} (`{member.name}` / `{member.id}`)", inline=False)
            inviter_str = f"<@{result.inviter_id}> (`{result.inviter_name}`)" if result.inviter_id else (result.inviter_name or "Unknown")
            embed.add_field(name="Inviter", value=inviter_str, inline=True)
            embed.add_field(name="Invite Code", value=f"`{result.invite_code}`", inline=True)
            chan_str = f"<#{result.channel_id}>" if result.channel_id else (result.channel_name or "Unknown")
            embed.add_field(name="Channel", value=chan_str, inline=True)
            if getattr(member, "display_avatar", None):
                embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="PB HERO Invite Tracker")
            await channel.send(embed=embed)

        elif result.source_type == "VANITY_URL":
            embed = discord.Embed(
                title="🔗 Member Joined via Vanity URL",
                color=0x3498DB,  # Blue
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Member", value=f"{member.mention} (`{member.name}` / `{member.id}`)", inline=False)
            embed.add_field(name="Source", value="Server Vanity URL", inline=True)
            embed.add_field(name="Invite Code", value=f"`{result.invite_code}`", inline=True)
            if getattr(member, "display_avatar", None):
                embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="PB HERO Invite Tracker")
            await channel.send(embed=embed)

        else:
            embed = discord.Embed(
                title="⚠️ Member Joined",
                description="Join could not be reliably attributed to a specific active invite.",
                color=0xE67E22,  # Amber
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Member", value=f"{member.mention} (`{member.name}` / `{member.id}`)", inline=False)
            embed.add_field(name="Invite", value="Unknown", inline=True)
            embed.add_field(name="Source", value="UNKNOWN", inline=True)
            if getattr(member, "display_avatar", None):
                embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="PB HERO Invite Tracker")
            await channel.send(embed=embed)

    async def _dispatch_lifecycle_log(self, event_type: str, invite: discord.Invite) -> None:
        """Send embed for invite create / delete."""
        if not await self._is_event_enabled(event_type):
            return

        channel = await self._get_mod_log_channel()
        if not channel:
            return

        inviter_str = f"{invite.inviter.mention} (`{invite.inviter}`)" if invite.inviter else "System / Unknown"
        chan_str = f"{invite.channel.mention}" if invite.channel else "Unknown"

        if event_type == "invite_create":
            embed = discord.Embed(
                title="➕ Server Invite Created",
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Invite Code", value=f"`{invite.code}`", inline=True)
            embed.add_field(name="Created By", value=inviter_str, inline=True)
            embed.add_field(name="Target Channel", value=chan_str, inline=True)
            max_uses_str = str(invite.max_uses) if invite.max_uses else "Unlimited"
            max_age_str = f"{invite.max_age}s" if invite.max_age else "Never"
            embed.add_field(name="Max Uses", value=max_uses_str, inline=True)
            embed.add_field(name="Expires", value=max_age_str, inline=True)
            embed.set_footer(text="PB HERO Invite Tracker")
            await channel.send(embed=embed)

        elif event_type == "invite_revoke":
            embed = discord.Embed(
                title="🗑️ Server Invite Revoked / Deleted",
                color=0xED4245,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="Invite Code", value=f"`{invite.code}`", inline=True)
            embed.add_field(name="Channel", value=chan_str, inline=True)
            embed.add_field(name="Status", value="REVOKED (joins preserved)", inline=True)
            embed.set_footer(text="PB HERO Invite Tracker")
            await channel.send(embed=embed)

    # ========================================================
    # Dedicated Discord Invite Activity Logging
    # ========================================================

    @staticmethod
    def _safe_format_template(template_str: str, format_vars: Dict[str, Any]) -> str:
        """Safely format a template string by replacing {variable} tags."""
        res = template_str or ""
        for k, v in format_vars.items():
            res = res.replace(f"{{{k}}}", str(v))
        return res

    async def get_activity_diagnostics(self) -> Dict[str, Any]:
        """Check status and permissions of configured invite activity channel."""
        session = await get_session_direct()
        try:
            cfg = await InviteActivitySettingsRepo.get_or_create(session, self.guild_id)
            if not cfg.enabled or not cfg.channel_id:
                return {
                    "enabled": bool(cfg.enabled),
                    "channel_id": str(cfg.channel_id) if cfg.channel_id else None,
                    "channel_name": None,
                    "status": "DISABLED" if not cfg.enabled else "NO_CHANNEL",
                    "reason": "Invite activity logging is disabled" if not cfg.enabled else "No Discord channel selected",
                    "can_view": False,
                    "can_send": False,
                    "can_embed": False,
                    "is_ready": False,
                }

            if not self.bot or not self.bot.is_ready():
                return {
                    "enabled": True,
                    "channel_id": str(cfg.channel_id),
                    "channel_name": None,
                    "status": "DEGRADED",
                    "reason": "Discord bot is offline or not ready",
                    "can_view": False,
                    "can_send": False,
                    "can_embed": False,
                    "is_ready": False,
                }

            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                return {
                    "enabled": True,
                    "channel_id": str(cfg.channel_id),
                    "channel_name": None,
                    "status": "DEGRADED",
                    "reason": "Configured guild not accessible by bot",
                    "can_view": False,
                    "can_send": False,
                    "can_embed": False,
                    "is_ready": False,
                }

            channel = guild.get_channel(int(cfg.channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                return {
                    "enabled": True,
                    "channel_id": str(cfg.channel_id),
                    "channel_name": None,
                    "status": "DEGRADED",
                    "reason": "Bot cannot send messages to the configured invite log channel.",
                    "can_view": False,
                    "can_send": False,
                    "can_embed": False,
                    "is_ready": False,
                }

            me = guild.me
            perms = channel.permissions_for(me) if me else None
            can_view = bool(perms.view_channel) if perms else False
            can_send = bool(perms.send_messages) if perms else False
            can_embed = bool(perms.embed_links) if perms else False

            is_ready = can_view and can_send and can_embed
            status = "HEALTHY" if is_ready else "DEGRADED"
            reason = None if is_ready else "Bot cannot send messages to the configured invite log channel."

            return {
                "enabled": True,
                "channel_id": str(channel.id),
                "channel_name": channel.name,
                "status": status,
                "reason": reason,
                "can_view": can_view,
                "can_send": can_send,
                "can_embed": can_embed,
                "is_ready": is_ready,
            }
        finally:
            await session.close()

    async def _dispatch_activity_log(
        self,
        member: discord.Member,
        result: AttributionResult,
        join_record_id: Optional[int] = None,
    ) -> Optional[int]:
        """Dispatch a professional Discord embed to the dedicated invite activity channel."""
        session = await get_session_direct()
        try:
            cfg = await InviteActivitySettingsRepo.get_or_create(session, member.guild.id)
            if not cfg.enabled or not cfg.channel_id:
                return None

            # Event filters
            if result.source_type == "UNKNOWN" and not cfg.log_unknown:
                return None
            if result.source_type == "VANITY_URL" and not cfg.log_vanity:
                return None

            # Channel validation
            channel = member.guild.get_channel(int(cfg.channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.warning(
                    "Configured invite activity channel %s not found or invalid in guild %s",
                    cfg.channel_id,
                    member.guild.id,
                )
                return None

            me = member.guild.me
            perms = channel.permissions_for(me) if me else None
            if not perms or not (perms.view_channel and perms.send_messages and perms.embed_links):
                logger.warning(
                    "Bot lacks permissions (view/send/embed) in invite activity channel %s",
                    channel.name,
                )
                return None

            # Duplicate check if join record already posted
            if join_record_id:
                join_obj = await session.get(InviteJoin, join_record_id)
                if join_obj and join_obj.activity_message_id:
                    logger.info("Activity embed already dispatched for join %s, skipping duplicate", join_record_id)
                    return join_obj.activity_message_id

            # Color resolution
            color_int = 0x5865F2
            if cfg.color_hex:
                clean_hex = str(cfg.color_hex).lstrip("#")
                try:
                    color_int = int(clean_hex, 16)
                except ValueError:
                    pass

            joined_timestamp = int(member.joined_at.timestamp()) if member.joined_at else int(time.time())
            joined_str = f"<t:{joined_timestamp}:f>"

            if result.source_type == "NORMAL_INVITE":
                total_invites = 0
                rank_str = "N/A"
                if result.inviter_id:
                    stats = await InviteJoinRepo.get_user_stats(session, member.guild.id, result.inviter_id)
                    total_invites = stats.get("total_joins", stats.get("total_invites", 0))
                    rank = await InviteJoinRepo.get_user_rank(session, member.guild.id, result.inviter_id)
                    if rank is not None:
                        rank_str = f"#{rank}"

                inviter_mention = f"<@{result.inviter_id}>" if result.inviter_id else (result.inviter_name or "Unknown")
                chan_str = f"<#{result.channel_id}>" if result.channel_id else (f"#{result.channel_name}" if result.channel_name else "Unknown")

                format_vars = {
                    "inviter": result.inviter_name or "Unknown",
                    "inviter_mention": inviter_mention,
                    "inviter_id": str(result.inviter_id or ""),
                    "member": member.name,
                    "member_mention": member.mention,
                    "member_id": str(member.id),
                    "invite_code": result.invite_code or "Unknown",
                    "invite_channel": chan_str,
                    "total_invites": str(total_invites),
                    "rank": rank_str,
                    "joined_at": joined_str,
                    "server_name": member.guild.name,
                }

                title = self._safe_format_template(cfg.title_template or "🎉 NEW MEMBER INVITED", format_vars)
                desc = self._safe_format_template(cfg.description_template or "{inviter_mention} invited {member_mention}", format_vars)

                embed = discord.Embed(
                    title=title,
                    description=desc if desc.strip() else None,
                    color=color_int,
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="👤 Inviter", value=inviter_mention, inline=True)
                embed.add_field(name="👥 New Member", value=member.mention, inline=True)
                embed.add_field(name="🔗 Invite", value=f"`{result.invite_code or 'Unknown'}`", inline=True)
                embed.add_field(name="📍 Invite Channel", value=chan_str, inline=True)
                embed.add_field(name="📊 Total Invites", value=str(total_invites), inline=True)
                if rank_str != "N/A":
                    embed.add_field(name="🏆 Rank", value=rank_str, inline=True)
                embed.add_field(name="🕐 Joined", value=joined_str, inline=True)

                # Milestone check
                if total_invites in (5, 10, 25, 50, 100):
                    embed.add_field(
                        name="🏆 Invite Milestone",
                        value=f"{inviter_mention} has reached {total_invites} invites!",
                        inline=False,
                    )

            elif result.source_type == "VANITY_URL":
                embed = discord.Embed(
                    title="✨ MEMBER JOINED VIA VANITY",
                    description="Member joined using the server's vanity URL.",
                    color=0x3498DB,
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="👥 Member", value=f"{member.mention} (`{member.name}`)", inline=False)
                embed.add_field(name="📍 Source", value="Server Vanity URL", inline=True)
                if result.invite_code:
                    embed.add_field(name="🔗 Invite", value=f"`{result.invite_code}`", inline=True)
                embed.add_field(name="🕐 Time", value=joined_str, inline=True)

            else:
                embed = discord.Embed(
                    title="⚠️ MEMBER JOINED",
                    description="Join could not be reliably attributed to a specific active invite.",
                    color=0xE67E22,
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="👥 Member", value=f"{member.mention} (`{member.name}`)", inline=False)
                embed.add_field(name="🔗 Invite", value="Unknown", inline=True)
                embed.add_field(name="📍 Source", value="Unknown", inline=True)
                embed.add_field(name="🕐 Time", value=joined_str, inline=True)

            if getattr(member, "display_avatar", None):
                embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="PB HERO Discord Invite Tracker")

            msg = await channel.send(embed=embed)
            if join_record_id and msg:
                await InviteJoinRepo.update_activity_message_id(session, join_record_id, msg.id)
                await session.commit()
            return msg.id if msg else None
        except Exception as e:
            logger.warning("Failed to dispatch invite activity log embed: %s", e)
            return None
        finally:
            await session.close()

    async def _dispatch_activity_lifecycle(self, event_type: str, invite: discord.Invite) -> None:
        """Dispatch lifecycle logs (invite created / revoked) to the dedicated activity channel."""
        session = await get_session_direct()
        try:
            cfg = await InviteActivitySettingsRepo.get_or_create(session, self.guild_id)
            if not cfg.enabled or not cfg.channel_id:
                return

            if event_type == "invite_create" and not cfg.log_created:
                return
            if event_type == "invite_revoke" and not cfg.log_revoked:
                return

            guild = self.bot.get_guild(self.guild_id) if self.bot else None
            if not guild:
                return

            channel = guild.get_channel(int(cfg.channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                return

            me = guild.me
            perms = channel.permissions_for(me) if me else None
            if not perms or not (perms.view_channel and perms.send_messages and perms.embed_links):
                return

            inviter_str = f"{invite.inviter.mention} (`{invite.inviter}`)" if invite.inviter else "System / Unknown"
            chan_str = f"{invite.channel.mention}" if invite.channel else "Unknown"

            if event_type == "invite_create":
                embed = discord.Embed(
                    title="🔗 NEW INVITE CREATED",
                    color=0x5865F2,
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="Invite Code", value=f"`{invite.code}`", inline=True)
                embed.add_field(name="Created By", value=inviter_str, inline=True)
                embed.add_field(name="Target Channel", value=chan_str, inline=True)
                max_uses_str = str(invite.max_uses) if invite.max_uses else "Unlimited"
                max_age_str = f"{invite.max_age}s" if invite.max_age else "Never"
                embed.add_field(name="Max Uses", value=max_uses_str, inline=True)
                embed.add_field(name="Expires", value=max_age_str, inline=True)
                embed.set_footer(text="PB HERO Invite Tracker")
                await channel.send(embed=embed)

            elif event_type == "invite_revoke":
                embed = discord.Embed(
                    title="🗑️ INVITE REVOKED",
                    color=0xED4245,
                    timestamp=datetime.now(timezone.utc),
                )
                embed.add_field(name="Invite Code", value=f"`{invite.code}`", inline=True)
                embed.add_field(name="Channel", value=chan_str, inline=True)
                embed.add_field(name="Status", value="REVOKED (joins preserved)", inline=True)
                embed.set_footer(text="PB HERO Invite Tracker")
                await channel.send(embed=embed)
        except Exception as e:
            logger.warning("Failed to dispatch activity lifecycle log (%s): %s", event_type, e)
        finally:
            await session.close()

    async def send_test_activity_log(self) -> Dict[str, Any]:
        """Send a test invite activity embed to the configured channel without modifying DB counters."""
        if not self.bot or not self.bot.is_ready():
            raise RuntimeError("Discord bot is offline or not ready.")

        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            raise RuntimeError(f"Configured guild {self.guild_id} not accessible by bot.")

        session = await get_session_direct()
        try:
            cfg = await InviteActivitySettingsRepo.get_or_create(session, self.guild_id)
            if not cfg.enabled or not cfg.channel_id:
                raise ValueError("Invite activity logging is disabled or no channel is selected.")

            channel = guild.get_channel(int(cfg.channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                raise ValueError(f"Configured channel ID {cfg.channel_id} not found as a text channel.")

            me = guild.me
            perms = channel.permissions_for(me) if me else None
            missing = []
            if not perms or not perms.view_channel:
                missing.append("View Channel")
            if not perms or not perms.send_messages:
                missing.append("Send Messages")
            if not perms or not perms.embed_links:
                missing.append("Embed Links")
            if missing:
                raise ValueError(f"Bot lacks required permissions in #{channel.name}: {', '.join(missing)}")

            test_vars = {
                "inviter": "Rex12400",
                "inviter_mention": "@Rex12400",
                "inviter_id": "123456789012345678",
                "member": "Rahul",
                "member_mention": "@Rahul",
                "member_id": "987654321098765432",
                "invite_code": "xFP2SD3UVF",
                "invite_channel": f"#{channel.name}",
                "total_invites": "12",
                "rank": "#1",
                "joined_at": "Today at 12:35 PM",
                "server_name": guild.name,
            }

            title = "🧪 INVITE TRACKING TEST"
            desc = self._safe_format_template(
                cfg.description_template or "@Rex12400 invited @Rahul", test_vars
            )
            color_int = 0x5865F2
            if cfg.color_hex:
                clean_hex = str(cfg.color_hex).lstrip("#")
                try:
                    color_int = int(clean_hex, 16)
                except ValueError:
                    pass

            embed = discord.Embed(
                title=title,
                description=desc if desc.strip() else None,
                color=color_int,
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="👤 Inviter", value="@Rex12400", inline=True)
            embed.add_field(name="👥 New Member", value="@Rahul", inline=True)
            embed.add_field(name="🔗 Invite", value="`xFP2SD3UVF`", inline=True)
            embed.add_field(name="📍 Invite Channel", value=f"#{channel.name}", inline=True)
            embed.add_field(name="📊 Total Invites", value="12", inline=True)
            embed.add_field(name="🏆 Rank", value="#1", inline=True)
            embed.add_field(name="🕐 Joined", value="Today at 12:35 PM", inline=True)
            embed.add_field(
                name="🧪 Notice",
                value="This is a test notification from PB HERO Bot. No database counters were modified.",
                inline=False,
            )
            embed.set_footer(text="PB HERO Discord Invite Tracker • Test Mode")

            msg = await channel.send(embed=embed)
            return {
                "success": True,
                "channel_id": str(channel.id),
                "channel_name": channel.name,
                "message_id": str(msg.id),
            }
        finally:
            await session.close()


_invite_tracker: Optional[InviteTracker] = None


def get_invite_tracker(bot: Optional[commands.Bot] = None) -> InviteTracker:
    """Singleton getter for InviteTracker."""
    global _invite_tracker
    if _invite_tracker is None:
        _invite_tracker = InviteTracker(bot)
    elif bot is not None:
        _invite_tracker.set_bot(bot)
    return _invite_tracker
