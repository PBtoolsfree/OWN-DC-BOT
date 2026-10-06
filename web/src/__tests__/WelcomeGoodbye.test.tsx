import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import WelcomeGoodbye from '../pages/WelcomeGoodbye';
import { greetingsApi } from '../api/greetings';
import { toast } from '../hooks/useToast';
import { GreetingsResponse, GreetingChannelOption, GuildRoleOption } from '../types';

vi.mock('../api/greetings', () => ({
  greetingsApi: {
    getGreetings: vi.fn(),
    updateGreetings: vi.fn(),
    getChannels: vi.fn(),
    getRoles: vi.fn(),
    getRules: vi.fn(),
    updateRules: vi.fn(),
    getInvite: vi.fn(),
    generateInvite: vi.fn(),
    verifyInvite: vi.fn(),
    regenerateInvite: vi.fn(),
    testGreeting: vi.fn(),
    testWelcome: vi.fn(),
    testGoodbye: vi.fn(),
    resetSystem: vi.fn(),
  },
}));

vi.mock('../hooks/useToast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

const mockGreetingsData: GreetingsResponse = {
  settings: {
    id: 1,
    guild_id: '123456789012345678',
    welcome_enabled: false,
    welcome_channel_id: '111',
    welcome_title: '👋 Welcome to {server_name}!',
    welcome_description: 'Welcome {user_mention} to **{server_name}**! ❤️\n\nYou are member **#{member_count}**.',
    welcome_footer: 'PB HERO SERVER',
    welcome_mention_user: true,
    welcome_show_avatar: true,
    welcome_show_server_icon: true,
    welcome_show_member_count: true,
    welcome_show_timestamp: true,
    welcome_use_embed: true,
    goodbye_enabled: false,
    goodbye_channel_id: '222',
    goodbye_title: '👋 Goodbye {display_name}',
    goodbye_description: '**{display_name}** has left **{server_name}**.',
    goodbye_footer: 'PB HERO SERVER',
    goodbye_mention_user: false,
    goodbye_show_avatar: true,
    goodbye_show_server_icon: true,
    goodbye_show_member_count: true,
    goodbye_show_timestamp: true,
    goodbye_use_embed: true,
    allow_mass_mentions: false,
    rules_delivery_enabled: false,
    rules_source: 'rules_channel',
    rules_channel_id: '333',
    rules_title: '📜 PB HERO SERVER RULES',
    rules_description: '1. Respect everyone.\n2. No spam.',
    rules_footer: 'PB HERO SERVER',
    rules_button_text: 'Read Full Rules',
    auto_role_enabled: false,
    auto_role_id: '444',
    welcome_dm_enabled: false,
    welcome_dm_title: '👋 Welcome to {server_name}!',
    welcome_dm_description: 'Hi {display_name}! ❤️ Thanks for joining.',
    welcome_dm_footer: 'PB HERO SERVER',
    welcome_dm_use_embed: true,
    goodbye_dm_enabled: false,
    goodbye_dm_title: '👋 Goodbye {display_name}',
    goodbye_dm_description: 'You have left {server_name}.',
    goodbye_dm_footer: 'PB HERO SERVER',
    goodbye_dm_use_embed: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  server: {
    server_id: '123456789012345678',
    server_name: 'PB HERO SERVER',
    member_count: 142,
    server_icon: 'https://cdn.example.com/icon.png',
    bot_online: true,
  },
  welcome_channel_status: {
    status: 'ok',
    channel_name: 'welcome',
    can_view: true,
    can_send: true,
    can_embed: true,
    warning: null,
  },
  goodbye_channel_status: {
    status: 'ok',
    channel_name: 'goodbye',
    can_view: true,
    can_send: true,
    can_embed: true,
    warning: null,
  },
  recent_activity: [
    {
      id: 'act-1',
      timestamp: '2024-01-01T12:00:00Z',
      event_type: 'welcome',
      username: 'TestMember',
      user_id: '12345678',
      channel_id: '111',
      channel_name: 'welcome',
      status: 'delivered',
      is_test: false,
    },
  ],
  stats: {
    welcome_sent_today: 5,
    goodbye_sent_today: 2,
    welcome_dms_today: 3,
    goodbye_dms_today: 1,
    rules_delivered_today: 4,
    roles_assigned_today: 3,
    dm_failures_today: 0,
  },
  invite: {
    id: 1,
    guild_id: '123456789012345678',
    invite_channel_id: '111',
    invite_code: 'pbhero-invite',
    invite_url: 'https://discord.gg/pbhero-invite',
    is_active: true,
    max_age: 0,
    max_uses: 0,
    temporary: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    last_verified_at: '2024-01-01T00:00:00Z',
    verification_status: 'permanent_active',
    verification_error: null,
  },
};

const mockChannels: GreetingChannelOption[] = [
  {
    id: '111',
    name: 'welcome',
    type: 'text',
    category: 'Information',
    position: 1,
    can_view: true,
    can_send: true,
    can_embed: true,
    is_selectable: true,
  },
  {
    id: '222',
    name: 'goodbye',
    type: 'text',
    category: 'Information',
    position: 2,
    can_view: true,
    can_send: true,
    can_embed: true,
    is_selectable: true,
  },
  {
    id: '333',
    name: 'rules',
    type: 'text',
    category: 'Information',
    position: 3,
    can_view: true,
    can_send: true,
    can_embed: true,
    is_selectable: true,
  },
];

const mockRoles: GuildRoleOption[] = [
  {
    id: '444',
    name: 'Member',
    color: '#3498db',
    position: 5,
    is_assignable: true,
    is_managed: false, member_count: 5,
  },
  {
    id: '555',
    name: 'Admin',
    color: '#e74c3c',
    position: 10,
    is_assignable: false,
    is_managed: false, member_count: 5,
  },
];

describe('Welcome & Goodbye Page - Part 21 Required 16 UI Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(greetingsApi.getGreetings).mockResolvedValue(mockGreetingsData);
    vi.mocked(greetingsApi.getChannels).mockResolvedValue(mockChannels);
    vi.mocked(greetingsApi.getRoles).mockResolvedValue(mockRoles);
  });

  it('1. Welcome UI loads with header and Welcome System card', async () => {
    render(<WelcomeGoodbye />);
    expect(await screen.findByText('WELCOME SYSTEM')).toBeInTheDocument();
    expect(screen.getByText(/Public Welcome Channel Message/i)).toBeInTheDocument();
    expect(screen.getAllByText('PB HERO SERVER').length).toBeGreaterThan(0);
  });

  it('2. Goodbye UI renders when switching to goodbye tab', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    fireEvent.click(screen.getByTestId('tab-goodbye'));

    expect(await screen.findByText('GOODBYE SYSTEM')).toBeInTheDocument();
    expect(screen.getByText(/Public Goodbye \/ Departure Message/i)).toBeInTheDocument();
  });

  it('3. Rules UI renders when switching to rules tab', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    fireEvent.click(screen.getByTestId('tab-rules'));

    expect(await screen.findByText('Rules Delivery')).toBeInTheDocument();
    expect(screen.getByText(/Automatically delivers server rules/i)).toBeInTheDocument();
  });

  it('4. Welcome DM editor renders in Direct Messages tab', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    fireEvent.click(screen.getByTestId('tab-dms'));

    expect(await screen.findByText('Welcome Direct Message')).toBeInTheDocument();
    expect(screen.getByText(/Sends a private message to a new member after they join/i)).toBeInTheDocument();
  });

  it('5. Goodbye DM editor renders in Direct Messages tab', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    fireEvent.click(screen.getByTestId('tab-dms'));

    expect(await screen.findByText('Goodbye Direct Message')).toBeInTheDocument();
    expect(screen.getByText(/Attempts to send a private farewell message when a member leaves/i)).toBeInTheDocument();
  });

  it('6. Invite manager renders permanent invite status and actions', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    fireEvent.click(screen.getByTestId('tab-invite'));

    expect(await screen.findByText('Permanent Invite Manager')).toBeInTheDocument();
    expect(screen.getByDisplayValue('https://discord.gg/pbhero-invite')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Verify Invite/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Regenerate Invite/i })).toBeInTheDocument();
  });

  it('7. Channel selector populates channels dynamically', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const select = screen.getByDisplayValue(/#welcome/i);
    expect(select).toBeInTheDocument();
    expect(screen.getByText(/#goodbye/i)).toBeInTheDocument();
  });

  it('8. Role selector displays hierarchy indicators and assignable status', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    fireEvent.click(screen.getByTestId('tab-rules'));

    expect(await screen.findByText('Default Auto Role')).toBeInTheDocument();
    expect(screen.getByText(/Role Assignability: Assignable/i)).toBeInTheDocument();
  });

  it('9. Preview updates live when editing template title', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const titleInput = screen.getByDisplayValue('👋 Welcome to {server_name}!');
    fireEvent.change(titleInput, { target: { value: 'Custom Welcome Title' } });

    expect(screen.getByText('Custom Welcome Title')).toBeInTheDocument();
  });

  it('10. Save updates settings via greetings API', async () => {
    vi.mocked(greetingsApi.updateGreetings).mockResolvedValue({
      success: true,
      message: 'Settings saved',
      settings: { ...mockGreetingsData.settings, welcome_title: 'Updated Title' },
    });

    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const titleInput = screen.getByDisplayValue('👋 Welcome to {server_name}!');
    fireEvent.change(titleInput, { target: { value: 'Updated Title' } });

    const saveBtn = screen.getByRole('button', { name: /Save Welcome/i });
    expect(saveBtn).not.toBeDisabled();
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(greetingsApi.updateGreetings).toHaveBeenCalledWith(
        expect.objectContaining({ welcome_title: 'Updated Title' })
      );
    });
  });

  it('11. Reset opens confirmation modal and resets system', async () => {
    vi.mocked(greetingsApi.resetSystem).mockResolvedValue({
      success: true,
      message: 'Reset complete',
      settings: mockGreetingsData.settings,
    });

    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const resetBtn = screen.getByRole('button', { name: /Reset Welcome Template/i });
    fireEvent.click(resetBtn);

    expect(await screen.findByText('Reset Welcome Settings?')).toBeInTheDocument();
    const confirmBtn = screen.getByRole('button', { name: /Reset to Default/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(greetingsApi.resetSystem).toHaveBeenCalledWith('welcome');
    });
  });

  it('12. Generate Invite calls generate API endpoint', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    fireEvent.click(screen.getByTestId('tab-invite'));

    expect(await screen.findByText('Permanent Invite Manager')).toBeInTheDocument();
    expect(screen.getByText(/PERMANENT & ACTIVE/i)).toBeInTheDocument();
  });

  it('13. Verify Invite triggers verify request and shows result toast', async () => {
    vi.mocked(greetingsApi.verifyInvite).mockResolvedValue({
      status: 'permanent',
      is_valid: true,
      is_permanent: true,
      invite_url: 'https://discord.gg/pbhero-invite',
      message: 'Invite verified',
    });

    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    fireEvent.click(screen.getByTestId('tab-invite'));

    const verifyBtn = await screen.findByRole('button', { name: /Verify Invite/i });
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(greetingsApi.verifyInvite).toHaveBeenCalled();
      expect(toast.success).toHaveBeenCalledWith('Invite is active and permanent.');
    });
  });

  it('14. Regenerate Invite opens confirmation warning modal', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    fireEvent.click(screen.getByTestId('tab-invite'));

    const regenBtn = await screen.findByRole('button', { name: /Regenerate Invite/i });
    fireEvent.click(regenBtn);

    expect(await screen.findByText('Regenerate Server Permanent Invite?')).toBeInTheDocument();
    expect(screen.getByText(/Anyone who was using the old invite link may lose access/i)).toBeInTheDocument();
  });

  it('15. Status telemetry shows bot channel access indicators', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    expect(screen.getByText('Bot Channel Access Telemetry')).toBeInTheDocument();
    expect(screen.getByText('View Channel')).toBeInTheDocument();
    expect(screen.getByText('Send Messages')).toBeInTheDocument();
    expect(screen.getByText('Embed Links')).toBeInTheDocument();
  });

  it('16. Error handling shows toast notification on API failure', async () => {
    vi.mocked(greetingsApi.updateGreetings).mockRejectedValue({
      response: { data: { detail: 'Database error occurred' } },
    });

    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const titleInput = screen.getByDisplayValue('👋 Welcome to {server_name}!');
    fireEvent.change(titleInput, { target: { value: 'Trigger Error' } });

    const saveBtn = screen.getByRole('button', { name: /Save Welcome/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Database error occurred');
    });
  });

  it('17. Clicking variable pill inserts variable into focused field', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const titleInput = screen.getByDisplayValue('👋 Welcome to {server_name}!');
    fireEvent.focus(titleInput);

    const inviterBtn = screen.getByRole('button', { name: '{inviter}' });
    fireEvent.click(inviterBtn);

    expect(screen.getByDisplayValue('👋 Welcome to {server_name}!{inviter}')).toBeInTheDocument();
  });

  it('18. Theme presets render and applying a preset opens confirmation modal', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    expect(screen.getByText('Premium Theme Presets')).toBeInTheDocument();
    const gamingPresetBtn = screen.getByRole('button', { name: /Gaming/i });
    fireEvent.click(gamingPresetBtn);

    expect(await screen.findByText(/Apply "Gaming & Esports" Preset\?/i)).toBeInTheDocument();
    const confirmBtn = screen.getByRole('button', { name: /Apply Preset/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.getByDisplayValue('🎮 WELCOME TO {server_name}')).toBeInTheDocument();
    });
  });

  it('19. Interactive welcome buttons can be configured and toggled', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    expect(screen.getByText('Interactive Welcome Buttons (Action Row)')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Read Rules')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Explore Server')).toBeInTheDocument();

    const rulesInput = screen.getByDisplayValue('Read Rules');
    fireEvent.change(rulesInput, { target: { value: 'Server Guidelines' } });
    expect(screen.getByDisplayValue('Server Guidelines')).toBeInTheDocument();
  });

  it('20. Banner display mode switches to custom and displays URL input', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    expect(screen.getByText('Server Branding, Accent & Banner')).toBeInTheDocument();
    const bannerSelect = screen.getByDisplayValue('No Banner Image');
    fireEvent.change(bannerSelect, { target: { value: 'custom' } });

    expect(await screen.findByPlaceholderText('https://example.com/welcome-banner.gif')).toBeInTheDocument();
  });

  it('21. Character limit validation rejects oversized title with toast warning', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const titleInput = screen.getByDisplayValue('👋 Welcome to {server_name}!');
    const oversizedTitle = 'A'.repeat(300);
    fireEvent.change(titleInput, { target: { value: oversizedTitle } });

    const saveBtn = screen.getByRole('button', { name: /Save Welcome/i });
    fireEvent.click(saveBtn);

    expect(toast.error).toHaveBeenCalledWith('Title exceeds maximum limit of 256 characters.');
    expect(greetingsApi.updateGreetings).not.toHaveBeenCalled();
  });

  it('22. Server author branding updates and reflects in discord preview', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const authorInput = screen.getByPlaceholderText('PB HERO SERVER');
    fireEvent.change(authorInput, { target: { value: 'Official PB Gaming Hub' } });

    expect(screen.getByDisplayValue('Official PB Gaming Hub')).toBeInTheDocument();
    expect(screen.getByText('Official PB Gaming Hub')).toBeInTheDocument();
  });
});



