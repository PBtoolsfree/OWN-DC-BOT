"""
PB HERO Centralized Policy Evaluator.

Pure, deterministic evaluation function shared across:
1. Discord Moderation Engine (real-time message filtering)
2. Policy Tester (dry-run diagnostics on dashboard)
3. API Simulation & Testing
"""

import re
import time
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


class SpamTracker:
    """
    Deterministic message rate and spam tracker.
    Maintains per-guild, per-channel, per-user message timestamps.
    """

    def __init__(self):
        # (guild_id, channel_id, user_id) -> list of timestamp floats
        self._history: Dict[tuple[int, int, int], List[float]] = {}
        # (guild_id, user_id) -> list of timestamp floats for guild-wide rate/flood
        self._guild_history: Dict[tuple[int, int], List[float]] = {}
        # (guild_id, channel_id, user_id) -> list of (timestamp, content)
        self._content_history: Dict[tuple[int, int, int], List[tuple[float, str]]] = {}

    def record_and_count(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        timestamp: float,
        window_seconds: float,
        content: str = "",
    ) -> int:
        """
        Record a qualifying message and return the count of messages
        from this user in this channel within [timestamp - window_seconds, timestamp].
        """
        gid, cid, uid = int(guild_id), int(channel_id), int(user_id)
        key = (gid, cid, uid)
        cutoff = float(timestamp) - float(window_seconds)

        # Per channel history
        current = [ts for ts in self._history.get(key, []) if ts >= cutoff]
        current.append(float(timestamp))
        self._history[key] = current

        # Server-wide history
        g_key = (gid, uid)
        g_current = [ts for ts in self._guild_history.get(g_key, []) if ts >= cutoff]
        g_current.append(float(timestamp))
        self._guild_history[g_key] = g_current

        # Content history
        if content:
            c_current = [(ts, txt) for ts, txt in self._content_history.get(key, []) if ts >= cutoff]
            c_current.append((float(timestamp), content))
            self._content_history[key] = c_current

        return len(current)

    def check_count(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        timestamp: float,
        window_seconds: float,
    ) -> int:
        """Get count within window without recording a new message."""
        gid, cid, uid = int(guild_id), int(channel_id), int(user_id)
        key = (gid, cid, uid)
        cutoff = float(timestamp) - float(window_seconds)
        return sum(1 for ts in self._history.get(key, []) if ts >= cutoff)

    def reset_user(self, guild_id: int, channel_id: int, user_id: int) -> None:
        """Reset history for a user after enforcement."""
        gid, cid, uid = int(guild_id), int(channel_id), int(user_id)
        self._history.pop((gid, cid, uid), None)
        self._content_history.pop((gid, cid, uid), None)
        self._guild_history.pop((gid, uid), None)

    def clear(self) -> None:
        """Clear all tracking state."""
        self._history.clear()
        self._guild_history.clear()
        self._content_history.clear()

    def count_repeated_messages(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        content: str,
        timestamp: float,
        window_seconds: float,
    ) -> int:
        """Count identical messages sent by this user within window."""
        if not content:
            return 0
        gid, cid, uid = int(guild_id), int(channel_id), int(user_id)
        key = (gid, cid, uid)
        cutoff = float(timestamp) - float(window_seconds)
        clean_content = content.strip().lower()
        items = self._content_history.get(key, [])
        return sum(1 for ts, txt in items if ts >= cutoff and txt.strip().lower() == clean_content)


def parse_action_string(action_str: Optional[str]) -> Dict[str, bool]:
    """
    Parses any action string (e.g., 'delete_timeout', 'DELETE + WARN', 'delete', 'DELETE ONLY')
    into individual booleans: delete, warn, timeout, kick, ban.
    """
    if not action_str:
        return {"delete": False, "warn": False, "timeout": False, "kick": False, "ban": False}
    normalized = action_str.lower().replace("+", " ").replace("_", " ").replace(",", " ")
    tokens = set(normalized.split())
    return {
        "delete": "delete" in tokens,
        "warn": "warn" in tokens,
        "timeout": "timeout" in tokens,
        "kick": "kick" in tokens,
        "ban": "ban" in tokens,
    }


