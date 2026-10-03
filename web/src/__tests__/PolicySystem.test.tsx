import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PolicyProfiles from '../pages/PolicyProfiles';
import ModeratorSettings from '../pages/ModeratorSettings';
import { policiesApi } from '../api/policies';
import { channelsApi } from '../api/channels';
import { moderationApi } from '../api/moderation';

vi.mock('../api/policies', () => ({
  policiesApi: {
    getProfiles: vi.fn(),
    createProfile: vi.fn(),
    updateProfile: vi.fn(),
    deleteProfile: vi.fn(),
    duplicateProfile: vi.fn(),
    applyProfile: vi.fn(),
  },
}));

vi.mock('../api/channels', () => ({
  channelsApi: {
    getChannels: vi.fn(),
  },
}));

vi.mock('../api/moderation', () => ({
  moderationApi: {
    getModLogSettings: vi.fn(),
    updateModLogSettings: vi.fn(),
  },
}));

const mockBuiltInProfiles = [
  {
    id: 1,
    name: 'ANNOUNCEMENTS',
    description: 'Official announcements only.',
    category: 'Announcements',
    is_builtin: true,
    allow_text: 'deny',
    allow_links: 'deny',
    allow_images: 'deny',
    allow_videos: 'deny',
    allow_files: 'deny',
    allow_stickers: 'deny',
    allow_everyone: 'deny',
    allow_here: 'deny',
    allow_role_mentions: 'deny',
    allow_user_mentions: 'deny',
  },
  {
    id: 2,
    name: 'GENERAL CHAT',
    description: 'Normal community discussion.',
    category: 'General',
    is_builtin: true,
    allow_text: 'allow',
    allow_links: 'allow',
    allow_images: 'allow',
    allow_videos: 'allow',
    allow_files: 'allow',
    allow_stickers: 'allow',
    allow_everyone: 'deny',
    allow_here: 'deny',
    allow_role_mentions: 'allow',
    allow_user_mentions: 'allow',
  },
  {
    id: 3,
    name: 'CUSTOM SAFE LINKS',
    description: 'User created safe link policy.',
    category: 'Media',
    is_builtin: false,
    allow_text: 'allow',
    allow_links: 'deny',
    allow_images: 'allow',
    allow_videos: 'deny',
    allow_files: 'deny',
    allow_stickers: 'allow',
    allow_everyone: 'deny',
    allow_here: 'deny',
    allow_role_mentions: 'allow',
    allow_user_mentions: 'allow',
  },
];

const mockChannels = [
  { id: '1001', name: 'general', type: 'text', category: 'GENERAL AREA', position: 0 },
  { id: '1002', name: 'announcements', type: 'text', category: 'IMPORTANT', position: 1 },
];

describe('Policy Profiles System Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (policiesApi.getProfiles as any).mockResolvedValue(mockBuiltInProfiles);
    (channelsApi.getChannels as any).mockResolvedValue(mockChannels);
  });

  it('renders built-in presets and custom policies properly', async () => {
    render(<PolicyProfiles />);

    await waitFor(() => {
      expect(screen.getByText('BUILT-IN PRESETS')).toBeInTheDocument();
      expect(screen.getByText('CUSTOM POLICIES')).toBeInTheDocument();
    });

    expect(screen.getByText('ANNOUNCEMENTS')).toBeInTheDocument();
    expect(screen.getByText('GENERAL CHAT')).toBeInTheDocument();
    expect(screen.getByText('CUSTOM SAFE LINKS')).toBeInTheDocument();
  });

  it('opens custom policy modal when button is clicked', async () => {
    render(<PolicyProfiles />);

    await waitFor(() => {
      expect(screen.getByText('+ Create Custom Policy')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('+ Create Custom Policy'));
    expect(screen.getByText('Create Custom Policy')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/STRICT LINKS ONLY/i)).toBeInTheDocument();
  });

  it('opens apply modal with dynamically grouped channel categories', async () => {
    render(<PolicyProfiles />);

    await waitFor(() => {
      expect(screen.getAllByText(/Apply to Channel/i).length).toBeGreaterThan(0);
    });

    const applyButtons = screen.getAllByText(/Apply to Channel/i);
    fireEvent.click(applyButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/DISCORD CHANNELS \(GROUPED BY CATEGORY\)/i)).toBeInTheDocument();
      expect(screen.getByText('IMPORTANT')).toBeInTheDocument();
      expect(screen.getByText('GENERAL AREA')).toBeInTheDocument();
    });
  });
});

describe('Moderator Settings & Discord Mod-Log Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (channelsApi.getChannels as any).mockResolvedValue(mockChannels);
    (moderationApi.getModLogSettings as any).mockResolvedValue({
      mod_log_channel_id: '1002',
      mod_log_events: ['policy_violation', 'blocked_link', 'warning'],
      channel_status: {
        status: 'ok',
        channel_name: 'announcements',
        can_view: true,
        can_send: true,
        can_embed: true,
        warning: null,
      },
    });
    (moderationApi.updateModLogSettings as any).mockResolvedValue({ success: true });
  });

  it('renders Discord log channel selector and bot permissions status', async () => {
    render(<ModeratorSettings />);

    await waitFor(() => {
      expect(screen.getByText('Auto-Moderation Log Channel')).toBeInTheDocument();
      expect(screen.getByText('ACTIVE & READY')).toBeInTheDocument();
    });

    expect(screen.getByText('View Channel')).toBeInTheDocument();
    expect(screen.getByText('Send Messages')).toBeInTheDocument();
    expect(screen.getByText('Embed Links')).toBeInTheDocument();
  });

  it('allows toggling log events and saving configuration', async () => {
    render(<ModeratorSettings />);

    await waitFor(() => {
      expect(screen.getByText('Event Notification Filter Toggles')).toBeInTheDocument();
    });

    const blockedAttachmentToggle = screen.getByText('Blocked Attachment');
    fireEvent.click(blockedAttachmentToggle);

    const saveBtn = screen.getByText('Save Settings');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(moderationApi.updateModLogSettings).toHaveBeenCalled();
    });
  });
});
