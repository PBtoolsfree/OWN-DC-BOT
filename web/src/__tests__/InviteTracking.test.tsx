import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import InviteTracking from '../pages/InviteTracking';
import { invitesApi } from '../api/invites';
import {
  DiscordTrackedInvite,
  InviteJoinRecord,
  InviteLeaderboardEntry,
  InviteOverviewStats,
  InviteTrackerHealth,
  UserInviteProfile,
} from '../types';

vi.mock('../api/invites', () => ({
  invitesApi: {
    getStats: vi.fn(),
    getLeaderboard: vi.fn(),
    getInvites: vi.fn(),
    getJoinsHistory: vi.fn(),
    getHealth: vi.fn(),
    getInviteDetails: vi.fn(),
    getUserProfile: vi.fn(),
    syncInvites: vi.fn(),
    revokeInvite: vi.fn(),
  },
}));

const mockStats: InviteOverviewStats = {
  timeframe: 'all',
  total_joins: 294,
  unknown_joins: 6,
  vanity_joins: 14,
  normal_joins: 274,
  unique_inviters: 12,
  top_inviter: {
    name: 'Rex12400',
    count: 32,
  },
  top_invite: {
    code: 'HERO2026',
    count: 45,
  },
  total_invites: 42,
  active_invites: 18,
  revoked_invites: 10,
  expired_invites: 14,
};

const mockLeaderboard: InviteLeaderboardEntry[] = [
  {
    rank: 1,
    user_id: '1001',
    username: 'Rex12400',
    joins: 32,
    percentage: 55.2,
    last_invite_join: '2026-10-05T10:30:00Z',
  },
  {
    rank: 2,
    user_id: '1002',
    username: 'PlayerX',
    joins: 27,
    percentage: 44.8,
    last_invite_join: '2026-10-05T09:15:00Z',
  },
];

const mockInvites: DiscordTrackedInvite[] = [
  {
    id: 1,
    guild_id: '1234567890',
    invite_code: 'HERO2026',
    inviter_id: '1001',
    inviter_name: 'Rex12400',
    channel_id: '2001',
    channel_name: 'welcome',
    uses: 45,
    max_uses: 0,
    max_age: 0,
    temporary: false,
    status: 'ACTIVE',
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-05T10:30:00Z',
    last_seen_at: '2026-10-05T10:30:00Z',
    revoked_at: null,
    is_vanity: false,
    is_permanent_config: false,
    invite_url: 'https://discord.gg/HERO2026',
    tracked_joins: 45,
  },
  {
    id: 2,
    guild_id: '1234567890',
    invite_code: 'OLD999',
    inviter_id: '1002',
    inviter_name: 'PlayerX',
    channel_id: '2001',
    channel_name: 'welcome',
    uses: 10,
    max_uses: 10,
    max_age: 3600,
    temporary: false,
    status: 'REVOKED',
    created_at: '2026-09-20T00:00:00Z',
    updated_at: '2026-09-21T00:00:00Z',
    last_seen_at: '2026-09-21T00:00:00Z',
    revoked_at: '2026-09-21T00:00:00Z',
    is_vanity: false,
    is_permanent_config: false,
    invite_url: 'https://discord.gg/OLD999',
    tracked_joins: 10,
  },
];

const mockHealth: InviteTrackerHealth = {
  status: 'HEALTHY',
  sync_status: 'SYNCED',
  sync_error: null,
  last_sync: '2026-10-05T10:00:00Z',
  last_attribution: '2026-10-05T10:30:00Z',
  tracked_invites_cached: 18,
  total_joins: 294,
  unknown_joins: 6,
  permissions: {
    has_manage_guild: true,
    can_read_invites: true,
    intents_ok: true,
    details: 'All permissions verified.',
  },
};

const mockJoins: InviteJoinRecord[] = [
  {
    id: 1,
    guild_id: '1234567890',
    member_id: '9901',
    member_name: 'NewFanA',
    invite_code: 'HERO2026',
    inviter_id: '1001',
    inviter_name: 'Rex12400',
    source_type: 'NORMAL_INVITE',
    channel_id: '2001',
    channel_name: 'welcome',
    joined_at: '2026-10-05T10:30:00Z',
    is_still_member: true,
    left_at: null,
  },
];