def evaluate_automod_rules(
    rules: List[Dict[str, Any]],
    content: str = "",
    attachments: Optional[List[Any]] = None,
    mentions_count: int = 0,
    *,
    guild_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    user_id: Optional[int] = None,
    timestamp: Optional[Any] = None,
    spam_tracker: Optional[SpamTracker] = None,
    is_bot: bool = False,
    is_dm: bool = False,
    category_id: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """
    Evaluate message against enabled automod rules.
    Returns infraction dict or None if no infraction detected.
    """
    # Convert timestamp
    current_ts = time.time()
    if timestamp is not None:
        if hasattr(timestamp, "timestamp"):
            current_ts = timestamp.timestamp()
        else:
            try:
                current_ts = float(timestamp)
            except (ValueError, TypeError):
                current_ts = time.time()

    for rule in rules:
        if not rule.get("enabled", True):
            continue

        rtype = rule.get("rule_type", "")

        # Extract parameters with robust alias handling (threshold vs threshold_count, time_window vs window_seconds)
        raw_thresh = rule.get("threshold_count")
        if raw_thresh is None:
            raw_thresh = rule.get("threshold", 5)
        try:
            threshold = int(raw_thresh)
        except (ValueError, TypeError):
            threshold = 5

        raw_win = rule.get("window_seconds")
        if raw_win is None:
            raw_win = rule.get("time_window_seconds")
        if raw_win is None:
            raw_win = rule.get("time_window", 5)
        try:
            time_window = int(raw_win)
        except (ValueError, TypeError):
            time_window = 5

        action = rule.get("action", "delete_warn")

        raw_dur = rule.get("action_duration")
        if raw_dur is None:
            raw_dur = rule.get("timeout_duration")
        if raw_dur is None:
            raw_dur = rule.get("duration_seconds", 600)
        try:
            timeout_duration = int(raw_dur)
        except (ValueError, TypeError):
            timeout_duration = 600

        severity = rule.get("severity", "medium")
        rule_name = rule.get("name") or rtype.replace("_", " ").title()

        # Check Scope (global vs specific channels/categories)
        scope = rule.get("scope", "global")
        if scope == "channels" and channel_id is not None:
            raw_chans = rule.get("channels") or []
            if isinstance(raw_chans, str):
                raw_chans = deserialize_json_field(raw_chans, default=[])
            allowed_channels = {int(c) for c in raw_chans if str(c).isdigit()}
            if allowed_channels and int(channel_id) not in allowed_channels:
                continue
        elif scope == "categories" and category_id is not None:
            raw_cats = rule.get("categories") or []
            if isinstance(raw_cats, str):
                raw_cats = deserialize_json_field(raw_cats, default=[])
            allowed_cats = {str(c).lower() for c in raw_cats}
            if allowed_cats and str(category_id).lower() not in allowed_cats:
                continue

        # 1. Message Spam
        if rtype == "message_spam":
            if is_bot or is_dm or guild_id is None or channel_id is None or user_id is None or spam_tracker is None:
                continue
            count = spam_tracker.record_and_count(
                guild_id=guild_id,
                channel_id=channel_id,
                user_id=user_id,
                timestamp=current_ts,
                window_seconds=time_window,
                content=content or "",
            )
            if count >= threshold:
                return {
                    "matched": True,
                    "rule": "message_spam",
                    "rule_name": rule_name,
                    "reason": f"Message spam detected ({count} messages in {time_window}s, threshold is {threshold})",
                    "action": action,
                    "timeout_duration": timeout_duration,
                    "severity": severity or "medium",
                    "threshold": threshold,
                    "threshold_count": threshold,
                    "time_window": time_window,
                    "window_seconds": time_window,
                    "count": count,
                }

        # 2. Invite Filter
        elif rtype == "invite_filter":
            if re.search(r"(discord\.gg/|discord\.com/invite/)[a-zA-Z0-9]+", content or "", re.IGNORECASE):
                return {
                    "matched": True,
                    "rule": "invite_filter",
                    "rule_name": rule_name,
                    "reason": "Discord invite links are not allowed",
                    "action": action,
                    "timeout_duration": timeout_duration,
                    "severity": severity or "high",
                }

        # 3. Keyword Filter
        elif rtype == "keyword_filter":
            raw_kw = rule.get("custom_keywords") or []
            keywords = deserialize_json_field(raw_kw, default=[]) if isinstance(raw_kw, str) else raw_kw
            for kw in keywords:
                if kw and str(kw).strip().lower() in (content or "").lower():
                    return {
                        "matched": True,
                        "rule": "keyword_filter",
                        "rule_name": rule_name,
                        "reason": f"Message contains blocked keyword: {str(kw).strip()}",
                        "action": action,
                        "timeout_duration": timeout_duration,
                        "severity": severity or "medium",
                    }

        # 4. Mention Spam
        elif rtype == "mention_spam":
            if mentions_count >= threshold:
                return {
                    "matched": True,
                    "rule": "mention_spam",
                    "rule_name": rule_name,
                    "reason": f"Mention spam detected ({mentions_count} mentions, limit is {threshold})",
                    "action": action,
                    "timeout_duration": timeout_duration,
                    "severity": severity or "high",
                }

        # 5. Caps / Character Spam
        elif rtype == "caps_spam":
            if len(content or "") >= 10:
                letters = [c for c in content if c.isalpha()]
                if letters:
                    caps_pct = (sum(1 for c in letters if c.isupper()) / len(letters)) * 100
                    if caps_pct >= threshold:
                        return {
                            "matched": True,
                            "rule": "caps_spam",
                            "rule_name": rule_name,
                            "reason": f"Excessive caps detected ({caps_pct:.0f}%, limit is {threshold}%)",
                            "action": action,
                            "timeout_duration": timeout_duration,
                            "severity": severity or "low",
                        }

        # 6. Attachment Restriction
        elif rtype == "attachment_restriction":
            att_count = len(attachments) if attachments else 0
            if att_count >= threshold:
                return {
                    "matched": True,
                    "rule": "attachment_restriction",
                    "rule_name": rule_name,
                    "reason": f"Attachment limit exceeded ({att_count} attachments, limit is {threshold})",
                    "action": action,
                    "timeout_duration": timeout_duration,
                    "severity": severity or "low",
                }

        # 7. Repeated Message Detection
        elif rtype == "repeated_message":
            if spam_tracker and guild_id and channel_id and user_id and content:
                rep_count = spam_tracker.count_repeated_messages(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=user_id,
                    content=content,
                    timestamp=current_ts,
                    window_seconds=time_window,
                )
                if rep_count >= threshold:
                    return {
                        "matched": True,
                        "rule": "repeated_message",
                        "rule_name": rule_name,
                        "reason": f"Repeated message detected ({rep_count} duplicates in {time_window}s)",
                        "action": action,
                        "timeout_duration": timeout_duration,
                        "severity": severity or "medium",
                    }

        # 8. Flood Protection
        elif rtype == "flood_protection":
            if not is_bot and not is_dm and guild_id is not None and user_id is not None and spam_tracker is not None:
                g_key = (int(guild_id), int(user_id))
                cutoff = current_ts - float(time_window)
                g_timestamps = [ts for ts in spam_tracker._guild_history.get(g_key, []) if ts >= cutoff]
                if len(g_timestamps) >= threshold:
                    return {
                        "matched": True,
                        "rule": "flood_protection",
                        "rule_name": rule_name,
                        "reason": f"Flood protection triggered ({len(g_timestamps)} messages across server in {time_window}s)",
                        "action": action,
                        "timeout_duration": timeout_duration,
                        "severity": severity or "critical",
                    }

        # 9. Link Filter
        elif rtype == "link_filter":
            if contains_url(content or ""):
                return {
                    "matched": True,
                    "rule": "link_filter",
                    "rule_name": rule_name,
                    "reason": "External links are not permitted by automod link filter",
                    "action": action,
                    "timeout_duration": timeout_duration,
                    "severity": severity or "medium",
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

