"""
PB HERO Moderation Engine.

Application-side message filtering engine that enforces channel policies,
granular bypass rules, automod rules, warning records, and escalation ladders.
"""

from datetime import datetime, timedelta
import logging
import time
from typing import Optional

import discord

from app.database.engine import get_session_direct
from app.database.models import ModerationAction, PolicyValue
from app.database.repositories import (
    AutomodRuleRepo,
    BlockedMessageRepo,
    ChannelPolicyRepo,
    ExemptionRuleRepo,
    ModerationCaseRepo,
    ModerationExemptionRepo,
    RoleOverride,
    ServerConfigRepo,
    WarningEscalationRepo,
    WarningRecordRepo,
)
from app.database.serializers import deserialize_json_field
from app.moderation.evaluator import (
    evaluate_automod_rules,
    evaluate_message_policy,
    evaluate_voice_policy,
)

logger = logging.getLogger("pbhero.moderation")


def can_moderate_member(
    bot_member: Optional[discord.Member],
    target_member: Optional[discord.Member],
    action: str,
) -> tuple[bool, str]:
    """
    Check Discord permissions and role hierarchy before executing punishments.
    Returns (can_execute, reason_if_cannot).
    """
    if not bot_member:
        return False, "Bot member information unavailable"
    if not target_member:
        return False, "Target member information unavailable"
    if target_member.id == bot_member.id:
        return False, "Cannot execute moderation action against the bot itself"
    if target_member.guild and target_member.id == target_member.guild.owner_id:
        return False, "Cannot execute moderation action against server owner"

    # Discord Role Hierarchy: Bot's top role must be strictly higher than target's top role
    target_pos = getattr(target_member.top_role, "position", 0) if hasattr(target_member, "top_role") else 0
    bot_pos = getattr(bot_member.top_role, "position", 0) if hasattr(bot_member, "top_role") else 0
    target_role_name = getattr(target_member.top_role, "name", "target role")
    bot_role_name = getattr(bot_member.top_role, "name", "bot role")

    if target_pos >= bot_pos:
        return (
            False,
            f"Cannot {action} member: target's highest role ({target_role_name}) "
            f"is higher than or equal to bot's highest role ({bot_role_name})",
        )

    perms = bot_member.guild_permissions
    if action == "timeout" and not perms.moderate_members:
        return False, "Bot lacks 'Moderate Members' permission"
    if action == "kick" and not perms.kick_members:
        return False, "Bot lacks 'Kick Members' permission"
    if action == "ban" and not perms.ban_members:
        return False, "Bot lacks 'Ban Members' permission"
    if action == "delete" and not perms.manage_messages:
        return False, "Bot lacks 'Manage Messages' permission"

    return True, ""


async def execute_moderation_action(
    bot: Optional[discord.Client],
    guild: Optional[discord.Guild],
    target_user_id: int | str,
    action: str,
    reason: str = "Automated moderation enforcement",
    duration_seconds: int = 600,
    send_dm: bool = True,
    delete_message_history_days: int = 1,
) -> dict:
    """
    Safely executes a punishment action (timeout, kick, ban) against a target member,
    verifying bot permissions and role hierarchy first.
    """
    action = action.lower()
    target_id_int = int(target_user_id) if isinstance(target_user_id, str) and target_user_id.isdigit() else target_user_id

    bot_member = guild.me if guild else None
    target_member = None
    if guild and hasattr(guild, "get_member"):
        target_member = guild.get_member(target_id_int)

    can_exec, reason_why = can_moderate_member(bot_member, target_member, action)
    if not can_exec:
        return {
            "success": False,
            "action": action,
            "error": reason_why,
            "permission_error": True,
            "dm_sent": False,
        }

    dm_sent = False
    if send_dm and target_member:
        try:
            dm_ch = await target_member.create_dm()
            await dm_ch.send(
                f"🛡️ **PB HERO Moderation Action**: You received a `{action.upper()}` for: {reason}"
            )
            dm_sent = True
        except Exception:
            pass

    try:
        if action == "timeout" and target_member:
            until = datetime.utcnow() + timedelta(seconds=duration_seconds)
            await target_member.timeout(until=until, reason=reason)
        elif action == "kick" and target_member:
            await target_member.kick(reason=reason)
        elif action == "ban" and target_member:
            await target_member.ban(reason=reason, delete_message_days=delete_message_history_days)
        return {
            "success": True,
            "action": action,
            "error": None,
            "permission_error": False,
            "dm_sent": dm_sent,
        }
    except Exception as e:
        return {
            "success": False,
            "action": action,
            "error": str(e),
            "permission_error": "permission" in str(e).lower() or "hierarchy" in str(e).lower(),
            "dm_sent": dm_sent,
        }


