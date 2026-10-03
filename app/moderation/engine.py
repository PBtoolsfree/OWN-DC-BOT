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
            if config:
                self._server_config_cache = {
                    "mod_log_channel_id": config.mod_log_channel_id,
                    "admin_role_ids": json.loads(config.admin_role_ids) if config.admin_role_ids else [],
                    "moderator_role_ids": json.loads(config.moderator_role_ids) if config.moderator_role_ids else [],
                    "global_allowed_domains": json.loads(config.global_allowed_domains) if config.global_allowed_domains else [],
                    "warning_message_template": config.warning_message_template,
                }
            else:
                self._server_config_cache = {
                    "mod_log_channel_id": None,
                    "admin_role_ids": [],
                    "moderator_role_ids": [],
                    "global_allowed_domains": [],
                    "warning_message_template": None,
                }

            self._cache_valid = True
            logger.info("Moderation cache refreshed: %d policies, %d exemptions",
                        len(self._policy_cache), len(self._exemption_cache))
        finally:
            await session.close()

    def _policy_to_dict(self, policy) -> dict:
        """Convert a ChannelPolicy model to a dict for processing."""
        allowed_domains = []
        if policy.allowed_domains:
            try:
                allowed_domains = json.loads(policy.allowed_domains)
            except json.JSONDecodeError:
                allowed_domains = [d.strip() for d in policy.allowed_domains.split(",") if d.strip()]

        return {
            "channel_id": policy.discord_channel_id,
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
            "allowed_domains": allowed_domains,
            "warning_message": policy.warning_message,
            "log_violations": policy.log_violations,
            "delete_violations": policy.delete_violations,
            "warn_on_violation": policy.warn_on_violation,
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

        # Run checks
        violation = None

        # 1. Check mentions
        mention_violation = check_mentions(message, policy)
        if mention_violation:
            violation = mention_violation

        # 2. Check links
        if not violation and policy.get("allow_links") == "deny":
            if contains_url(message.content):
                # Check allowlist
                urls = filter_urls(message.content, policy.get("allowed_domains", []) +
                                   self._server_config_cache.get("global_allowed_domains", []))
                blocked_urls = [u for u in urls if not u["allowed"]]
                if blocked_urls:
                    violation = {
                        "reason": "Links are not allowed in this channel",
                        "rule": "links_denied",
                        "urls": [u["url"] for u in blocked_urls],
                    }

        # 3. Check attachments
        if not violation and message.attachments:
            att_violations = validate_attachments(message.attachments, policy)
            if att_violations:
                violation = att_violations[0]  # Report first violation

        # 4. Check stickers
        if not violation and message.stickers and policy.get("allow_stickers") == "deny":
            violation = {
                "reason": "Stickers are not allowed in this channel",
                "rule": "stickers_denied",
            }

        # 5. Check text-only messages without required content
        if not violation and policy.get("allow_text") == "deny":
            # If text is denied, message must contain allowed media
            has_allowed_content = bool(message.attachments) or bool(message.stickers)
            if not has_allowed_content and message.content.strip():
                violation = {
                    "reason": "Text messages are not allowed in this channel",
                    "rule": "text_denied",
                }

        return violation

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

        # Send warning
        if policy.get("warn_on_violation", True):
            warning_text = policy.get("warning_message") or \
                           self._server_config_cache.get("warning_message_template") or \
                           f"⚠️ {violation['reason']}"
            try:
                warn_msg = await message.channel.send(
                    f"{message.author.mention} {warning_text}",
                    delete_after=10,
                    allowed_mentions=discord.AllowedMentions(users=[message.author]),
                )
            except discord.Forbidden:
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

        # Log to mod log channel
        await self._send_mod_log(message, violation)

    async def _send_mod_log(self, message: discord.Message, violation: dict) -> None:
        """Send violation to the moderation log channel."""
        mod_log_id = self._server_config_cache.get("mod_log_channel_id")
        if not mod_log_id:
            return

        channel = self.bot.get_channel(mod_log_id)
        if not channel:
            return

        try:
            embed = discord.Embed(
                title="🛡️ Message Blocked",
                color=0xE74C3C,
                timestamp=message.created_at,
            )
            embed.add_field(name="User", value=f"{message.author.mention} ({message.author})", inline=True)
            embed.add_field(name="Channel", value=f"<#{message.channel.id}>", inline=True)
            embed.add_field(name="Rule", value=violation["rule"], inline=True)
            embed.add_field(name="Reason", value=violation["reason"], inline=False)
            if message.content:
                embed.add_field(name="Content", value=message.content[:500], inline=False)
            embed.set_footer(text=f"Message ID: {message.id}")

            await channel.send(embed=embed)
        except Exception as e:
            logger.error("Failed to send mod log: %s", str(e))

    async def simulate_policy(self, channel_id: int, role_ids: list[int],
                              content: str, has_attachment: bool = False,
                              attachment_type: str = "image") -> dict:
        """
        Simulate policy check for the dashboard policy tester.

        Returns dict with allowed/blocked status and reason.
        """
        if not self._cache_valid:
            await self.refresh_cache()

        policy = self._policy_cache.get(channel_id)
        if not policy:
            return {"allowed": True, "reason": "No policy configured for this channel"}

        # Check exemptions by role
        admin_roles = set(self._server_config_cache.get("admin_role_ids", []))
        mod_roles = set(self._server_config_cache.get("moderator_role_ids", []))
        exempt_roles = admin_roles | mod_roles

        for role_id in role_ids:
            if role_id in exempt_roles:
                return {"allowed": True, "reason": "Exempt: moderator/admin role"}

        # Check mentions
        if "@everyone" in content and policy.get("allow_everyone") == "deny":
            return {"allowed": False, "reason": "@everyone mentions are blocked in this channel"}
        if "@here" in content and policy.get("allow_here") == "deny":
            return {"allowed": False, "reason": "@here mentions are blocked in this channel"}

        # Check links
        if policy.get("allow_links") == "deny" and contains_url(content):
            urls = filter_urls(content, policy.get("allowed_domains", []))
            blocked = [u for u in urls if not u["allowed"]]
            if blocked:
                return {"allowed": False, "reason": f"Links are blocked. Detected: {blocked[0]['url']}"}

        # Check text
        if policy.get("allow_text") == "deny" and content.strip() and not has_attachment:
            return {"allowed": False, "reason": "Text messages are blocked in this channel"}

        # Check attachment
        if has_attachment:
            if attachment_type == "image" and policy.get("allow_images") == "deny":
                return {"allowed": False, "reason": "Images are blocked in this channel"}
            elif attachment_type == "video" and policy.get("allow_videos") == "deny":
                return {"allowed": False, "reason": "Videos are blocked in this channel"}
            elif attachment_type == "file" and policy.get("allow_files") == "deny":
                return {"allowed": False, "reason": "Files are blocked in this channel"}

        return {"allowed": True, "reason": "Message passes all policy checks"}
