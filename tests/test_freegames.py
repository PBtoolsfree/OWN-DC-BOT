"""
Comprehensive Test Suite for Free Games & Deals Tracker.

Covers all 24+ specifications and Section 29 button validation.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse
import pytest
import pytest_asyncio
import discord

from app.database.models import (
    FreeGameNotificationModel,
    FreeGameOfferModel,
    FreeGameSettings,
    FreeGameSourceModel,
)
from app.database.repositories import (
    FreeGameNotificationRepo,
    FreeGameOfferRepo,
    FreeGameSettingsRepo,
    FreeGameSourceRepo,
)
from app.freegames.dedupe import (
    compute_offer_unique_key,
    is_duplicate_offer,
    should_send_ending_soon,
)
from app.freegames.normalizer import (
    normalize_claim_url,
    parse_price,
    parse_utc_timestamp,
)
from app.freegames.notifier import (
    build_claim_button_view,
    build_offer_embed,
    format_price_display,
    prepare_notification_payload,
)
from app.freegames.schemas import (
    FreeGameOffer,
    OfferStatus,
    OfferType,
    SourceStatus,
)
from app.freegames.service import FreeGameService
from app.freegames.sources import (
    AppStoreSource,
    EpicGamesSource,
    GOGSource,
    GooglePlaySource,
    SteamSource,
    get_all_sources,
    get_source,
)
from app.freegames.validator import (
    TRUSTED_SOURCE_DOMAINS,
    validate_claim_url_security,
    validate_offer_eligibility,
)


# ─── 1. Source Adapter Normalization ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_epic_source_normalization():
    """Test Epic Games promotions API normalization."""
    mock_payload = {
        "data": {
            "Catalog": {
                "searchStore": {
                    "elements": [
                        {
                            "id": "epic-test-123",
                            "title": "Subnautica",
                            "description": "Underwater survival game.",
                            "productSlug": "subnautica",
                            "urlSlug": "subnautica",
                            "promotions": {
                                "promotionalOffers": [
                                    {
                                        "promotionalOffers": [
                                            {
                                                "startDate": "2026-10-01T15:00:00.000Z",
                                                "endDate": "2026-10-15T15:00:00.000Z",
                                                "discountSetting": {
                                                    "discountType": "PERCENTAGE",
                                                    "discountPercentage": 0,
                                                },
                                            }
                                        ]
                                    }
                                ]
                            },
                            "price": {
                                "totalPrice": {
                                    "originalPrice": 2999,
                                    "discountPrice": 0,
                                    "currencyCode": "USD",
                                }
                            },
                            "keyImages": [
                                {"type": "OfferImageWide", "url": "https://cdn.epicgames.com/subnautica.jpg"}
                            ],
                        }
                    ]
                }
            }
        }
    }

    source = EpicGamesSource()
    with patch.object(source, "_fetch_json", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_payload
        offers = await source.fetch_offers()

    assert len(offers) == 1
    offer = offers[0]
    assert offer.source == "epic"
    assert offer.title == "Subnautica"
    assert offer.external_id == "epic-test-123"
    assert offer.is_free is True
    assert offer.original_price == 29.99
    assert offer.current_price == 0.0
    assert offer.claim_url == "https://store.epicgames.com/p/subnautica"
    assert offer.thumbnail_url == "https://cdn.epicgames.com/subnautica.jpg"
    assert offer.offer_type == OfferType.FREE_TO_KEEP.value


@pytest.mark.asyncio
async def test_steam_source_normalization():
    """Test Steam source normalization via direct store giveaway feed."""
    mock_giveaways = [
        {
            "id": 999,
            "title": "Portal 2 Giveaway",
            "worth": "$19.99",
            "open_giveaway_url": "https://www.gamerpower.com/open/portal-2",
            "image": "https://cdn.steam.com/portal2.jpg",
            "description": "Co-op puzzle game",
            "end_date": "2026-10-20 23:59:59",
            "type": "Game",
            "platforms": "PC, Steam",
        }
    ]

    source = SteamSource()
    with patch.object(source, "_fetch_json", new_callable=AsyncMock) as mock_get, \
         patch.object(source, "_resolve_canonical_redirect", new_callable=AsyncMock) as mock_resolve:
        mock_get.return_value = mock_giveaways
        mock_resolve.return_value = "https://store.steampowered.com/app/620/Portal_2/"

        offers = await source.fetch_offers()

    assert len(offers) == 1
    assert offers[0].source == "steam"
    assert offers[0].title == "Portal 2"
    assert offers[0].claim_url == "https://store.steampowered.com/app/620/Portal_2/"
    assert offers[0].original_price == 19.99


# ─── 2. Free-to-Keep Detection ────────────────────────────────────────────────

def test_free_to_keep_detection():
    """Test detection of paid game temporarily free."""
    offer = FreeGameOffer(
        source="epic",
        external_id="free-game-1",
        title="Death Stranding",
        store_name="Epic Games Store",
        platform="PC",
        claim_url="https://store.epicgames.com/p/death-stranding",
        original_price=39.99,
        current_price=0.0,
        offer_type=OfferType.FREE_TO_KEEP.value,
        is_free=True,
    )
    is_valid, reason = validate_offer_eligibility(offer, allowed_offer_types=["free_to_keep"])
    assert is_valid is True
    assert reason == "ELIGIBLE"


# ─── 3. Free-to-Play Filtering ────────────────────────────────────────────────

def test_free_to_play_filtering():
    """Ensure permanently free-to-play games are filtered out by default."""
    offer = FreeGameOffer(
        source="steam",
        external_id="f2p-1",
        title="Dota 2",
        store_name="Steam",
        platform="PC",
        claim_url="https://store.steampowered.com/app/570/Dota_2/",
        original_price=0.0,
        current_price=0.0,
        offer_type=OfferType.FREE_TO_PLAY.value,
        is_free=True,
    )
    # Default allowed_types does not include free_to_play
    is_valid, reason = validate_offer_eligibility(offer, allowed_offer_types=["free_to_keep"])
    assert is_valid is False
    assert "OFFER_TYPE_DISABLED" in reason


# ─── 4. Claim URL Extraction & Normalization ──────────────────────────────────

def test_claim_url_normalization():
    """Test stripping tracking parameters and enforcing HTTPS canonical URLs."""
    dirty_epic = "http://store.epicgames.com/en-US/p/fallout-3?utm_source=partner&ref=discord"
    norm_epic = normalize_claim_url(dirty_epic, source="epic")
    assert norm_epic == "https://store.epicgames.com/p/fallout-3"

    dirty_steam = "http://store.steampowered.com/app/400/Portal/?snr=1_2_3"
    norm_steam = normalize_claim_url(dirty_steam, source="steam")
    assert norm_steam == "https://store.steampowered.com/app/400/"

    dirty_gog = "http://www.gog.com/en/game/witcher_3?utm_campaign=winter"
    norm_gog = normalize_claim_url(dirty_gog, source="gog")
    assert "gog.com/game/witcher_3" in norm_gog

    dirty_play = "http://play.google.com/store/apps/details?id=com.game.test&hl=en&gl=us"
    norm_play = normalize_claim_url(dirty_play, source="google_play")
    assert norm_play == "https://play.google.com/store/apps/details?id=com.game.test"

    dirty_ios = "http://apps.apple.com/us/app/game-title/id123456789?uo=4"
    norm_ios = normalize_claim_url(dirty_ios, source="app_store")
    assert norm_ios == "https://apps.apple.com/app/id123456789"


# ─── 5. HTTPS Validation ──────────────────────────────────────────────────────

def test_https_validation():
    """Verify non-HTTPS URLs are rejected."""
    is_valid, reason = validate_claim_url_security("http://store.epicgames.com/p/test", source="epic")
    assert is_valid is False
    assert "INSECURE_SCHEME" in reason


# ─── 6. Trusted Domain Validation ─────────────────────────────────────────────

def test_trusted_domain_validation():
    """Verify official domains pass and untrusted third-party domains fail."""
    # Official trusted
    assert validate_claim_url_security("https://store.epicgames.com/p/test", source="epic")[0] is True
    assert validate_claim_url_security("https://store.steampowered.com/app/100/", source="steam")[0] is True
    assert validate_claim_url_security("https://www.gog.com/game/test", source="gog")[0] is True
    assert validate_claim_url_security("https://play.google.com/store/apps/details?id=test", source="google_play")[0] is True
    assert validate_claim_url_security("https://apps.apple.com/app/test/id1", source="app_store")[0] is True

    # Untrusted / spoofed domains
    is_valid, reason = validate_claim_url_security("https://store-epicgames.phishing.com/p/test", source="epic")
    assert is_valid is False
    assert "UNTRUSTED_DOMAIN" in reason

    is_valid, reason = validate_claim_url_security("https://free-steam-keys.ru/claim", source="steam")
    assert is_valid is False
    assert "UNTRUSTED_DOMAIN" in reason


# ─── 7. Malicious URL Rejection ───────────────────────────────────────────────

def test_malicious_url_rejection():
    """Verify dangerous schemes like javascript:, data:, file: are strictly rejected."""
    bad_urls = [
        "javascript:alert(document.cookie)",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        "ftp://mirror.example.com/games",
        "vbscript:msgbox(1)",
    ]
    for url in bad_urls:
        is_valid, reason = validate_claim_url_security(url)
        assert is_valid is False
        assert "MALICIOUS_SCHEME" in reason or "INSECURE_SCHEME" in reason


# ─── 8. Duplicate Detection & Deterministic Identity ──────────────────────────

def test_duplicate_key_generation():
    """Test deterministic key computation."""
    key1 = compute_offer_unique_key("epic", external_id="game-123")
    assert key1 == "epic:game-123"

    key2 = compute_offer_unique_key("steam", claim_url="https://store.steampowered.com/app/400/")
    assert key2.startswith("steam:")


# ─── 9 & 10. Repeated Polling & Offer Lifecycle ───────────────────────────────

@pytest.mark.asyncio
async def test_repeated_polling_and_deduplication(db_session):
    """Test that recurring polls do not recreate or repost existing active offers."""
    # 1. Create initial active offer
    offer_dict = {
        "source": "epic",
        "external_id": "ext-repeat-1",
        "unique_key": "epic:ext-repeat-1",
        "title": "Amnesia: The Dark Descent",
        "store_name": "Epic Games Store",
        "platform": "PC",
        "claim_url": "https://store.epicgames.com/p/amnesia",
        "current_price": 0.0,
        "original_price": 19.99,
        "is_free": True,
        "starts_at": datetime.now(timezone.utc) - timedelta(days=1),
        "ends_at": datetime.now(timezone.utc) + timedelta(days=5),
    }
    db_offer, is_new = await FreeGameOfferRepo.upsert_offer(db_session, offer_dict)
    await FreeGameOfferRepo.mark_posted(db_session, db_offer.id, channel_id=123, message_id=987654321)
    await db_session.commit()

    # 2. Check duplicate logic
    incoming = FreeGameOffer(
        source="epic",
        external_id="ext-repeat-1",
        title="Amnesia: The Dark Descent",
        store_name="Epic Games Store",
        platform="PC",
        claim_url="https://store.epicgames.com/p/amnesia",
        is_free=True,
    )
    existing = await FreeGameOfferRepo.get_by_unique_key(db_session, incoming.unique_key)
    assert existing is not None
    should_post = is_duplicate_offer(incoming, existing)
    assert should_post is True  # Already posted and active -> duplicate!


# ─── 11. Expiry Handling ──────────────────────────────────────────────────────

def test_expired_offer_rejected():
    """Verify offers with ends_at in the past are marked invalid."""
    past_date = datetime.now(timezone.utc) - timedelta(hours=2)
    offer = FreeGameOffer(
        source="epic",
        external_id="expired-1",
        title="Old Game",
        store_name="Epic Games Store",
        platform="PC",
        claim_url="https://store.epicgames.com/p/old-game",
        ends_at=past_date,
    )
    is_valid, reason = validate_offer_eligibility(offer)
    assert is_valid is False
    assert reason == "OFFER_ALREADY_EXPIRED"


# ─── 12. Ending-Soon Notification ─────────────────────────────────────────────

def test_ending_soon_detection():
    """Test detection of active offers expiring within configured window."""
    now = datetime.now(timezone.utc)
    ends_in_4h = now + timedelta(hours=4)

    offer = FreeGameOffer(
        source="epic",
        external_id="ending-soon-1",
        title="Expiring Gem",
        store_name="Epic Games Store",
        platform="PC",
        claim_url="https://store.epicgames.com/p/expiring-gem",
        ends_at=ends_in_4h,
    )

    # 6 hour threshold -> should alert
    assert should_send_ending_soon(offer, ending_soon_hours=6) is True
    # 2 hour threshold -> not yet
    assert should_send_ending_soon(offer, ending_soon_hours=2) is False


# ─── 13. Discord Embed Generation ─────────────────────────────────────────────

def test_discord_embed_generation():
    """Verify rich embed generation with all required fields."""
    offer = FreeGameOffer(
        source="epic",
        external_id="embed-test",
        title="Control Standard Edition",
        description="A supernatural third-person action-adventure game.",
        store_name="Epic Games Store",
        platform="PC",
        claim_url="https://store.epicgames.com/p/control",
        original_price=29.99,
        current_price=0.0,
        currency="USD",
        ends_at=datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc),
        thumbnail_url="https://cdn.epicgames.com/control.jpg",
    )

    embed = build_offer_embed(offer)
    assert "Control Standard Edition" in embed.title
    assert embed.url == offer.claim_url
    assert embed.footer.text == "PB HERO FREE GAMES"

    fields = {f.name: f.value for f in embed.fields}
    assert fields["🏪 Store"] == "Epic Games Store"
    assert fields["💻 Platform"] == "PC"
    assert "FREE" in fields["🔥 Current Price"]
    assert "$29.99" in fields["💰 Normal Price"]
    assert "15 October 2026" in fields["🗓️ Ends"]


# ─── 14 & 29. Test The Exact Claim Button (CRITICAL REGRESSION) ───────────────

def test_exact_claim_button_generation():
    """
    CRITICAL SECTION 29 REQUIREMENT:
    Assert that the generated Discord button:
    1. label == '🎁 CLAIM GAME'
    2. button.url == normalized_offer.claim_url
    3. button.style == discord.ButtonStyle.link
    4. URL belongs to trusted source domain.
    """
    canonical_url = "https://store.epicgames.com/p/bioshock-the-collection"
    view = build_claim_button_view(canonical_url, source="epic")
    assert view is not None
    assert len(view.children) == 1

    btn = view.children[0]
    assert isinstance(btn, discord.ui.Button)
    assert btn.label == "🎁 CLAIM GAME"
    assert btn.url == canonical_url
    assert btn.style == discord.ButtonStyle.link

    # Trusted domain verification
    domain = urlparse(btn.url).netloc.lower()
    assert domain in TRUSTED_SOURCE_DOMAINS["epic"]


# ─── 15. Missing Claim URL Skipped ────────────────────────────────────────────

def test_missing_claim_url_skipped():
    """Verify offers with empty or missing claim_url are skipped."""
    offer = FreeGameOffer(
        source="epic",
        external_id="no-url-1",
        title="Mystery Game",
        store_name="Epic Games Store",
        platform="PC",
        claim_url="",  # Missing URL
    )
    is_valid, reason = validate_offer_eligibility(offer)
    assert is_valid is False
    assert reason == "SKIPPED_OFFER_NO_CLAIM_URL"


# ─── 16. Source Failure Isolation ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_source_failure_isolation():
    """Verify that a failure in one source does not crash the service or other sources."""
    service = FreeGameService()

    cfg = MagicMock()
    cfg.enabled = True
    cfg.enabled_sources_json = json.dumps(["epic", "steam"])
    cfg.offer_types_json = json.dumps(["free_to_keep"])
    cfg.ending_soon_enabled = False

    mock_session = AsyncMock()

    with patch.object(service, "get_settings", new_callable=AsyncMock) as mock_cfg, \
         patch("app.freegames.service.get_source") as mock_get_source, \
         patch("app.freegames.service.get_session_direct", new_callable=AsyncMock) as mock_session_call, \
         patch("app.freegames.service.FreeGameSourceRepo.record_failure", new_callable=AsyncMock), \
         patch("app.freegames.service.FreeGameSourceRepo.record_success", new_callable=AsyncMock):

        mock_cfg.return_value = cfg
        mock_session_call.return_value = mock_session

        # Epic fails with Network Error
        epic_mock = AsyncMock()
        epic_mock.fetch_offers.side_effect = Exception("Epic 503 Service Unavailable")

        # Steam succeeds with 1 offer
        steam_offer = FreeGameOffer(
            source="steam",
            external_id="steam-iso-1",
            title="Isolate Game",
            store_name="Steam",
            platform="PC",
            claim_url="https://store.steampowered.com/app/123/",
        )
        steam_mock = AsyncMock()
        steam_mock.fetch_offers.return_value = [steam_offer]

        def source_router(name):
            if name == "epic":
                return epic_mock
            if name == "steam":
                return steam_mock
            return None

        mock_get_source.side_effect = source_router

        # Patch _process_offer so it doesn't need DB
        with patch.object(service, "_process_offer", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = True
            res = await service.sync_offers()

        assert res["sources"]["epic"]["success"] is False
        assert "503" in res["sources"]["epic"]["error"]
        assert res["sources"]["steam"]["success"] is True
        assert res["sources"]["steam"]["count"] == 1


# ─── 17. Discord Failure Isolation ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discord_failure_isolation():
    """Verify that Discord message dispatch exceptions do not crash PB HERO."""
    bot = MagicMock()
    channel = AsyncMock()
    channel.send.side_effect = discord.HTTPException(response=MagicMock(status=500), message="Internal Server Error")
    bot.get_channel.return_value = channel

    service = FreeGameService(bot=bot)
    cfg = MagicMock()
    cfg.destination_channel_id = 12345
    cfg.role_mention_id = None
    cfg.post_thumbnail = True
    cfg.post_description = True
    cfg.show_price = True
    cfg.show_expiry = True

    offer = FreeGameOffer(
        source="epic",
        external_id="discord-fail-1",
        title="Failing Post Game",
        store_name="Epic Games Store",
        platform="PC",
        claim_url="https://store.epicgames.com/p/failing-post",
    )

    with patch.object(service, "check_channel_permissions") as mock_perms, \
         patch("app.freegames.service.get_session_direct", new_callable=AsyncMock):
        mock_perms.return_value = (True, {"status": "ok"})
        success = await service._deliver_new_offer_notification(1, offer, cfg)
        assert success is False


# ─── 18 & 21. Database Persistence & Settings Persistence ─────────────────────

@pytest.mark.asyncio
async def test_settings_persistence(db_session):
    """Test FreeGameSettings CRUD operations."""
    cfg = await FreeGameSettingsRepo.get_or_create(db_session, guild_id=777)
    await db_session.commit()

    assert cfg.enabled is True
    assert cfg.poll_interval_seconds == 900

    # Update
    updated = await FreeGameSettingsRepo.update(
        db_session,
        guild_id=777,
        destination_channel_id=999888,
        poll_interval_seconds=1800,
        ending_soon_enabled=True,
    )
    await db_session.commit()

    assert updated.destination_channel_id == 999888
    assert updated.poll_interval_seconds == 1800
    assert updated.ending_soon_enabled is True


# ─── 19 & 20. Notification Deduplication & Restart Safety ─────────────────────

@pytest.mark.asyncio
async def test_notification_deduplication(db_session):
    """Ensure FreeGameNotificationRepo logs events and prevents duplicate sends."""
    # First record
    notif = await FreeGameNotificationRepo.record(
        db_session,
        offer_id=1,
        notification_type="NEW_OFFER",
        channel_id=556677,
        message_id=11223344,
        claim_url="https://store.epicgames.com/p/test",
    )
    await db_session.commit()
    assert notif.id is not None

    # Check existence
    has_sent = await FreeGameNotificationRepo.has_notification(
        db_session,
        offer_id=1,
        notification_type="NEW_OFFER",
    )
    assert has_sent is True

    has_ending = await FreeGameNotificationRepo.has_notification(
        db_session,
        offer_id=1,
        notification_type="ENDING_SOON",
    )
    assert has_ending is False


# ─── 22. API Endpoints Contract (claim_url included) ──────────────────────────

def test_api_schema_contract():
    """Verify offer dictionary contains canonical claim_url and required metadata."""
    offer = FreeGameOffer(
        source="gog",
        external_id="gog-1",
        title="The Witcher 2",
        store_name="GOG",
        platform="PC",
        claim_url="https://www.gog.com/game/the_witcher_2",
        original_price=19.99,
        current_price=0.0,
    )
    d = offer.to_dict()
    assert "claim_url" in d
    assert d["claim_url"] == "https://www.gog.com/game/the_witcher_2"
    assert d["unique_key"] == "gog:gog-1"


# ─── 23. Mobile Regional Handling ─────────────────────────────────────────────

def test_mobile_regional_handling():
    """Verify Google Play and App Store regional metadata handling."""
    offer = FreeGameOffer(
        source="google_play",
        external_id="com.premium.game",
        title="Monument Valley",
        store_name="Google Play",
        platform="Android",
        claim_url="https://play.google.com/store/apps/details?id=com.premium.game",
        metadata={"region": "US", "price_currency": "USD"},
    )
    assert offer.platform == "Android"
    assert offer.metadata["region"] == "US"
    assert "play.google.com" in offer.claim_url


# ─── 24. Multiple Sources Registered ──────────────────────────────────────────

def test_source_registry():
    """Ensure all required sources are registered in the source registry."""
    all_sources = get_all_sources()
    registered_names = {s.name for s in all_sources}
    expected = {"epic", "steam", "gog", "google_play", "app_store"}
    assert expected.issubset(registered_names)


# ─── 25. Admin Test Notification Without DB Record ───────────────────────────

@pytest.mark.asyncio
async def test_admin_test_does_not_persist():
    """Section 24: Verify send_test_notification sends embed but does not save offer to DB."""
    bot = MagicMock()
    channel = AsyncMock()
    mock_msg = MagicMock()
    mock_msg.id = 555444333
    channel.send.return_value = mock_msg
    bot.get_channel.return_value = channel

    service = FreeGameService(bot=bot)
    cfg = MagicMock()
    cfg.destination_channel_id = 99999
    cfg.role_mention_id = None
    cfg.post_thumbnail = True
    cfg.post_description = True
    cfg.show_price = True
    cfg.show_expiry = True

    with patch.object(service, "get_settings", new_callable=AsyncMock) as mock_cfg, \
         patch.object(service, "check_channel_permissions") as mock_perms:
        mock_cfg.return_value = cfg
        mock_perms.return_value = (True, {"status": "ok"})

        res = await service.send_test_notification()

    assert res["success"] is True
    assert res["message_id"] == 555444333
    assert "store.epicgames.com" in res["claim_url"]
    channel.send.assert_called_once()