async def evaluate_infraction(
    session,
    user_id: int | str,
    username: str,
    channel_id: Optional[int | str] = None,
    channel_name: Optional[str] = None,
    rule: str = "Policy Violation",
    reason: str = "Infraction detected",
    severity: str = "medium",
    bot: Optional[discord.Client] = None,
    guild: Optional[discord.Guild] = None,
    moderator: str = "PB HERO AutoMod",
) -> dict:
    """
    Central escalation service:
    1. Record warning in warning_records
    2. Calculate active count/points based on configured decay
    3. Find escalation ladder rule
    4. Execute configured action (checking permissions & role hierarchy)
    5. Send optional DM
    6. Record dashboard audit log in moderation_cases
    7. Return comprehensive escalation summary
    """
    decay_days = await ServerConfigRepo.get_config(session, "warning_decay_days", 30)
    mode = await ServerConfigRepo.get_config(session, "warning_mode", "count")
    points_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    points = points_map.get(severity, 1)

    warn_record = await WarningRecordRepo.create(
        session=session,
        user_id=user_id,
        username=username,
        channel_id=channel_id,
        channel_name=channel_name,
        rule=rule,
        reason=reason,
        severity=severity,
        points=points,
        moderator=moderator,
        expires_days=decay_days,
    )

    strikes, total_points = await WarningRecordRepo.get_user_strikes_and_points(
        session=session,
        user_id=user_id,
        decay_days=decay_days,
    )
    active_score = total_points if mode == "point" or mode == "points" else strikes

    escalation_rule = await WarningEscalationRepo.find_escalation(
        session=session,
        current_val=active_score,
        mode=mode,
    )

    action_taken = "warn"
    action_detail = "Warning issued"
    perm_error = None
    dm_status = "disabled"

    if escalation_rule:
        esc_action = escalation_rule.action.lower()
        duration = escalation_rule.duration or 600
        exec_res = await execute_moderation_action(
            bot=bot,
            guild=guild,
            target_user_id=user_id,
            action=esc_action,
            reason=f"PB HERO Escalation: {reason}",
            duration_seconds=duration,
            send_dm=escalation_rule.send_dm,
            delete_message_history_days=getattr(escalation_rule, "delete_message_history_days", 1) or 1,
        )
        if exec_res["success"]:
            action_taken = esc_action
            action_detail = f"{esc_action.capitalize()} executed"
        else:
            perm_error = exec_res.get("error")

    # Audit log in moderation_cases
    action_enum_map = {
        "warn": ModerationAction.WARN,
        "timeout": ModerationAction.TIMEOUT,
        "kick": ModerationAction.KICK,
        "ban": ModerationAction.BAN,
    }
    case_record = await ModerationCaseRepo.create(
        session=session,
        case_id=warn_record.case_id,
        target_user_id=user_id,
        target_username=username,
        moderator_user_id=bot.user.id if bot and bot.user else 0,
        moderator_username=moderator,
        action=action_enum_map.get(action_taken, ModerationAction.WARN),
        reason=f"{reason} (Permission Warning: {perm_error})" if perm_error else reason,
        channel_id=channel_id,
        channel_name=channel_name,
        rule=rule,
        warning_id=warn_record.warning_id,
        severity=severity,
        dm_status=dm_status,
        discord_log_status="pending",
        executor=moderator,
    )

    return {
        "case_id": warn_record.case_id,
        "warning_id": warn_record.warning_id,
        "action_taken": action_taken,
        "active_strikes": strikes,
        "active_points": total_points,
        "escalation_matched": escalation_rule.id if escalation_rule else None,
        "perm_error": perm_error,
    }


