"""
PB HERO Centralized Policy Evaluator.

Pure, deterministic evaluation function shared across:
1. Discord Moderation Engine (real-time message filtering)
2. Policy Tester (dry-run diagnostics on dashboard)
3. API Simulation & Testing
"""

import re
from typing import Any, Dict, List, Optional

from app.database.serializers import deserialize_json_field, normalize_domain
from app.moderation.url_detector import contains_url, filter_urls

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".flv", ".wmv"}


def resolve_rule_value(val: Any, default_if_inherit: str = "allow") -> str:
    """Resolve an enum/string/inherit to 'allow' or 'deny'."""
    if not val:
        return default_if_inherit
    v = val.value.lower() if hasattr(val, "value") else str(val).lower()
    if v == "inherit":
        return default_if_inherit
    return v


def evaluate_message_policy(
    policy: Dict[str, Any],
    content: str = "",
    attachments: Optional[List[Dict[str, Any]]] = None,
    stickers: Optional[List[Any]] = None,
    role_mentions: Optional[List[Any]] = None,
    user_mentions: Optional[List[Any]] = None,
    server_config: Optional[Dict[str, Any]] = None,
    channel_name: str = "",
) -> Dict[str, Any]:
    """
    Evaluate message content against channel policy rules.

    Returns structured decision:
    {
      "allowed": bool,
      "reason": str,
      "matched_rule": str or None,
      "effective_value": "allow" | "deny" | "inherit",
      "matched_policy": str,
      "urls": list
    }
    """
    matched_policy = (
        policy.get("preset_name")
        or policy.get("channel_name")
        or channel_name
        or "Channel Policy"
    )

    # 1. Resolve Effective Values
    eff_text = resolve_rule_value(policy.get("allow_text"), default_if_inherit="allow")
    eff_links = resolve_rule_value(policy.get("allow_links"), default_if_inherit="allow")
    eff_images = resolve_rule_value(policy.get("allow_images"), default_if_inherit="allow")
    eff_videos = resolve_rule_value(policy.get("allow_videos"), default_if_inherit="allow")
    eff_files = resolve_rule_value(policy.get("allow_files"), default_if_inherit="allow")
    eff_stickers = resolve_rule_value(policy.get("allow_stickers"), default_if_inherit="allow")
    eff_everyone = resolve_rule_value(policy.get("allow_everyone"), default_if_inherit="deny")
    eff_here = resolve_rule_value(policy.get("allow_here"), default_if_inherit="deny")
    eff_role_mentions = resolve_rule_value(policy.get("allow_role_mentions"), default_if_inherit="allow")
    eff_user_mentions = resolve_rule_value(policy.get("allow_user_mentions"), default_if_inherit="allow")

    # 2. Check @everyone and @here Mentions
    if eff_everyone == "deny" and "@everyone" in content:
        return {
            "allowed": False,
            "reason": "@everyone mentions are not permitted in this channel",
            "matched_rule": "allow_everyone",
            "effective_value": "deny",
            "matched_policy": matched_policy,
        }

    if eff_here == "deny" and "@here" in content:
        return {
            "allowed": False,
            "reason": "@here mentions are not permitted in this channel",
            "matched_rule": "allow_here",
            "effective_value": "deny",
            "matched_policy": matched_policy,
        }

    # 3. Check Role Mentions (<@&role_id>)
    has_role_ping = bool(role_mentions) or bool(re.search(r"<@&[0-9]+>", content))
    if eff_role_mentions == "deny" and has_role_ping:
        return {
            "allowed": False,
            "reason": "Role mentions are not permitted in this channel",
            "matched_rule": "allow_role_mentions",
            "effective_value": "deny",
            "matched_policy": matched_policy,
        }

    # 4. Check User Mentions (<@!?[0-9]+>)
    has_user_ping = bool(user_mentions) or bool(re.search(r"<@!?[0-9]+>", content))
    if eff_user_mentions == "deny" and has_user_ping:
        return {
            "allowed": False,
            "reason": "User mentions are not permitted in this channel",
            "matched_rule": "allow_user_mentions",
            "effective_value": "deny",
            "matched_policy": matched_policy,
        }

    # 5. Check Links & Allowed Domains
    if eff_links == "deny" and contains_url(content):
        # Prepare combined allowed domains
        raw_pol_domains = policy.get("allowed_domains") or []
        pol_domains = deserialize_json_field(raw_pol_domains, default=[])
        srv_domains = []
        if server_config and "global_allowed_domains" in server_config:
            srv_domains = deserialize_json_field(server_config["global_allowed_domains"], default=[])

        all_allowed_domains = [normalize_domain(d) for d in (pol_domains + srv_domains) if normalize_domain(d)]
        analyzed_urls = filter_urls(content, all_allowed_domains)
        blocked_urls = [u["url"] for u in analyzed_urls if not u["allowed"]]

        if blocked_urls:
            return {
                "allowed": False,
                "reason": f"Links are not permitted in this channel (blocked: {blocked_urls[0]})",
                "matched_rule": "allow_links",
                "effective_value": "deny",
                "matched_policy": matched_policy,
                "urls": blocked_urls,
            }

    # 6. Check Attachments
    has_allowed_media = False
    if attachments:
        for att in attachments:
            fname = (att.get("filename") or "").lower()
            ctype = (att.get("content_type") or "").lower()

            is_image = any(fname.endswith(ext) for ext in IMAGE_EXTENSIONS) or ctype.startswith("image/")
            is_video = any(fname.endswith(ext) for ext in VIDEO_EXTENSIONS) or ctype.startswith("video/")

            if is_image:
                if eff_images == "deny":
                    return {
                        "allowed": False,
                        "reason": "Images are not permitted in this channel",
                        "matched_rule": "allow_images",
                        "effective_value": "deny",
                        "matched_policy": matched_policy,
                    }
                has_allowed_media = True
            elif is_video:
                if eff_videos == "deny":
                    return {
                        "allowed": False,
                        "reason": "Videos are not permitted in this channel",
                        "matched_rule": "allow_videos",
                        "effective_value": "deny",
                        "matched_policy": matched_policy,
                    }
                has_allowed_media = True
            else:
                if eff_files == "deny":
                    return {
                        "allowed": False,
                        "reason": "Files and documents are not permitted in this channel",
                        "matched_rule": "allow_files",
                        "effective_value": "deny",
                        "matched_policy": matched_policy,
                    }
                has_allowed_media = True

    # 7. Check Stickers
    if stickers and eff_stickers == "deny":
        return {
            "allowed": False,
            "reason": "Stickers are not permitted in this channel",
            "matched_rule": "allow_stickers",
            "effective_value": "deny",
            "matched_policy": matched_policy,
        }

    # 8. Check Text Messages
    has_text = bool(content and content.strip())
    if eff_text == "deny" and has_text and not has_allowed_media and not stickers:
        return {
            "allowed": False,
            "reason": "Text messages are not permitted in this channel",
            "matched_rule": "allow_text",
            "effective_value": "deny",
            "matched_policy": matched_policy,
        }

    return {
        "allowed": True,
        "reason": "Message permitted by channel policy",
        "matched_rule": None,
        "effective_value": "allow",
        "matched_policy": matched_policy,
    }
