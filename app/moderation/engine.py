"""
PB HERO Moderation Engine.

Application-side message filtering engine that enforces channel policies.
This complements Discord's native permissions with custom rules.
"""

import json
import logging
from typing import Optional

import discord

from app.database.engine import get_session_direct
from app.database.models import PolicyValue
from app.database.repositories import (
    BlockedMessageRepo,
    ChannelPolicyRepo,
    ExemptionRuleRepo,
    RoleOverride,
    ServerConfigRepo,
)
from app.moderation.attachment_validator import validate_attachments
from app.moderation.mention_filter import check_mentions
from app.moderation.url_detector import contains_url, detect_urls, filter_urls

logger = logging.getLogger("pbhero.moderation")


class ModerationEngine:
    """
    Server-side message filtering and policy enforcement engine.

    Processes every message in the configured guild against channel-specific
    policies. Supports exemptions for roles, users, and channels.
    """

    def __init__(self, bot: discord.Client, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self._policy_cache: dict = {}
        self._exemption_cache: dict = {}
        self._server_config_cache: dict = {}
        self._cache_valid = False

    async def refresh_cache(self) -> None:
        """Refresh the policy and exemption caches."""
        session = await get_session_direct()
        try:
            # Load all policies
            policies = await ChannelPolicyRepo.get_all(session)
            self._policy_cache = {}
            for policy in policies:
                if policy.enabled:
                    self._policy_cache[policy.discord_channel_id] = self._policy_to_dict(policy)

            # Load exemptions
            exemptions = await ExemptionRuleRepo.get_all(session)
            self._exemption_cache = {}
            for exemption in exemptions:
                key = f"{exemption.rule_type}:{exemption.target_id}"
                if key not in self._exemption_cache:
                    self._exemption_cache[key] = []
                self._exemption_cache[key].append(exemption.exempt_from)

            # Load server config
            config = await ServerConfigRepo.get(session)
            from app.database.serializers import deserialize_json_field

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
                }
            else:
                self._server_config_cache = {
                    "mod_log_channel_id": None,
                    "admin_role_ids": [],
                    "moderator_role_ids": [],
                    "global_allowed_domains": [],
                    "warning_message_template": None,
                    "mod_log_events": default_log_events,
                }

            self._cache_valid = True
            logger.info("Moderation cache refreshed: %d policies, %d exemptions",
                        len(self._policy_cache), len(self._exemption_cache))
        finally:
            await session.close()

    def _policy_to_dict(self, policy) -> dict:
        """Convert a ChannelPolicy model to a dict for processing."""
        from app.database.serializers import deserialize_json_field

        return {
            "channel_id": policy.discord_channel_id,
            "channel_name": policy.channel_name,
            "category_name": policy.category_name,
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
            "allowed_domains": deserialize_json_field(policy.allowed_domains, default=[]),
            "warning_message": policy.warning_message,
            "log_violations": getattr(policy, "log_violations", True),
            "delete_violations": getattr(policy, "delete_violations", True),
            "warn_on_violation": getattr(policy, "warn_on_violation", True),
            "send_dm_warning": getattr(policy, "send_dm_warning", False),
        }

    def _is_exempt(self, member: discord.Member) -> bool:
        """Check if a member is exempt from moderation policies."""
        # Server owner is always exempt
        if member.guild.owner_id == member.id:
            return True

        # Bot itself is exempt (prevent loops)
        if member.bot:
            return True

        # Check user exemption
        user_key = f"user:{member.id}"
        if user_key in self._exemption_cache:
            return True

        # Check role exemptions
        admin_roles = set(self._server_config_cache.get("admin_role_ids", []))
        mod_roles = set(self._server_config_cache.get("moderator_role_ids", []))
        exempt_roles = admin_roles | mod_roles

        for role in member.roles:
            if role.id in exempt_roles:
                return True
            role_key = f"role:{role.id}"
            if role_key in self._exemption_cache:
                return True

        # Administrator permission exempts
        if member.guild_permissions.administrator:
            return True

        return False

    async def process_message(self, message: discord.Message) -> Optional[dict]:
        """
        Process a message against channel policies.

        Returns violation dict if blocked, None if allowed.
        """
        # Only process guild messages from the configured guild
        if not message.guild or message.guild.id != self.guild_id:
            return None

        # Skip bot messages
        if message.author.bot:
            return None

        # Refresh cache if needed
        if not self._cache_valid:
            await self.refresh_cache()

        # Get policy for this channel
        channel_id = message.channel.id
        policy = self._policy_cache.get(channel_id)
        if not policy:
            return None  # No policy = allow all

        # Check exemptions
        if isinstance(message.author, discord.Member) and self._is_exempt(message.author):
            return None

        # Check channel exemption
        channel_key = f"channel:{channel_id}"
        if channel_key in self._exemption_cache:
            return None

        # Run checks via unified evaluator
        from app.moderation.evaluator import evaluate_message_policy

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
            return {
                "reason": eval_result["reason"],
                "rule": eval_result.get("matched_rule") or "policy_violation",
                "urls": eval_result.get("urls", []),
                "matched_policy": eval_result.get("matched_policy"),
            }

        return None

    async def handle_violation(self, message: discord.Message, violation: dict) -> None:
        """Handle a policy violation: delete, warn, log."""
        policy = self._policy_cache.get(message.channel.id, {})

        # Delete the message
        if policy.get("delete_violations", True):
            try:
                await message.delete()
                logger.info("Deleted message %d from %s in #%s: %s",
                           message.id, message.author, message.channel.name, violation["reason"])
            except discord.Forbidden:
                logger.warning("Cannot delete message in #%s: missing permissions", message.channel.name)
            except discord.NotFound:
                pass

        # Send in-channel warning
        if policy.get("warn_on_violation", True):
            warning_text = policy.get("warning_message") or \
                           self._server_config_cache.get("warning_message_template") or \
                           f"⚠️ {violation['reason']}"
            try:
                await message.channel.send(
                    f"{message.author.mention} {warning_text}",
                    delete_after=10,
                    allowed_mentions=discord.AllowedMentions(users=[message.author]),
                )
            except discord.Forbidden:
                pass

        # Send DM warning if enabled
        if policy.get("send_dm_warning", False):
            try:
                dm_channel = await message.author.create_dm()
                await dm_channel.send(
                    f"⚠️ **PB HERO AutoMod Notification**: Your message in **#{message.channel.name}** was removed.\n"
                    f"> **Reason**: {violation['reason']}\n"
                    f"> **Rule**: `{violation.get('rule', 'Policy Rule')}`"
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        # Log to database
        if policy.get("log_violations", True):
            session = await get_session_direct()
            try:
                await BlockedMessageRepo.create(
                    session=session,
                    channel_id=message.channel.id,
                    user_id=message.author.id,
                    username=str(message.author),
                    message_id=message.id,
                    content_preview=message.content[:200] if message.content else None,
                    reason=violation["reason"],
                    rule=violation["rule"],
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("Failed to log blocked message: %s", str(e))
            finally:
                await session.close()

        # Log to Discord mod log channel
        await self._send_mod_log(message, violation)

    async def _send_mod_log(self, message: discord.Message, violation: dict) -> None:
        """Send violation to the moderation log channel."""
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
                logger.warning("Bot lacks Send Messages or Embed Links permission in mod log channel #%s", channel.name)
                return

        policy = self._policy_cache.get(message.channel.id, {})
        policy_name = violation.get("matched_policy") or policy.get("preset_name") or "Channel Policy"

        try:
            embed = discord.Embed(
                title="🛡️ AUTO MODERATION",
                color=0xED4245,
                timestamp=message.created_at,
            )
            embed.add_field(name="Action", value="`MESSAGE BLOCKED`", inline=True)
            embed.add_field(name="User", value=f"{message.author.mention}\n`{message.author} ({message.author.id})`", inline=True)
            embed.add_field(name="Channel", value=f"<#{message.channel.id}>", inline=True)
            embed.add_field(name="Reason", value=violation["reason"], inline=False)
            embed.add_field(name="Policy", value=str(policy_name), inline=True)
            embed.add_field(name="Rule", value=f"`{violation['rule']}`", inline=True)
            embed.add_field(name="Moderator", value="PB HERO AutoMod", inline=True)
            if message.content:
                clean_content = message.content[:500] + ("..." if len(message.content) > 500 else "")
                embed.add_field(name="Content", value=f"```{clean_content}```", inline=False)
            embed.set_footer(text=f"Incident ID: {message.id} • PB HERO Security")

            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except Exception as e:
            logger.error("Failed to send mod log: %s", str(e))

    async def simulate_policy(self, channel_id: int, role_ids: list[int],
                              content: str, has_attachment: bool = False,
                              attachment_type: str = "image") -> dict:
        """
        Simulate policy check for the dashboard policy tester using evaluate_message_policy.
        """
        if not self._cache_valid:
            await self.refresh_cache()

        policy = self._policy_cache.get(channel_id)
        if not policy:
            # Check DB directly in case channel hasn't loaded in cache yet
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

        from app.moderation.evaluator import evaluate_message_policy
        return evaluate_message_policy(
            policy=policy,
            content=content,
            attachments=attachments_mock,
            server_config=self._server_config_cache,
            channel_name=policy.get("channel_name", ""),
        )