class ModerationEngine:
    """
    Server-side message filtering, automod, and policy enforcement engine.
    """

    def __init__(self, bot: discord.Client, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self._policy_cache: dict = {}
        self._exemption_cache: dict = {}
        self._granular_exemptions_cache: list[dict] = []
        self._automod_rules_cache: list[dict] = []
        self._server_config_cache: dict = {}
        self._cache_valid = False
        # Rate-limiting safety: list of (timestamp, user_id)
        self._recent_actions: list[tuple[float, int]] = []

    async def refresh_cache(self) -> None:
        """Refresh policies, exemptions, automod rules, and server configuration."""
        session = await get_session_direct()
        try:
            # 1. Load channel policies
            policies = await ChannelPolicyRepo.get_all(session)
            self._policy_cache = {}
            for policy in policies:
                if policy.enabled:
                    self._policy_cache[policy.discord_channel_id] = self._policy_to_dict(policy)

            # 2. Load legacy exemptions
            legacy_exemptions = await ExemptionRuleRepo.get_all(session)
            self._exemption_cache = {}
            for exemption in legacy_exemptions:
                key = f"{exemption.rule_type}:{exemption.target_id}"
                if key not in self._exemption_cache:
                    self._exemption_cache[key] = []
                self._exemption_cache[key].append(exemption.exempt_from)

            # 3. Load granular moderation exemptions
            granular_exemptions = await ModerationExemptionRepo.get_all(session)
            self._granular_exemptions_cache = [
                {
                    "id": ex.id,
                    "target_type": ex.target_type,
                    "target_id": ex.target_id,
                    "target_name": ex.target_name,
                    "scope": ex.scope,
                    "scope_id": ex.scope_id,
                    "scope_name": ex.scope_name,
                    "channel_type": ex.channel_type,
                    "bypass_all": ex.bypass_all,
                    "bypass_text": ex.bypass_text,
                    "bypass_links": ex.bypass_links,
                    "bypass_images": ex.bypass_images,
                    "bypass_videos": ex.bypass_videos,
                    "bypass_files": ex.bypass_files,
                    "bypass_stickers": ex.bypass_stickers,
                    "bypass_mentions": ex.bypass_mentions,
                    "bypass_spam": ex.bypass_spam,
                    "bypass_keywords": ex.bypass_keywords,
                    "bypass_invites": ex.bypass_invites,
                    "bypass_warnings": ex.bypass_warnings,
                    "bypass_timeout": ex.bypass_timeout,
                    "bypass_kick": ex.bypass_kick,
                    "bypass_ban": ex.bypass_ban,
                }
                for ex in granular_exemptions
            ]

            # 4. Load automod rules
            automod_rules = await AutomodRuleRepo.get_all(session)
            if not automod_rules:
                await AutomodRuleRepo.create_defaults(session)
                automod_rules = await AutomodRuleRepo.get_all(session)

            self._automod_rules_cache = [
                {
                    "id": r.id,
                    "rule_type": r.rule_type,
                    "name": r.name,
                    "enabled": r.enabled,
                    "scope": r.scope,
                    "channels": deserialize_json_field(r.channels, default=[]),
                    "categories": deserialize_json_field(r.categories, default=[]),
                    "threshold": r.threshold,
                    "time_window": r.time_window,
                    "action": r.action,
                    "timeout_duration": r.timeout_duration,
                    "custom_keywords": deserialize_json_field(r.custom_keywords, default=[]),
                    "severity": r.severity or "medium",
                }
                for r in automod_rules
            ]

            # 5. Load server config
            config = await ServerConfigRepo.get(session)
            default_log_events = [
                "policy_violation", "blocked_link", "blocked_attachment", "blocked_mention",
                "warning", "timeout", "kick", "ban", "message_delete"
            ]

            if config:
                self._server_config_cache = {
                    "mod_log_channel_id": config.mod_log_channel_id,
                    "admin_role_ids": deserialize_json_field(config.admin_role_ids, default=[]),
                    "moderator_role_ids": deserialize_json_field(config.moderator_role_ids, default=[]),
                    "global_allowed_domains": deserialize_json_field(config.global_allowed_domains, default=[]),
                    "warning_message_template": config.warning_message_template,
                    "mod_log_events": deserialize_json_field(getattr(config, "mod_log_events", None), default=default_log_events),
                    "warning_decay_days": getattr(config, "warning_decay_days", 30),
                    "warning_mode": getattr(config, "warning_mode", "count"),
                    "rate_limit_actions_per_min": getattr(config, "rate_limit_actions_per_min", 20),
                    "rate_limit_user_actions_per_min": getattr(config, "rate_limit_user_actions_per_min", 5),
                }
            else:
                self._server_config_cache = {
                    "mod_log_channel_id": None,
                    "admin_role_ids": [],
                    "moderator_role_ids": [],
                    "global_allowed_domains": [],
                    "warning_message_template": None,
                    "mod_log_events": default_log_events,
                    "warning_decay_days": 30,
                    "warning_mode": "count",
                    "rate_limit_actions_per_min": 20,
                    "rate_limit_user_actions_per_min": 5,
                }

            self._cache_valid = True
            logger.info(
                "Moderation cache refreshed: %d policies, %d granular exemptions, %d automod rules",
                len(self._policy_cache),
                len(self._granular_exemptions_cache),
                len(self._automod_rules_cache),
            )
        finally:
            await session.close()

    def _policy_to_dict(self, policy) -> dict:
        """Convert a ChannelPolicy model to a dict for processing."""
        return {
            "channel_id": policy.discord_channel_id,
            "channel_name": policy.channel_name,
            "category_name": policy.category_name,
            "channel_type": getattr(policy, "channel_type", "text"),
            "preset_name": getattr(policy, "preset_name", None),
            "allow_text": policy.allow_text.value if isinstance(policy.allow_text, PolicyValue) else str(policy.allow_text),
            "allow_links": policy.allow_links.value if isinstance(policy.allow_links, PolicyValue) else str(policy.allow_links),
            "allow_images": policy.allow_images.value if isinstance(policy.allow_images, PolicyValue) else str(policy.allow_images),
            "allow_videos": policy.allow_videos.value if isinstance(policy.allow_videos, PolicyValue) else str(policy.allow_videos),
            "allow_files": policy.allow_files.value if isinstance(policy.allow_files, PolicyValue) else str(policy.allow_files),
            "allow_stickers": policy.allow_stickers.value if isinstance(policy.allow_stickers, PolicyValue) else str(policy.allow_stickers),
            "allow_everyone": policy.allow_everyone.value if isinstance(policy.allow_everyone, PolicyValue) else str(policy.allow_everyone),
            "allow_here": policy.allow_here.value if isinstance(policy.allow_here, PolicyValue) else str(policy.allow_here),
            "allow_role_mentions": policy.allow_role_mentions.value if isinstance(policy.allow_role_mentions, PolicyValue) else str(policy.allow_role_mentions),
            "allow_user_mentions": policy.allow_user_mentions.value if isinstance(policy.allow_user_mentions, PolicyValue) else str(policy.allow_user_mentions),
            # Voice fields
            "allow_connect": getattr(policy, "allow_connect", "inherit"),
            "allow_speak": getattr(policy, "allow_speak", "inherit"),
            "allow_video": getattr(policy, "allow_video", "inherit"),
            "allow_stream": getattr(policy, "allow_stream", "inherit"),
            "allow_soundboard": getattr(policy, "allow_soundboard", "inherit"),
            "allow_voice_activity": getattr(policy, "allow_voice_activity", "inherit"),
            "allow_priority_speaker": getattr(policy, "allow_priority_speaker", "inherit"),
            "allow_mute_members": getattr(policy, "allow_mute_members", "inherit"),
            "allow_deafen_members": getattr(policy, "allow_deafen_members", "inherit"),
            "allow_move_members": getattr(policy, "allow_move_members", "inherit"),
            "allowed_domains": deserialize_json_field(policy.allowed_domains, default=[]),
            "warning_message": policy.warning_message,
            "log_violations": getattr(policy, "log_violations", True),
            "delete_violations": getattr(policy, "delete_violations", True),
            "warn_on_violation": getattr(policy, "warn_on_violation", True),
            "send_dm_warning": getattr(policy, "send_dm_warning", False),
        }

    def _is_exempt(
        self,
        member: discord.Member,
        channel_id: int,
        category_name: Optional[str] = None,
        rule_name: str = "all",
    ) -> bool:
        """
        Check if a member is exempt from moderation policies via deterministic precedence:
        1. Server owner / Bot self
        2. Discord Administrator permission
        3. Explicit user exemption
        4. Role exemptions
        5. Bot exemption
        6. Channel exemption
        7. Category exemption
        """
        # Server owner is always exempt
        if member.guild.owner_id == member.id:
            return True

        # Bot itself is exempt
        if member.bot and member.id == self.bot.user.id:
            return True

        # Discord Administrator permission
        if member.guild_permissions.administrator:
            return True

        # Check admin & mod role lists
        admin_roles = set(self._server_config_cache.get("admin_role_ids", []))
        mod_roles = set(self._server_config_cache.get("moderator_role_ids", []))
        exempt_role_ids = admin_roles | mod_roles
        member_role_ids = {r.id for r in member.roles}
        if member_role_ids & exempt_role_ids:
            return True

        # Check granular exemptions
        exemptions = self._granular_exemptions_cache
        if not exemptions:
            return False

        def scope_matches(ex: dict) -> bool:
            scope = ex.get("scope", "global")
            if scope == "global":
                return True
            if scope == "channel":
                return ex.get("scope_id") == channel_id
            if scope == "category":
                cat = category_name or ""
                return (ex.get("scope_name") and ex["scope_name"].lower() == cat.lower())
            if scope == "channel_type":
                return ex.get("channel_type") == "text"
            return True

        def rule_matches(ex: dict) -> bool:
            if ex.get("bypass_all"):
                return True
            rule_key = rule_name.lower().replace("allow_", "").replace("filter_", "")
            # check bypass_<rule>
            attr_name = f"bypass_{rule_key}"
            if ex.get(attr_name):
                return True
            # Check general categories
            if "link" in rule_key and ex.get("bypass_links"):
                return True
            if "mention" in rule_key and ex.get("bypass_mentions"):
                return True
            if "spam" in rule_key and ex.get("bypass_spam"):
                return True
            if "keyword" in rule_key and ex.get("bypass_keywords"):
                return True
            if "invite" in rule_key and ex.get("bypass_invites"):
                return True
            if ("image" in rule_key or "media" in rule_key) and ex.get("bypass_images"):
                return True
            if "video" in rule_key and ex.get("bypass_videos"):
                return True
            if "file" in rule_key and ex.get("bypass_files"):
                return True
            return False

        # 1. User exemption
        for ex in exemptions:
            if ex.get("target_type") == "user" and ex.get("target_id") == member.id and scope_matches(ex):
                if rule_matches(ex):
                    return True

        # 2. Role exemptions
        for ex in exemptions:
            if ex.get("target_type") == "role" and ex.get("target_id") in member_role_ids and scope_matches(ex):
                if rule_matches(ex):
                    return True

        # 3. Bot exemption
        if member.bot:
            for ex in exemptions:
                if ex.get("target_type") == "bot" and (ex.get("target_id") == 0 or ex.get("target_id") == member.id) and scope_matches(ex):
                    if rule_matches(ex):
                        return True

        # 4. Channel exemption
        for ex in exemptions:
            if ((ex.get("target_type") == "channel" and ex.get("target_id") == channel_id) or
                (ex.get("scope") == "channel" and ex.get("scope_id") == channel_id)):
                if rule_matches(ex):
                    return True

        # 5. Category exemption
        if category_name:
            for ex in exemptions:
                if (ex.get("scope") == "category" and ex.get("scope_name") and ex["scope_name"].lower() == category_name.lower()):
                    if rule_matches(ex):
                        return True

        return False

    async def process_message(self, message: discord.Message) -> Optional[dict]:
        """
        Process a message against automod rules and channel policy.
        Returns infraction dict if blocked, None if allowed.
        """
        if not message.guild or message.guild.id != self.guild_id:
            return None

        # Refresh cache if needed
        if not self._cache_valid:
            await self.refresh_cache()

        channel_id = message.channel.id
        category_name = message.channel.category.name if getattr(message.channel, "category", None) else None

        # 1. Check Automod Rules First
        mentions_count = len(message.mentions) + len(message.role_mentions)
        if message.mention_everyone:
            mentions_count += 2

        automod_violation = evaluate_automod_rules(
            rules=self._automod_rules_cache,
            content=message.content,
            attachments=list(message.attachments) if message.attachments else None,
            mentions_count=mentions_count,
        )

        if automod_violation:
            # Check if author is exempt from this rule
            if isinstance(message.author, discord.Member) and self._is_exempt(
                member=message.author,
                channel_id=channel_id,
                category_name=category_name,
                rule_name=automod_violation["rule"],
            ):
                logger.info(
                    "Automod violation '%s' bypassed by exemption for %s in #%s",
                    automod_violation["rule"],
                    message.author,
                    message.channel.name,
                )
            else:
                return {
                    "reason": automod_violation["reason"],
                    "rule": automod_violation["rule"],
                    "rule_name": automod_violation.get("rule_name", "Automod Rule"),
                    "action": automod_violation.get("action", "delete_warn"),
                    "severity": automod_violation.get("severity", "medium"),
                    "timeout_duration": automod_violation.get("timeout_duration", 600),
                    "matched_policy": automod_violation.get("rule_name", "Automod Rule"),
                }

        # 2. Check Channel Policy
        policy = self._policy_cache.get(channel_id)
        if not policy:
            return None

        # Evaluate via unified policy evaluator
        attachments_data = [
            {"filename": a.filename, "content_type": getattr(a, "content_type", "")}
            for a in message.attachments
        ]

        eval_result = evaluate_message_policy(
            policy=policy,
            content=message.content,
            attachments=attachments_data,
            stickers=list(message.stickers) if message.stickers else None,
            role_mentions=list(message.role_mentions) if message.role_mentions else None,
            user_mentions=list(message.mentions) if message.mentions else None,
            server_config=self._server_config_cache,
            channel_name=message.channel.name if hasattr(message.channel, "name") else "",
        )

        if not eval_result["allowed"]:
            matched_rule = eval_result.get("matched_rule") or "policy_violation"
            # Check exemption for this matched policy rule
            if isinstance(message.author, discord.Member) and self._is_exempt(
                member=message.author,
                channel_id=channel_id,
                category_name=category_name,
                rule_name=matched_rule,
            ):
                logger.info(
                    "Channel policy violation '%s' bypassed by exemption for %s in #%s",
                    matched_rule,
                    message.author,
                    message.channel.name,
                )
                return None

            return {
                "reason": eval_result["reason"],
                "rule": matched_rule,
                "urls": eval_result.get("urls", []),
                "matched_policy": eval_result.get("matched_policy"),
                "action": "delete_warn",
                "severity": "medium",
            }

        return None

    async def handle_violation(self, message: discord.Message, violation: dict) -> None:
        """
        Handle a policy or automod violation:
        1. Apply rate limit check
        2. Delete message if configured
        3. Issue warning and record in warning_records
        4. Evaluate escalation ladder (timeout, kick, ban) with permission & hierarchy checks
        5. Send in-channel and DM warnings
        6. Record in moderation_cases and blocked_messages
        7. Send embed to Discord mod log channel
        """
        channel_id = message.channel.id
        policy = self._policy_cache.get(channel_id, {})
        author = message.author
        now_ts = time.time()

        # 1. Rate-limiting check
        self._recent_actions = [a for a in self._recent_actions if now_ts - a[0] < 60]
        max_per_min = self._server_config_cache.get("rate_limit_actions_per_min", 20)
        max_user_per_min = self._server_config_cache.get("rate_limit_user_actions_per_min", 5)

        total_recent = len(self._recent_actions)
        user_recent = sum(1 for a in self._recent_actions if a[1] == author.id)
        rate_limited = (total_recent >= max_per_min) or (user_recent >= max_user_per_min)
        if not rate_limited:
            self._recent_actions.append((now_ts, author.id))

        action_intent = violation.get("action", "delete_warn")
        should_delete = "delete" in action_intent or policy.get("delete_violations", True)

        # 2. Delete the violating message
        if should_delete:
            try:
                await message.delete()
                logger.info(
                    "Deleted message %d from %s in #%s: %s",
                    message.id,
                    author,
                    message.channel.name,
                    violation["reason"],
                )
            except discord.Forbidden:
                logger.warning("Cannot delete message in #%s: missing permissions", message.channel.name)
            except discord.NotFound:
                pass

        # 3. Create Warning & Evaluate Escalation Ladder
        session = await get_session_direct()
        case_id = None
        warning_id = None
        executed_action = "warn"
        action_detail = "Warning issued"
        perm_error = None
        dm_status = "disabled"

        try:
            decay_days = self._server_config_cache.get("warning_decay_days", 30)
            mode = self._server_config_cache.get("warning_mode", "count")
            severity = violation.get("severity", "medium")
            points_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            points = points_map.get(severity, 1)

            # Record warning in warning_records
            warn_record = await WarningRecordRepo.create(
                session=session,
                user_id=author.id,
                username=str(author),
                channel_id=channel_id,
                channel_name=message.channel.name,
                rule=violation.get("rule", "policy_violation"),
                reason=violation["reason"],
                severity=severity,
                points=points,
                moderator="PB HERO AutoMod",
                expires_days=decay_days,
            )
            warning_id = warn_record.warning_id
            case_id = warn_record.case_id

            # Calculate active warnings for this user
            strikes, total_points = await WarningRecordRepo.get_user_strikes_and_points(
                session=session,
                user_id=author.id,
                decay_days=decay_days,
            )
            active_score = total_points if mode == "point" else strikes

            # Check Escalation Ladder
            escalation_rule = await WarningEscalationRepo.find_escalation(
                session=session,
                current_val=active_score,
                mode=mode,
            )

            # Check Bot Permissions & Role Hierarchy
            bot_member = message.guild.me if message.guild else None
            target_member = author if isinstance(author, discord.Member) else None

            if not rate_limited and escalation_rule and target_member and bot_member:
                esc_action = escalation_rule.action.lower()
                can_exec, reason_why = can_moderate_member(bot_member, target_member, esc_action)

                if can_exec:
                    if esc_action == "timeout":
                        duration = escalation_rule.duration or violation.get("timeout_duration") or 600
                        until = datetime.utcnow() + timedelta(seconds=duration)
                        try:
                            await target_member.timeout(
                                until=until,
                                reason=f"PB HERO AutoMod Escalation: {violation['reason']}",
                            )
                            executed_action = "timeout"
                            action_detail = f"Timeout ({duration // 60}m)"
                        except discord.HTTPException as e:
                            perm_error = f"Timeout failed: {e}"
                    elif esc_action == "kick":
                        try:
                            await target_member.kick(
                                reason=f"PB HERO AutoMod Escalation: {violation['reason']}",
                            )
                            executed_action = "kick"
                            action_detail = "Kicked from server"
                        except discord.HTTPException as e:
                            perm_error = f"Kick failed: {e}"
                    elif esc_action == "ban":
                        try:
                            del_days = getattr(escalation_rule, "delete_message_history_days", 1) or 1
                            await target_member.ban(
                                reason=f"PB HERO AutoMod Escalation: {violation['reason']}",
                                delete_message_days=del_days,
                            )
                            executed_action = "ban"
                            action_detail = "Banned from server"
                        except discord.HTTPException as e:
                            perm_error = f"Ban failed: {e}"
                else:
                    perm_error = reason_why
                    logger.warning("AutoMod could not execute %s against %s: %s", esc_action, author, reason_why)

            # Send DM Warning if enabled
            send_dm = policy.get("send_dm_warning", False) or (escalation_rule and escalation_rule.send_dm)
            if send_dm:
                try:
                    dm_channel = await author.create_dm()
                    dm_msg = (
                        f"🛡️ **PB HERO AutoMod Notification**\n"
                        f"You received an automated moderation action in **#{message.channel.name}**.\n\n"
                        f"> **Action Taken**: `{action_detail}`\n"
                        f"> **Reason**: {violation['reason']}\n"
                        f"> **Rule**: `{violation.get('rule', 'Policy Rule')}`\n"
                        f"> **Active Strikes**: {strikes} (Points: {total_points})\n"
                        f"> **Case ID**: `{case_id}`"
                    )
                    await dm_channel.send(dm_msg)
                    dm_status = "delivered"
                except (discord.Forbidden, discord.HTTPException):
                    dm_status = "failed"
                    logger.info("DM delivery failed for user %s (DMs closed)", author)

            # Record in moderation_cases table
            action_enum_map = {
                "warn": ModerationAction.WARN,
                "timeout": ModerationAction.TIMEOUT,
                "kick": ModerationAction.KICK,
                "ban": ModerationAction.BAN,
            }
            mod_action_enum = action_enum_map.get(executed_action, ModerationAction.WARN)

            case_reason = violation["reason"]
            if perm_error:
                case_reason = f"{case_reason} (PERMISSION ERROR: {perm_error})"

            await ModerationCaseRepo.create(
                session=session,
                case_id=case_id,
                target_user_id=author.id,
                target_username=str(author),
                moderator_user_id=self.bot.user.id if self.bot.user else 0,
                moderator_username="PB HERO AutoMod",
                action=mod_action_enum,
                reason=case_reason,
                channel_id=channel_id,
                channel_name=message.channel.name,
                message_id=message.id,
                rule=violation.get("rule", "policy_violation"),
                policy_name=violation.get("matched_policy") or policy.get("preset_name"),
                warning_id=warning_id,
                severity=severity,
                dm_status=dm_status,
                discord_log_status="pending",
                executor="PB HERO AutoMod",
            )

            # Record in blocked_messages table
            if policy.get("log_violations", True):
                await BlockedMessageRepo.create(
                    session=session,
                    channel_id=channel_id,
                    user_id=author.id,
                    username=str(author),
                    message_id=message.id,
                    content_preview=message.content[:200] if message.content else None,
                    reason=violation["reason"],
                    rule=violation["rule"],
                )

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Failed to persist moderation records: %s", str(e))
        finally:
            await session.close()

        # Send transient in-channel notification
        if policy.get("warn_on_violation", True) and not rate_limited:
            warn_tpl = policy.get("warning_message") or self._server_config_cache.get("warning_message_template") or f"⚠️ {violation['reason']}"
            try:
                await message.channel.send(
                    f"{author.mention} {warn_tpl}",
                    delete_after=10,
                    allowed_mentions=discord.AllowedMentions(users=[author]),
                )
            except discord.Forbidden:
                pass

        # Send Embed to Discord Mod Log Channel
        await self._send_mod_log(
            message=message,
            violation=violation,
            case_id=case_id or f"CASE-{message.id % 10000:04d}",
            warning_id=warning_id or "WARN-0000",
            action_taken=action_detail,
            perm_error=perm_error,
            dm_status=dm_status,
        )

    async def _send_mod_log(
        self,
        message: discord.Message,
        violation: dict,
        case_id: str,
        warning_id: str,
        action_taken: str,
        perm_error: Optional[str] = None,
        dm_status: str = "disabled",
    ) -> None:
        """Send formatted embed to the configured moderation log channel."""
        mod_log_id = self._server_config_cache.get("mod_log_channel_id")
        if not mod_log_id:
            return

        enabled_events = set(self._server_config_cache.get("mod_log_events", []))
        rule_key = violation.get("rule", "policy_violation")
        event_tag = "policy_violation"
        if "link" in rule_key:
            event_tag = "blocked_link"
        elif "image" in rule_key or "video" in rule_key or "file" in rule_key or "attachment" in rule_key:
            event_tag = "blocked_attachment"
        elif "mention" in rule_key or "everyone" in rule_key or "here" in rule_key:
            event_tag = "blocked_mention"

        if enabled_events and event_tag not in enabled_events and "policy_violation" not in enabled_events:
            return

        try:
            channel = self.bot.get_channel(int(mod_log_id))
        except (ValueError, TypeError):
            return

        if not channel:
            logger.warning("Auto-Mod log channel %s not found on server", mod_log_id)
            return

        # Check permissions
        if hasattr(channel, "guild") and channel.guild and channel.guild.me:
            perms = channel.permissions_for(channel.guild.me)
            if not perms.send_messages or not perms.embed_links:
                logger.warning(
                    "Bot lacks Send Messages or Embed Links permission in mod log channel #%s",
                    channel.name,
                )
                return

        policy = self._policy_cache.get(message.channel.id, {})
        policy_name = violation.get("matched_policy") or policy.get("preset_name") or "Channel Policy"

        # Action Colors
        # Warning: 0xFEE75C (yellow)
        # Blocked: 0xE67E22 (orange)
        # Timeout: 0xED4245 (red-orange)
        # Kick: 0xE74C3C (red)
        # Ban: 0x992D22 (dark red)
        color = 0xE67E22
        if "timeout" in action_taken.lower():
            color = 0xED4245
        elif "kick" in action_taken.lower():
            color = 0xE74C3C
        elif "ban" in action_taken.lower():
            color = 0x992D22
        elif "warn" in action_taken.lower():
            color = 0xFEE75C

        try:
            embed = discord.Embed(
                title="🛡️ PB HERO AUTO-MOD",
                color=color,
                timestamp=message.created_at,
            )
            embed.add_field(name="Case ID", value=f"`{case_id}`", inline=True)
            embed.add_field(name="Warning ID", value=f"`{warning_id}`", inline=True)
            embed.add_field(name="Action Taken", value=f"**{action_taken.upper()}**", inline=True)

            embed.add_field(
                name="User",
                value=f"{message.author.mention}\n`{message.author} ({message.author.id})`",
                inline=True,
            )
            embed.add_field(name="Channel", value=f"<#{message.channel.id}>", inline=True)
            embed.add_field(name="DM Status", value=f"`{dm_status.upper()}`", inline=True)

            embed.add_field(name="Policy / Profile", value=str(policy_name), inline=True)
            embed.add_field(name="Rule Triggered", value=f"`{violation['rule']}`", inline=True)
            embed.add_field(name="Moderator", value="PB HERO AutoMod", inline=True)

            embed.add_field(name="Reason", value=violation["reason"], inline=False)

            if perm_error:
                embed.add_field(
                    name="⚠️ Permission Warning",
                    value=f"```fix\n{perm_error}\n```",
                    inline=False,
                )

            if message.content:
                clean_content = message.content[:500] + ("..." if len(message.content) > 500 else "")
                embed.add_field(name="Content Preview", value=f"```{clean_content}```", inline=False)

            embed.set_footer(text=f"Incident ID: {message.id} • PB HERO Security System")
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except Exception as e:
            logger.error("Failed to send mod log: %s", str(e))

    async def simulate_policy(
        self,
        channel_id: int,
        role_ids: list[int],
        content: str,
        has_attachment: bool = False,
        attachment_type: str = "image",
    ) -> dict:
        """
        Simulate policy check for the dashboard policy tester using evaluate_message_policy.
        """
        if not self._cache_valid:
            await self.refresh_cache()

        policy = self._policy_cache.get(channel_id)
        if not policy:
            session = await get_session_direct()
            try:
                db_pol = await ChannelPolicyRepo.get_for_channel(session, channel_id)
                if db_pol:
                    policy = self._policy_to_dict(db_pol)
            finally:
                await session.close()

        if not policy:
            return {
                "allowed": True,
                "decision": "allow",
                "reason": "No policy configured for this channel (all allowed)",
                "matched_rule": None,
                "effective_value": "allow",
                "matched_policy": "Default",
            }

        # Check exemptions by role
        admin_roles = set(self._server_config_cache.get("admin_role_ids", []))
        mod_roles = set(self._server_config_cache.get("moderator_role_ids", []))
        exempt_roles = admin_roles | mod_roles

        for role_id in role_ids:
            try:
                if int(role_id) in exempt_roles:
                    return {
                        "allowed": True,
                        "decision": "exempt",
                        "reason": "Exempt from moderation: user has moderator/admin role",
                        "matched_rule": "role_exemption",
                        "effective_value": "allow",
                        "matched_policy": "Role Exemption",
                    }
            except (ValueError, TypeError):
                pass

        attachments_mock = []
        if has_attachment:
            ext_map = {"image": "test.png", "video": "test.mp4", "file": "test.pdf"}
            attachments_mock = [{"filename": ext_map.get(attachment_type, "test.bin"), "content_type": f"{attachment_type}/test"}]

        return evaluate_message_policy(
            policy=policy,
            content=content,
            attachments=attachments_mock,
            server_config=self._server_config_cache,
            channel_name=policy.get("channel_name", ""),
        )
