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
            "decision": "deny",
            "reason": "@everyone mentions are not permitted in this channel",
            "matched_rule": "allow_everyone",
            "effective_value": "deny",
            "matched_policy": matched_policy,
        }

    if eff_here == "deny" and "@here" in content:
        return {
            "allowed": False,
            "decision": "deny",
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
            "decision": "deny",
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
            "decision": "deny",
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
                "decision": "deny",
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
                        "decision": "deny",
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
                        "decision": "deny",
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
                        "decision": "deny",
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
            "decision": "deny",
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
            "decision": "deny",
            "reason": "Text messages are not permitted in this channel",
            "matched_rule": "allow_text",
            "effective_value": "deny",
            "matched_policy": matched_policy,
        }

    return {
        "allowed": True,
        "decision": "allow",
        "reason": "Message permitted by channel policy",
        "matched_rule": None,
        "effective_value": "allow",
        "matched_policy": matched_policy,
    }


def evaluate_voice_policy(
    policy: Dict[str, Any],
    action: str,
    channel_name: str = "",
) -> Dict[str, Any]:
    """
    Evaluate voice permissions against channel policy.

    Actions supported:
    'connect', 'speak', 'video', 'stream', 'soundboard', 'voice_activity',
    'priority_speaker', 'mute_members', 'deafen_members', 'move_members'
    """
    matched_policy = (
        policy.get("preset_name")
        or policy.get("channel_name")
        or channel_name
        or "Voice Policy"
    )

    action_map = {
        "connect": ("allow_connect", "Connecting to this voice channel is not permitted"),
        "speak": ("allow_speak", "Speaking is not permitted in this voice channel"),
        "video": ("allow_video", "Video cameras are not permitted in this voice channel"),
        "stream": ("allow_stream", "Screen sharing/streaming is not permitted in this voice channel"),
        "soundboard": ("allow_soundboard", "Soundboard audio is not permitted in this voice channel"),
        "voice_activity": ("allow_voice_activity", "Voice activity detection is disabled; push-to-talk required"),
        "priority_speaker": ("allow_priority_speaker", "Priority speaker is restricted to moderators"),
        "mute_members": ("allow_mute_members", "Muting members is restricted to moderators"),
        "deafen_members": ("allow_deafen_members", "Deafening members is restricted to moderators"),
        "move_members": ("allow_move_members", "Moving members is restricted to moderators"),
    }

    rule_key, default_reason = action_map.get(action.lower(), (f"allow_{action.lower()}", f"{action} is not permitted"))
    default_val = "deny" if action in ("priority_speaker", "mute_members", "deafen_members", "move_members") else "allow"
    eff_val = resolve_rule_value(policy.get(rule_key), default_if_inherit=default_val)

    if eff_val == "deny":
        return {
            "allowed": False,
            "decision": "deny",
            "reason": default_reason,
            "matched_rule": rule_key,
            "effective_value": "deny",
            "matched_policy": matched_policy,
        }

    return {
        "allowed": True,
        "decision": "allow",
        "reason": f"{action} permitted by voice policy",
        "matched_rule": rule_key,
        "effective_value": "allow",
        "matched_policy": matched_policy,
    }


def evaluate_automod_rules(
    rules: List[Dict[str, Any]],
    content: str,
    attachments: Optional[List[Any]] = None,
    mentions_count: int = 0,
) -> Optional[Dict[str, Any]]:
    """
    Evaluate message against enabled automod rules.
    Returns infraction dict or None if no infraction detected.
    """
    for rule in rules:
        if not rule.get("enabled", True):
            continue

        rtype = rule.get("rule_type", "")

        # 1. Invite Filter
        if rtype == "invite_filter":
            if re.search(r"(discord\.gg/|discord\.com/invite/)[a-zA-Z0-9]+", content, re.IGNORECASE):
                return {
                    "matched": True,
                    "rule": "invite_filter",
                    "rule_name": rule.get("name", "Invite Link Filter"),
                    "reason": "Discord invite links are not allowed",
                    "action": rule.get("action", "delete_warn"),
                    "timeout_duration": rule.get("timeout_duration", 600),
                    "severity": rule.get("severity", "high"),
                }

        # 2. Keyword Filter
        elif rtype == "keyword_filter":
            raw_kw = rule.get("custom_keywords") or []
            keywords = deserialize_json_field(raw_kw, default=[])
            for kw in keywords:
                if kw and kw.strip().lower() in content.lower():
                    return {
                        "matched": True,
                        "rule": "keyword_filter",
                        "rule_name": rule.get("name", "Keyword Filter"),
                        "reason": f"Message contains blocked keyword: {kw.strip()}",
                        "action": rule.get("action", "delete_warn"),
                        "timeout_duration": rule.get("timeout_duration", 600),
                        "severity": rule.get("severity", "medium"),
                    }

        # 3. Mention Spam
        elif rtype == "mention_spam":
            threshold = rule.get("threshold", 5)
            if mentions_count >= threshold:
                return {
                    "matched": True,
                    "rule": "mention_spam",
                    "rule_name": rule.get("name", "Mention Spam"),
                    "reason": f"Mention spam detected ({mentions_count} mentions, limit is {threshold})",
                    "action": rule.get("action", "delete_timeout"),
                    "timeout_duration": rule.get("timeout_duration", 600),
                    "severity": rule.get("severity", "high"),
                }

        # 4. Caps Spam
        elif rtype == "caps_spam":
            threshold = rule.get("threshold", 70)
            if len(content) >= 10:
                letters = [c for c in content if c.isalpha()]
                if letters:
                    caps_pct = (sum(1 for c in letters if c.isupper()) / len(letters)) * 100
                    if caps_pct >= threshold:
                        return {
                            "matched": True,
                            "rule": "caps_spam",
                            "rule_name": rule.get("name", "Caps / Character Spam"),
                            "reason": f"Excessive caps detected ({caps_pct:.0f}%, limit is {threshold}%)",
                            "action": rule.get("action", "delete_warn"),
                            "timeout_duration": rule.get("timeout_duration", 300),
                            "severity": rule.get("severity", "low"),
                        }

    return None


