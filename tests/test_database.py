"""
Database tests verifying SQLite models, repositories, and relationships.
"""

import pytest
from app.dashboard.auth import hash_password, verify_password
from app.database.models import (
    AdminUser,
    ChannelPolicy,
    ModerationAction,
    ModerationCase,
    PolicyValue,
    YouTubeChannel,
    YouTubeDestination,
)
from app.database.repositories import (
    AdminUserRepo,
    ChannelPolicyRepo,
    ModerationCaseRepo,
    YouTubeChannelRepo,
    YouTubeDestinationRepo,
)


@pytest.mark.asyncio
async def test_admin_user_repo(db_session):
    """Test AdminUser creation, password hashing, and lookup."""
    raw_pass = "SecureAdminPassword!123"
    hashed = hash_password(raw_pass)

    user = await AdminUserRepo.create(db_session, "superadmin", hashed)
    await db_session.commit()

    assert user.id is not None
    assert user.username == "superadmin"
    assert verify_password(user.password_hash, raw_pass) is True

    fetched = await AdminUserRepo.get_by_username(db_session, "superadmin")
    assert fetched is not None
    assert fetched.username == "superadmin"

    count = await AdminUserRepo.count(db_session)
    assert count == 1


@pytest.mark.asyncio
async def test_channel_policy_repo(db_session):
    """Test channel policy creation, updating, and fetching."""
    channel_id = 987654321012345678

    policy = await ChannelPolicyRepo.upsert(
        db_session,
        channel_id=channel_id,
        channel_name="general-chat",
        allow_links=PolicyValue.INHERIT,
    )
    await db_session.commit()

    assert policy.discord_channel_id == channel_id
    assert policy.allow_links == PolicyValue.INHERIT

    # Update policy
    await ChannelPolicyRepo.upsert(
        db_session,
        channel_id=channel_id,
        allow_links=PolicyValue.DENY,
        allow_everyone=PolicyValue.DENY,
    )
    await db_session.commit()

    updated = await ChannelPolicyRepo.get_for_channel(db_session, channel_id)
    assert updated.allow_links == PolicyValue.DENY
    assert updated.allow_everyone == PolicyValue.DENY


@pytest.mark.asyncio
async def test_moderation_cases(db_session):
    """Test logging and fetching moderation cases."""
    case = await ModerationCaseRepo.create(
        db_session,
        target_user_id=111111111111111111,
        target_username="badactor",
        moderator_user_id=222222222222222222,
        moderator_username="mod_hero",
        action=ModerationAction.TIMEOUT,
        reason="Posting prohibited invite links",
        duration=600,
        channel_id=333333333333333333,
    )
    await db_session.commit()

    assert case.id is not None
    assert case.case_number == 1
    assert case.action == ModerationAction.TIMEOUT

    recent = await ModerationCaseRepo.get_recent(db_session, limit=10)
    assert len(recent) == 1
    assert recent[0].target_username == "badactor"


@pytest.mark.asyncio
async def test_youtube_channels_and_destinations(db_session):
    """Test YouTube channel monitoring and destination association."""
    yt_ch = await YouTubeChannelRepo.create(
        db_session,
        youtube_channel_id="UC_x5XG1OV2P6uZZ5FSM9Ttw",
        channel_name="Google Developers",
        handle="@GoogleDevelopers",
    )
    await db_session.commit()

    assert yt_ch.id is not None
    assert yt_ch.youtube_channel_id == "UC_x5XG1OV2P6uZZ5FSM9Ttw"

    dest = await YouTubeDestinationRepo.create(
        db_session,
        youtube_channel_id="UC_x5XG1OV2P6uZZ5FSM9Ttw",
        discord_channel_id=555555555555555555,
        custom_template="Check out the new Google upload!",
    )
    await db_session.commit()

    assert dest.id is not None
    assert dest.discord_channel_id == 555555555555555555

    dests = await YouTubeDestinationRepo.get_for_channel(db_session, "UC_x5XG1OV2P6uZZ5FSM9Ttw")
    assert len(dests) == 1
    assert dests[0].custom_template == "Check out the new Google upload!"