describe('InviteTracking Page Component', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(invitesApi.getStats).mockResolvedValue(mockStats);
    vi.mocked(invitesApi.getLeaderboard).mockResolvedValue({ leaderboard: mockLeaderboard });
    vi.mocked(invitesApi.getInvites).mockResolvedValue({
      items: mockInvites,
      total: 2,
      page: 1,
      page_size: 15,
      total_pages: 1,
    });
    vi.mocked(invitesApi.getHealth).mockResolvedValue(mockHealth);
    vi.mocked(invitesApi.getJoinsHistory).mockResolvedValue({
      items: mockJoins,
      total: 1,
      page: 1,
      page_size: 25,
      total_pages: 1,
    });
  });

  it('renders overview stats cards, leaderboard, and table', async () => {
    render(
      <BrowserRouter>
        <InviteTracking />
      </BrowserRouter>
    );

    // Header & Health
    await waitFor(() => {
      expect(screen.getByText(/discord invite tracking/i)).toBeInTheDocument();
      expect(screen.getByText('HEALTHY')).toBeInTheDocument();
    });

    // Stat cards
    expect(screen.getByText(/total joins/i)).toBeInTheDocument();
    expect(screen.getByText('294')).toBeInTheDocument();
    expect(screen.getByText(/invite links/i)).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText(/active invites/i)).toBeInTheDocument();
    expect(screen.getByText('18')).toBeInTheDocument();
    expect(screen.getAllByText(/top inviter/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Rex12400').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/unknown joins/i)).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument();

    // Leaderboard
    expect(screen.getByText(/invite leaderboard/i)).toBeInTheDocument();
    expect(screen.getAllByText('PlayerX').length).toBeGreaterThanOrEqual(1);

    // Table rows
    expect(screen.getByText('HERO2026')).toBeInTheDocument();
    expect(screen.getByText('OLD999')).toBeInTheDocument();
  });

  it('allows switching timeframe filters', async () => {
    render(
      <BrowserRouter>
        <InviteTracking />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('HERO2026')).toBeInTheDocument();
    });

    const sevenDaysBtn = screen.getByText('7 Days');
    fireEvent.click(sevenDaysBtn);

    await waitFor(() => {
      expect(invitesApi.getStats).toHaveBeenCalledWith('7d');
    });
  });

  it('opens invite details modal when clicking Details', async () => {
    vi.mocked(invitesApi.getInviteDetails).mockResolvedValue({
      invite: mockInvites[0],
      joins: mockJoins,
      total_joins: 1,
    });

    render(
      <BrowserRouter>
        <InviteTracking />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('HERO2026')).toBeInTheDocument();
    });

    const detailsBtns = screen.getAllByRole('button', { name: /details/i });
    expect(detailsBtns.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(detailsBtns[0]);

    await waitFor(() => {
      expect(invitesApi.getInviteDetails).toHaveBeenCalledWith('HERO2026');
      expect(screen.getByText(/members joined through this invite/i)).toBeInTheDocument();
      expect(screen.getByText('NewFanA')).toBeInTheDocument();
    });
  });

  it('opens user profile modal when clicking on an inviter', async () => {
    const mockProfile: UserInviteProfile = {
      user_id: '1001',
      username: 'Rex12400',
      total_joins: 32,
      this_month_joins: 12,
      this_week_joins: 4,
      current_members_referred: 30,
      former_members_referred: 2,
      last_invite_join: '2026-10-05T10:30:00Z',
      invites: [
        {
          invite_code: 'HERO2026',
          channel_name: 'welcome',
          uses: 45,
          status: 'ACTIVE',
          created_at: '2026-10-01T00:00:00Z',
        },
      ],
    };
    vi.mocked(invitesApi.getUserProfile).mockResolvedValue(mockProfile);

    render(
      <BrowserRouter>
        <InviteTracking />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Rex12400/i })).toBeInTheDocument();
    });

    const userBtn = screen.getByRole('button', { name: /Rex12400/i });
    fireEvent.click(userBtn);

    await waitFor(() => {
      expect(invitesApi.getUserProfile).toHaveBeenCalledWith('1001');
      expect(screen.getByText(/member invite profile/i)).toBeInTheDocument();
      expect(screen.getByText(/current members in server/i)).toBeInTheDocument();
      expect(screen.getByText(/former members/i)).toBeInTheDocument();
    });
  });

  it('switches between tabs: Invites, Joins Log, and Diagnostics', async () => {
    render(
      <BrowserRouter>
        <InviteTracking />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('HERO2026')).toBeInTheDocument();
    });

    // Switch to Joins Log tab
    const joinsTab = screen.getByRole('button', { name: /join attribution history/i });
    fireEvent.click(joinsTab);

    await waitFor(() => {
      expect(screen.getByText('Attributed Inviter')).toBeInTheDocument();
      expect(screen.getByText('NewFanA')).toBeInTheDocument();
    });

    // Switch to Diagnostics tab
    const diagTab = screen.getByRole('button', { name: /tracker health & permissions/i });
    fireEvent.click(diagTab);

    await waitFor(() => {
      expect(screen.getByText(/invite tracking diagnostics & gateway state/i)).toBeInTheDocument();
      expect(screen.getByText('Manage Server Permission')).toBeInTheDocument();
      expect(screen.getByText('Cached Active Invites (RAM)')).toBeInTheDocument();
    });
  });
});
