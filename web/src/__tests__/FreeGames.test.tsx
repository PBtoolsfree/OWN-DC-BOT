import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import FreeGames from '../pages/FreeGames';
import { freegamesApi } from '../api/freegames';
import { channelsApi } from '../api/channels';

vi.mock('../api/freegames', () => ({
  freegamesApi: {
    getStats: vi.fn(),
    getHealth: vi.fn(),
    getSources: vi.fn(),
    getOffers: vi.fn(),
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    syncOffers: vi.fn(),
    testNotification: vi.fn(),
  },
}));

vi.mock('../api/channels', () => ({
  channelsApi: {
    getChannels: vi.fn(),
    getRoles: vi.fn(),
  },
}));

const mockStats = {
  total_offers: 12,
  active_offers: 5,
  posted_today: 3,
  ending_soon: 2,
  total_notifications: 8,
};

const mockHealth = {
  healthy: true,
  scheduler_running: true,
  channel_permissions: {
    status: 'ok',
    can_view: true,
    can_send: true,
    can_embed: true,
  },
  sources: [
    {
      source_name: 'epic',
      category: 'PC',
      status: 'HEALTHY',
      offer_count: 2,
      latency_ms: 120,
      last_checked_at: '2026-10-06T12:00:00Z',
    },
    {
      source_name: 'steam',
      category: 'PC',
      status: 'HEALTHY',
      offer_count: 3,
      latency_ms: 140,
      last_checked_at: '2026-10-06T12:00:00Z',
    },
  ],
};

const mockOffers = [
  {
    id: 1,
    source: 'epic',
    external_id: 'epic-free-1',
    unique_key: 'epic:epic-free-1',
    title: 'Ghostrunner 2',
    description: 'Cyberpunk slasher game free this week',
    store_name: 'Epic Games',
    platform: 'PC',
    offer_type: 'free_to_keep',
    original_price: 39.99,
    current_price: 0.0,
    currency: 'USD',
    discount_percent: 100,
    claim_url: 'https://store.epicgames.com/p/ghostrunner-2',
    canonical_claim_url: 'https://store.epicgames.com/en-US/p/ghostrunner-2',
    claim_url_status: 'VALID',
    validated_at: '2026-10-06T10:00:00Z',
    source_url: 'https://store.epicgames.com',
    thumbnail_url: 'https://example.com/ghostrunner.jpg',
    starts_at: '2026-10-01T15:00:00Z',
    ends_at: '2026-10-08T15:00:00Z',
    is_free: true,
    status: 'ACTIVE',
    first_seen_at: '2026-10-01T15:00:00Z',
    last_seen_at: '2026-10-06T12:00:00Z',
    last_posted_at: '2026-10-06T09:00:00Z',
    posted_message_id: 123456789,
    posted_channel_id: 987654321,
  },
  {
    id: 2,
    source: 'steam',
    external_id: 'steam-sub-2',
    unique_key: 'steam:steam-sub-2',
    title: 'Company of Heroes 2',
    description: 'WWII Strategy game',
    store_name: 'Steam',
    platform: 'PC',
    offer_type: 'free_to_keep',
    original_price: 19.99,
    current_price: 0.0,
    currency: 'USD',
    discount_percent: 100,
    claim_url: 'https://store.steampowered.com/app/231430',
    canonical_claim_url: 'https://store.steampowered.com/app/231430/Company_of_Heroes_2/',
    claim_url_status: 'VALID',
    validated_at: '2026-10-06T10:00:00Z',
    source_url: 'https://store.steampowered.com',
    thumbnail_url: 'https://example.com/coh2.jpg',
    starts_at: '2026-10-02T15:00:00Z',
    ends_at: '2026-10-09T15:00:00Z',
    is_free: true,
    status: 'ENDING_SOON',
    first_seen_at: '2026-10-02T15:00:00Z',
    last_seen_at: '2026-10-06T12:00:00Z',
    last_posted_at: '2026-10-06T09:00:00Z',
    posted_message_id: 123456789,
    posted_channel_id: 987654321,
  },
];

const mockSettings = {
  id: 1,
  guild_id: '123456',
  enabled: true,
  destination_channel_id: '987654321',
  role_mention_id: '11223344',
  poll_interval_seconds: 900,
  enabled_sources_json: '["epic", "steam", "gog", "google_play", "app_store"]',
  offer_types_json: '["free_to_keep"]',
  ending_soon_enabled: true,
  ending_soon_hours: 24,
  post_thumbnail: true,
  post_description: true,
  show_price: true,
  show_expiry: true,
};

const mockChannels = [
  { id: '987654321', name: 'free-games', type: 'text', category: 'ANNOUNCEMENTS', position: 1 },
  { id: '111222333', name: 'general', type: 'text', category: 'GENERAL', position: 2 },
];

const mockRoles = [
  { id: '11223344', name: 'FreeGames-Ping', color: '#5865F2', position: 1 },
];