def generate_case_id() -> str:
    """Generate a clean, readable case identifier, e.g. CASE-2026-A1B2."""
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"CASE-{now.year}-{short_uuid}"


def generate_warning_id() -> str:
    """Generate a clean, readable warning identifier, e.g. WARN-2026-A1B2."""
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"WARN-{now.year}-{short_uuid}"


async def check_exemption_bypass(
    db_session,
    user_id: Any,
    user_roles: List[Any],
    is_bot: bool = False,
    channel_id: Optional[Any] = None,
    category_id: Optional[Any] = None,
    filter_type: str = "links",
) -> Dict[str, Any]:
    """
    Check if an infraction bypasses moderation based on granular exemptions and precedence:
    1. Explicit User
    2. Role
    3. Bot
    4. Channel
    5. Category
    """
    from app.database.repositories import ModerationExemptionRepo
    exemptions = await ModerationExemptionRepo.get_all(db_session)
    user_id_str = str(user_id)
    role_id_strs = {str(r) for r in user_roles}
    chan_id_str = str(channel_id) if channel_id else None
    cat_id_str = str(category_id) if category_id else None

    def match_filter(ex) -> bool:
        if ex.bypass_all:
            return True
        attr = f"bypass_{filter_type.lower()}"
        if getattr(ex, attr, False):
            return True
        if "link" in filter_type and getattr(ex, "bypass_links", False):
            return True
        if "spam" in filter_type and getattr(ex, "bypass_spam", False):
            return True
        if "mention" in filter_type and getattr(ex, "bypass_mentions", False):
            return True
        if "ban" in filter_type and getattr(ex, "bypass_ban", False):
            return True
        return False

    def match_scope(ex) -> bool:
        if ex.scope == "global":
            return True
        if ex.scope == "channel" and chan_id_str and str(ex.scope_id) == chan_id_str:
            return True
        if ex.scope == "category" and cat_id_str and str(ex.scope_id) == cat_id_str:
            return True
        return False

    # 1. User
    for ex in exemptions:
        if ex.target_type == "user" and str(ex.target_id) == user_id_str and match_scope(ex):
            if match_filter(ex):
                return {"exempt": True, "target_type": "user", "exemption_id": ex.id}

    # 2. Role
    for ex in exemptions:
        if ex.target_type == "role" and str(ex.target_id) in role_id_strs and match_scope(ex):
            if match_filter(ex):
                return {"exempt": True, "target_type": "role", "exemption_id": ex.id}

    # 3. Bot
    if is_bot:
        for ex in exemptions:
            if ex.target_type == "bot" and (str(ex.target_id) == user_id_str or ex.target_id == "all") and match_scope(ex):
                if match_filter(ex):
                    return {"exempt": True, "target_type": "bot", "exemption_id": ex.id}

    # 4. Channel
    for ex in exemptions:
        if ex.target_type == "channel" and chan_id_str and str(ex.target_id) == chan_id_str:
            if match_filter(ex):
                return {"exempt": True, "target_type": "channel", "exemption_id": ex.id}

    # 5. Category
    for ex in exemptions:
        if ex.target_type == "category" and cat_id_str and str(ex.target_id) == cat_id_str:
            if match_filter(ex):
                return {"exempt": True, "target_type": "category", "exemption_id": ex.id}

    return {"exempt": False, "target_type": None, "exemption_id": None}


async def evaluate_infraction(*args, **kwargs):
    """Proxy to engine.evaluate_infraction to avoid circular import."""
    from app.moderation.engine import evaluate_infraction as _eval_inf
    return await _eval_inf(*args, **kwargs)

