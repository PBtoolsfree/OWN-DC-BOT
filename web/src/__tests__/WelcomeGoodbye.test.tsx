import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import WelcomeGoodbye from '../pages/WelcomeGoodbye';
import { greetingsApi } from '../api/greetings';
import { GreetingsResponse, GreetingChannelOption } from '../types';

vi.mock('../api/greetings', () => ({
  greetingsApi: {
    getGreetings: vi.fn(),
    updateGreetings: vi.fn(),
    getChannels: vi.fn(),
    testWelcome: vi.fn(),
    testGoodbye: vi.fn(),
    resetSystem: vi.fn(),
  },
}));

vi.mock('../hooks/useToast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
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
    name: 'announcements',
    type: 'announcement',
    category: 'Information',
    position: 3,
    can_view: true,
    can_send: true,
    can_embed: true,
    is_selectable: true,
  },
];

describe('Welcome & Goodbye Page UI Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(greetingsApi.getGreetings).mockResolvedValue(mockGreetingsData);
    vi.mocked(greetingsApi.getChannels).mockResolvedValue(mockChannels);
  });

  it('1. Welcome page loads with header and status badges', async () => {
    render(<WelcomeGoodbye />);
    expect(await screen.findByText(/SERVER GREETINGS AUTOMATION/i)).toBeInTheDocument();
    expect(screen.getAllByText(/PB HERO SERVER/i).length).toBeGreaterThan(0);
    expect(screen.getByText('WELCOME SYSTEM')).toBeInTheDocument();
  });

  it('2. Goodbye page loads with its own configuration card', async () => {
    render(<WelcomeGoodbye />);
    expect(await screen.findByText('GOODBYE SYSTEM')).toBeInTheDocument();
    expect(screen.getByText(/Sent automatically when a member leaves/i)).toBeInTheDocument();
  });

  it('3. Channel dropdown loads dynamically from connected guild', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');
    const selects = screen.getAllByRole('combobox');
    expect(selects.length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/#welcome/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/#goodbye/i).length).toBeGreaterThan(0);
  });

  it('4. Enable toggle works for Welcome and Goodbye', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');
    const checkboxes = screen.getAllByRole('checkbox');
    // First checkbox is welcome_enabled
    const welcomeToggle = checkboxes[0];
    expect(welcomeToggle).not.toBeChecked();
    fireEvent.click(welcomeToggle);
    expect(welcomeToggle).toBeChecked();
  });

  it('5. Save works for Welcome and calls updateGreetings', async () => {
    vi.mocked(greetingsApi.updateGreetings).mockResolvedValue({
      success: true,
      message: 'Saved',
      settings: { ...mockGreetingsData.settings, welcome_title: 'New Welcome!' },
    });

    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const titleInput = screen.getByDisplayValue('👋 Welcome to {server_name}!');
    fireEvent.change(titleInput, { target: { value: 'New Welcome!' } });

    const saveBtn = screen.getByRole('button', { name: /Save Welcome/i });
    expect(saveBtn).not.toBeDisabled();
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(greetingsApi.updateGreetings).toHaveBeenCalledWith(
        expect.objectContaining({ welcome_title: 'New Welcome!' })
      );
    });
  });

  it('6. Preview works and updates when title changes', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const titleInput = screen.getByDisplayValue('👋 Welcome to {server_name}!');
    fireEvent.change(titleInput, { target: { value: 'Custom Title Here' } });

    expect(screen.getByText('Custom Title Here')).toBeInTheDocument();
  });

  it('7. Test button calls test endpoint', async () => {
    vi.mocked(greetingsApi.testWelcome).mockResolvedValue({
      status: 'ok',
      message: 'Test message sent',
      channel_id: '111',
      channel_name: 'welcome',
    });

    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const testBtn = screen.getByRole('button', { name: /Test Welcome/i });
    fireEvent.click(testBtn);

    await waitFor(() => {
      expect(greetingsApi.testWelcome).toHaveBeenCalled();
    });
  });

  it('8. Reset Welcome only opens modal and resets welcome', async () => {
    vi.mocked(greetingsApi.resetSystem).mockResolvedValue({
      success: true,
      message: 'Welcome settings reset',
      settings: mockGreetingsData.settings,
    });

    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const resetWelcomeBtn = screen.getByRole('button', { name: /Reset Welcome/i });
    fireEvent.click(resetWelcomeBtn);

    expect(await screen.findByText(/Reset Welcome Settings\?/i)).toBeInTheDocument();
    const confirmBtn = screen.getByRole('button', { name: /Reset to Default/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(greetingsApi.resetSystem).toHaveBeenCalledWith('welcome');
    });
  });

  it('9. Reset Goodbye only resets goodbye', async () => {
    vi.mocked(greetingsApi.resetSystem).mockResolvedValue({
      success: true,
      message: 'Goodbye settings reset',
      settings: mockGreetingsData.settings,
    });

    render(<WelcomeGoodbye />);
    await screen.findByText('GOODBYE SYSTEM');

    const resetGoodbyeBtn = screen.getByRole('button', { name: /Reset Goodbye/i });
    fireEvent.click(resetGoodbyeBtn);

    expect(await screen.findByText(/Reset Goodbye Settings\?/i)).toBeInTheDocument();
    const confirmBtn = screen.getByRole('button', { name: /Reset to Default/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(greetingsApi.resetSystem).toHaveBeenCalledWith('goodbye');
    });
  });

  it('10. Variable insertion appends chip to focused field', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const titleInput = screen.getByDisplayValue('👋 Welcome to {server_name}!');
    fireEvent.focus(titleInput);

    const userMentionChip = screen.getAllByRole('button', { name: '{user_mention}' })[0];
    fireEvent.click(userMentionChip);

    expect(titleInput).toHaveValue('👋 Welcome to {server_name}!{user_mention}');
  });

  it('11. Unsaved changes disables save button initially and enables on change', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    const saveBtn = screen.getByRole('button', { name: /Save Welcome/i });
    expect(saveBtn).toBeDisabled();

    const titleInput = screen.getByDisplayValue('👋 Welcome to {server_name}!');
    fireEvent.change(titleInput, { target: { value: 'Something Changed' } });

    expect(saveBtn).not.toBeDisabled();
  });

  it('12. Permission status displays telemetry indicators', async () => {
    render(<WelcomeGoodbye />);
    await screen.findByText('WELCOME SYSTEM');

    expect(screen.getAllByText('Bot Channel Access').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('View Channel').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Send Messages').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Embed Links').length).toBeGreaterThanOrEqual(2);
  });
});