describe('FreeGames Page Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(freegamesApi.getStats).mockResolvedValue(mockStats);
    vi.mocked(freegamesApi.getHealth).mockResolvedValue(mockHealth);
    vi.mocked(freegamesApi.getSources).mockResolvedValue({ sources: mockHealth.sources });
    vi.mocked(freegamesApi.getOffers).mockResolvedValue({ offers: mockOffers, count: 2 });
    vi.mocked(freegamesApi.getSettings).mockResolvedValue(mockSettings);
    vi.mocked(channelsApi.getChannels).mockResolvedValue(mockChannels as any);
    vi.mocked(channelsApi.getRoles).mockResolvedValue(mockRoles as any);
  });

  it('renders overview stats cards with all required metrics', async () => {
    render(
      <BrowserRouter>
        <FreeGames />
      </BrowserRouter>
    );

    // Verify Title
    expect(await screen.findByText('Free Games & Deals Tracker')).toBeInTheDocument();

    // Verify 5 Overview metric titles
    expect(screen.getByText('Total Offers')).toBeInTheDocument();
    expect(screen.getByText('Active Offers')).toBeInTheDocument();
    expect(screen.getByText('Posted Today')).toBeInTheDocument();
    expect(screen.getByText('Ending Soon')).toBeInTheDocument();
    expect(screen.getByText('Source Health')).toBeInTheDocument();

    // Verify metric values
    expect(screen.getByText('12')).toBeInTheDocument(); // Total offers
    expect(screen.getByText('5')).toBeInTheDocument(); // Active offers
    expect(screen.getByText('3')).toBeInTheDocument(); // Posted today
    expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(1); // Ending soon
  });

  it('navigates to Offers tab and renders canonical claim URL with 🎁 CLAIM GAME button', async () => {
    render(
      <BrowserRouter>
        <FreeGames />
      </BrowserRouter>
    );

    await screen.findByText('Free Games & Deals Tracker');

    // Switch to Offers tab using testid
    const offersTab = screen.getByTestId('tab-offers');
    fireEvent.click(offersTab);

    // Verify game items
    expect(await screen.findByText('Ghostrunner 2')).toBeInTheDocument();
    expect(screen.getByText('Company of Heroes 2')).toBeInTheDocument();

    // Verify 🎁 CLAIM GAME buttons exist
    const claimButtons = screen.getAllByText('🎁 CLAIM GAME');
    expect(claimButtons.length).toBeGreaterThanOrEqual(2);

    // Verify canonical claim link on the button anchor
    const claimAnchor = claimButtons[0].closest('a');
    expect(claimAnchor).toHaveAttribute(
      'href',
      'https://store.epicgames.com/en-US/p/ghostrunner-2'
    );
    expect(claimAnchor).toHaveAttribute('target', '_blank');
  });

  it('navigates to Sources tab and renders all 5 required stores', async () => {
    render(
      <BrowserRouter>
        <FreeGames />
      </BrowserRouter>
    );

    await screen.findByText('Free Games & Deals Tracker');

    // Switch to Sources tab
    const sourcesTab = screen.getByTestId('tab-sources');
    fireEvent.click(sourcesTab);

    // Verify all 5 stores
    expect(await screen.findByText('Epic Games Store')).toBeInTheDocument();
    expect(screen.getByText('Steam')).toBeInTheDocument();
    expect(screen.getByText('GOG')).toBeInTheDocument();
    expect(screen.getByText('Google Play')).toBeInTheDocument();
    expect(screen.getByText('Apple App Store')).toBeInTheDocument();
  });

  it('navigates to Settings tab and updates destination channel and save', async () => {
    vi.mocked(freegamesApi.updateSettings).mockResolvedValue({
      success: true,
      settings: mockSettings,
    });

    render(
      <BrowserRouter>
        <FreeGames />
      </BrowserRouter>
    );

    await screen.findByText('Free Games & Deals Tracker');

    // Switch to Settings tab
    const settingsTab = screen.getByTestId('tab-settings');
    fireEvent.click(settingsTab);

    expect(await screen.findByText('Destination Text Channel')).toBeInTheDocument();

    // Click Save Settings button
    const saveButton = screen.getByRole('button', { name: /Save Settings/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(freegamesApi.updateSettings).toHaveBeenCalled();
    });
  });

  it('executes Sync Now and Test Notification actions', async () => {
    vi.mocked(freegamesApi.syncOffers).mockResolvedValue({
      success: true,
      total_found: 10,
      new_offers: 2,
    });
    vi.mocked(freegamesApi.testNotification).mockResolvedValue({
      success: true,
      message: 'Test notification delivered',
    });

    render(
      <BrowserRouter>
        <FreeGames />
      </BrowserRouter>
    );

    await screen.findByText('Free Games & Deals Tracker');

    // Trigger Sync Now
    const syncButton = screen.getByRole('button', { name: /Sync Now/i });
    fireEvent.click(syncButton);

    await waitFor(() => {
      expect(freegamesApi.syncOffers).toHaveBeenCalled();
    });

    // Trigger Test Notification
    const testButton = screen.getByRole('button', { name: /Test Notification/i });
    fireEvent.click(testButton);

    await waitFor(() => {
      expect(freegamesApi.testNotification).toHaveBeenCalled();
    });
  });
});
