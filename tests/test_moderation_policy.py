"""
Tests for PB HERO Moderation Policy System:
- Regression test for sqlite3 list parameter binding error on allowed_domains
- Central JSON field serialization / deserialization
- Policy profiles: built-in presets immutability & custom policy CRUD
- Channel policy upsert, inheritance, and domain normalization
- Shared policy evaluator (ALLOW, DENY, INHERIT, domain allowlists, mentions, attachments)
- Auto-mod log settings persistence
"""

import pytest
from app.database.models import PolicyValue
from app.database.repositories import (
    ChannelPolicyRepo,
    PolicyProfileRepo,
    ServerConfigRepo,
)
from app.database.serializers import (
    deserialize_json_field,
    normalize_domain,
    normalize_domain_list,
    serialize_json_field,
)
from app.moderation.evaluator import evaluate_message_policy


# ─── Part 1: Domain & Serializer Unit Tests ──────────────────────────────────

def test_domain_normalization():
    """Verify standard domain normalization."""
    assert normalize_domain("https://www.YouTube.com/watch?v=123") == "youtube.com"
    assert normalize_domain("http://YOUTU.BE/") == "youtu.be"
    assert normalize_domain("   discord.com/   ") == "discord.com"
    assert normalize_domain("https://SUB.DOMAIN.EXAMPLE.COM/PATH") == "sub.domain.example.com"
    assert normalize_domain("") == ""


def test_domain_list_normalization():
    """Verify deduplication and cleaning of domain lists."""
    raw = [
        "https://www.youtube.com",
        "youtube.com",
        "  youtu.be/ ",
        "HTTP://DISCORD.COM",
        "",
        None,
    ]
    cleaned = normalize_domain_list(raw)
    assert cleaned == ["youtube.com", "youtu.be", "discord.com"]


def test_json_serializers():
    """Verify safe JSON serialization and deserialization."""
    # List serialization
    data = ["youtube.com", "youtu.be"]
    serialized = serialize_json_field(data)
    assert isinstance(serialized, str)
    assert deserialize_json_field(serialized) == ["youtube.com", "youtu.be"]

    # Empty values default to []
    assert deserialize_json_field(None, default=[]) == []
    assert deserialize_json_field("", default=[]) == []
    assert deserialize_json_field("[]", default=[]) == []

    # Safe fallback on invalid json
    assert deserialize_json_field("invalid-not-json", default=[]) == []


# ─── Part 2: Regression Test: SQLite Save with Python List ──────────────────

@pytest.mark.asyncio
async def test_regression_sqlite_save_allowed_domains_list(db_session):
    """
    CRITICAL REGRESSION TEST:
    Reproduce the exact error:
    (sqlite3.ProgrammingError) Error binding parameter: type 'list' is not supported
    Verify that passing a Python list of allowed_domains does NOT throw an error,
    and is stored as valid JSON text in SQLite.
    """
    channel_id = 998877665544332211
    allowed_domains_list = ["youtube.com", "youtu.be", "discord.com"]

    # This upsert MUST succeed without sqlite3.ProgrammingError
    saved = await ChannelPolicyRepo.upsert(
        session=db_session,
        discord_channel_id=channel_id,
        channel_name="test-video-chat",
        category_name="COMMUNITY",
        allow_links=PolicyValue.DENY,
        allowed_domains=allowed_domains_list,  # Python list passed directly
    )
    await db_session.commit()

    assert saved is not None
    assert saved.discord_channel_id == channel_id

    # Retrieve from DB and verify serialization
    reloaded = await ChannelPolicyRepo.get_for_channel(db_session, channel_id)
    assert reloaded is not None
    assert isinstance(reloaded.allowed_domains, str)  # Stored as TEXT

    decoded_domains = deserialize_json_field(reloaded.allowed_domains)
    assert decoded_domains == ["youtube.com", "youtu.be", "discord.com"]


@pytest.mark.asyncio
async def test_save_empty_allowed_domains(db_session):
    """Verify saving empty allowed_domains works cleanly."""
    channel_id = 1122334455
    saved = await ChannelPolicyRepo.upsert(
        session=db_session,
        discord_channel_id=channel_id,
        channel_name="empty-domains-channel",
        allowed_domains=[],
    )
    await db_session.commit()

    reloaded = await ChannelPolicyRepo.get_for_channel(db_session, channel_id)
    assert reloaded is not None
    assert deserialize_json_field(reloaded.allowed_domains) == []


# ─── Part 3: Policy Profiles & Built-in Protection ───────────────────────────

@pytest.mark.asyncio
async def test_builtin_presets_seeded_and_protected(db_session):
    """Verify all 15 built-in presets exist and cannot be deleted or modified."""
    # Seed presets
    await PolicyProfileRepo.create_defaults(db_session)
    await db_session.commit()

    all_profiles = await PolicyProfileRepo.get_all(db_session)
    builtin_names = {p.name for p in all_profiles if p.is_builtin}

    # Verify key presets are present
    expected_presets = {
        "ANNOUNCEMENTS",
        "GENERAL CHAT",
        "IMAGE ONLY",
        "MEDIA",
        "NO LINK CHAT",
        "SUPPORT",
        "BOT COMMANDS",
        "READ ONLY",
        "LINKS ONLY",
        "GIVEAWAY",
        "CLIPS / SHOWCASE",
        "VERIFICATION",
        "STRICT CHAT",
        "FREE DISCUSSION",
        "MODERATOR ONLY",
    }
    assert expected_presets.issubset(builtin_names)

    # Attempt to delete a built-in preset -> must raise ValueError
    announcements = await PolicyProfileRepo.get_by_name(db_session, "ANNOUNCEMENTS")
    assert announcements is not None
    assert announcements.is_builtin is True

    with pytest.raises(ValueError):
        await PolicyProfileRepo.delete(db_session, announcements.id)

    # Attempt to update a built-in preset -> must raise ValueError or return None
    with pytest.raises(ValueError):
        await PolicyProfileRepo.update(db_session, announcements.id, name="MODIFIED")


@pytest.mark.asyncio
async def test_custom_policy_crud_and_duplicate(db_session):
    """Verify custom policy creation, updating, duplication, and deletion."""
    # 1. Create
    custom = await PolicyProfileRepo.create(
        db_session,
        name="SPECIAL COMMUNITY POLICY",
        description="Custom rules for community events",
        category="Events",
        allow_text=PolicyValue.ALLOW,
        allow_links=PolicyValue.DENY,
        allow_images=PolicyValue.ALLOW,
    )
    await db_session.commit()
    assert custom.id is not None
    assert custom.is_builtin is False
    assert custom.category == "Events"

    # 2. Update
    updated = await PolicyProfileRepo.update(
        db_session,
        custom.id,
        description="Updated description",
        category="Community",
    )
    await db_session.commit()
    assert updated.description == "Updated description"
    assert updated.category == "Community"

    # 3. Duplicate
    cloned = await PolicyProfileRepo.duplicate(
        db_session,
        custom.id,
        new_name="SPECIAL COMMUNITY POLICY (Copy)",
    )
    await db_session.commit()
    assert cloned is not None
    assert cloned.name == "SPECIAL COMMUNITY POLICY (Copy)"
    assert cloned.is_builtin is False
    assert cloned.allow_links == PolicyValue.DENY

    # 4. Delete
    deleted = await PolicyProfileRepo.delete(db_session, custom.id)
    await db_session.commit()
    assert deleted is True

    # Verify custom is gone
    check = await PolicyProfileRepo.get_by_id(db_session, custom.id)
    assert check is None


# ─── Part 4: Shared Evaluator Tests (ALLOW, DENY, INHERIT, Rules) ────────────

def test_evaluator_allow_plain_text():
    """Verify normal message in allow policy is permitted."""
    policy = {
        "preset_name": "GENERAL CHAT",
        "allow_text": "allow",
        "allow_links": "allow",
    }
    decision = evaluate_message_policy(policy=policy, content="Hello everyone in PB HERO server!")
    assert decision["allowed"] is True
    assert decision["effective_value"] == "allow"


def test_evaluator_deny_links_with_allowlist_exceptions():
    """
    Verify link filtering:
    - Links DENY
    - Allowed domains: youtube.com, youtu.be
    - youtube.com -> ALLOW
    - randomsite.com -> DENY
    """
    policy = {
        "preset_name": "NO LINK CHAT",
        "allow_text": "allow",
        "allow_links": "deny",
        "allowed_domains": ["youtube.com", "youtu.be"],
    }

    # Allowed YouTube link
    yt_decision = evaluate_message_policy(
        policy=policy,
        content="Watch this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )
    assert yt_decision["allowed"] is True

    # Denied unauthorized link
    bad_decision = evaluate_message_policy(
        policy=policy,
        content="Check this out: https://phishing-site.xyz/login",
    )
    assert bad_decision["allowed"] is False
    assert bad_decision["matched_rule"] == "allow_links"
    assert bad_decision["effective_value"] == "deny"


def test_evaluator_mention_blocking():
    """Verify @everyone, @here, and role mention blocking."""
    policy = {
        "preset_name": "STRICT CHAT",
        "allow_everyone": "deny",
        "allow_here": "deny",
        "allow_role_mentions": "deny",
    }

    # Test @everyone
    ev_dec = evaluate_message_policy(policy=policy, content="Hello @everyone!")
    assert ev_dec["allowed"] is False
    assert ev_dec["matched_rule"] == "allow_everyone"

    # Test @here
    here_dec = evaluate_message_policy(policy=policy, content="Urgent @here!")
    assert here_dec["allowed"] is False
    assert here_dec["matched_rule"] == "allow_here"

    # Test role ping
    role_dec = evaluate_message_policy(policy=policy, content="Pinging role <@&123456789>")
    assert role_dec["allowed"] is False
    assert role_dec["matched_rule"] == "allow_role_mentions"


def test_evaluator_attachment_blocking():
    """Verify attachment type filtering for images, videos, and files."""
    policy = {
        "preset_name": "IMAGE ONLY",
        "allow_text": "deny",
        "allow_images": "allow",
        "allow_videos": "deny",
        "allow_files": "deny",
    }

    # Allowed image attachment
    img_dec = evaluate_message_policy(
        policy=policy,
        content="",
        attachments=[{"filename": "screenshot.png", "content_type": "image/png"}],
    )
    assert img_dec["allowed"] is True

    # Blocked video attachment
    vid_dec = evaluate_message_policy(
        policy=policy,
        content="",
        attachments=[{"filename": "clip.mp4", "content_type": "video/mp4"}],
    )
    assert vid_dec["allowed"] is False
    assert vid_dec["matched_rule"] == "allow_videos"


# ─── Part 5: Server Config & Mod Log Settings ────────────────────────────────

@pytest.mark.asyncio
async def test_mod_log_settings_persistence(db_session):
    """Verify Discord log channel ID and event list persistence in ServerConfig."""
    events = ["policy_violation", "blocked_link", "warning", "timeout", "ban"]
    channel_id = 987654321012345678

    await ServerConfigRepo.update(
        session=db_session,
        mod_log_channel_id=channel_id,
        mod_log_events=events,
    )
    await db_session.commit()

    config = await ServerConfigRepo.get_or_create(db_session)
    assert config.mod_log_channel_id == channel_id
    decoded_events = deserialize_json_field(config.mod_log_events)
    assert decoded_events == events
