import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ExemptionsBypass } from '../pages/ExemptionsBypass';
import { AutomodRules } from '../pages/AutomodRules';
import { WarningsActions } from '../pages/WarningsActions';
import { CaseDetailsModal } from '../components/CaseDetailsModal';
import { ChannelPolicyEditor } from '../components/ChannelPolicyEditor';
import { moderationApi } from '../api/moderation';
import { DiscordChannel, ModerationCase } from '../types';

vi.mock('../api/moderation', () => ({
  moderationApi: {
    getModerationExemptions: vi.fn(),
    createModerationExemption: vi.fn(),
    deleteModerationExemption: vi.fn(),
    getAutomodRules: vi.fn(),
    deleteAutomodRule: vi.fn(),
    getWarnings: vi.fn(),
    getWarningsStats: vi.fn(),
    getEscalationRules: vi.fn(),
    getQuickSetupPreview: vi.fn(),
    applyQuickSetup: vi.fn(),
    getGuildTargets: vi.fn(),
  },
}));

describe('Moderation Control Center Frontend Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Exemptions & Bypass Page', () => {
    it('renders safety banner and lists exemptions', async () => {
      vi.mocked(moderationApi.getModerationExemptions).mockResolvedValue([
        {
          id: 1,
          target_type: 'role',
          target_id: '998877665544',
          target_name: 'Chulankar Moderator',
          scope: 'global',
          bypass_all: false,
          bypass_text: false,
          bypass_links: true,
          bypass_images: false,
          bypass_videos: false,
          bypass_files: false,
          bypass_stickers: false,
          bypass_mentions: true,
          bypass_spam: true,
          bypass_keywords: false,
          bypass_invites: false,
          bypass_warnings: false,
          bypass_timeout: false,
          bypass_kick: false,
          bypass_ban: false,
          created_at: '2026-10-03T12:00:00Z',
        },
      ]);
      vi.mocked(moderationApi.getGuildTargets).mockResolvedValue({
        roles: [{ id: '998877665544', name: 'Chulankar Moderator', color: '#5865F2', position: 5, permissions: { manage_messages: true } }],
        channels: [{ id: '111', name: 'general', type: 'text', category: 'General' }],
        members: [],
        bots: [{ id: '222', username: 'Music Bot', display_name: 'Music Bot', bot: true, roles: [], permissions: {} }],
        categories: [{ id: 'cat-1', name: 'General' }],
      });

      render(<ExemptionsBypass />);

      expect(screen.getByText(/Exemptions & Bypass/i)).toBeInTheDocument();
      expect(screen.getByText(/PB HERO Bypass Safety & Precedence/i)).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Chulankar Moderator')).toBeInTheDocument();
        expect(screen.getByText('role')).toBeInTheDocument();
      });
    });
  });

  describe('Automod Rules Page', () => {
    it('renders automod rules list with toggles', async () => {
      vi.mocked(moderationApi.getAutomodRules).mockResolvedValue([
        {
          id: 1,
          rule_type: 'keyword_filter',
          name: 'Banned Keywords',
          description: 'Filter illicit terms',
          enabled: true,
          scope: 'global',
          threshold: 1,
          time_window_seconds: 10,
          action: 'delete_warn',
          send_dm: true,
          log_event: true,
          cooldown_seconds: 5,
          custom_keywords: ['badword', 'scam'],
        },
        {
          id: 2,
          rule_type: 'invite_filter',
          name: 'Anti-Invite Spam',
          description: 'Blocks unauthorized discord invites',
          enabled: true,
          scope: 'global',
          threshold: 1,
          time_window_seconds: 10,
          action: 'delete_warn',
          send_dm: true,
          log_event: true,
          cooldown_seconds: 5,
          custom_keywords: [],
        },
      ]);

      render(<AutomodRules />);

      expect(screen.getByRole('heading', { level: 1, name: /Automod Rules/i })).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('Banned Keywords')).toBeInTheDocument();
        expect(screen.getByText('Anti-Invite Spam')).toBeInTheDocument();
      });
    });
  });

  describe('Warnings & Actions Page', () => {
    it('renders warning ladder and allows opening quick setup modal', async () => {
      vi.mocked(moderationApi.getWarnings).mockResolvedValue([
        {
          id: 1,
          warning_id: 'WARN-001',
          case_id: 'CASE-001',
          user_id: '12345678',
          username: 'test_troublemaker',
          channel_id: '111',
          channel_name: 'general',
          rule: 'Link Filter',
          reason: 'Unauthorized link posted',
          moderator: 'PB HERO AutoMod',
          severity: 'medium',
          points: 2,
          status: 'active',
          action_taken: 'warn',
          dm_status: 'delivered',
          created_at: '2026-10-03T12:00:00Z',
        },
      ]);

      vi.mocked(moderationApi.getEscalationRules).mockResolvedValue([
        { id: 1, threshold: 1, mode: 'count', action: 'warn', duration: 0, send_dm: true, reason_template: '1st violation' },
        { id: 2, threshold: 3, mode: 'count', action: 'timeout', duration: 600, send_dm: true, reason_template: '3rd violation' },
        { id: 3, threshold: 6, mode: 'count', action: 'ban', duration: 0, send_dm: true, reason_template: '6th violation' },
      ]);

      vi.mocked(moderationApi.getWarningsStats).mockResolvedValue({
        active_warnings: 1,
        warnings_today: 1,
        decay_days: 30,
        mode: 'count',
      });

      vi.mocked(moderationApi.getQuickSetupPreview).mockResolvedValue({
        styles: {
          balanced: {
            name: 'Balanced',
            description: 'Warnings and timeouts for repeated violations',
            actions: ['1st: Warning + DM', '3rd: Timeout 10m', '5th: Ban'],
            decay_days: 30,
          },
          strict: {
            name: 'Strict',
            description: 'Fast escalation ladder',
            actions: ['1st: Timeout 10m', '3rd: Ban'],
            decay_days: 60,
          },
        },
      });

      render(<WarningsActions />);

      expect(screen.getByText(/Warnings & Actions/i)).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByText('WARN-001')).toBeInTheDocument();
        expect(screen.getByText(/1 Violations/i)).toBeInTheDocument();
      });

      // Quick Setup button
      const quickSetupBtn = screen.getByRole('button', { name: /quick setup/i });
      fireEvent.click(quickSetupBtn);

      await waitFor(() => {
        expect(screen.getByText(/Choose Moderation Style/i)).toBeInTheDocument();
        expect(screen.getAllByText(/Balanced/i).length).toBeGreaterThan(0);
        expect(screen.getByText(/Strict/i)).toBeInTheDocument();
      });
    });
  });

  describe('Case Details Modal Component', () => {
    it('displays full case metadata including Case ID and DM status', () => {
      const mockCase: ModerationCase = {
        id: 10,
        case_number: 42,
        case_id: 'CASE-2026-0042',
        target_user_id: '12345678',
        target_username: 'troublemaker#0001',
        moderator_user_id: 'bot-1',
        moderator_username: 'PB HERO AutoMod',
        channel_id: '111',
        channel_name: 'general',
        action: 'timeout',
        reason: 'Repeated unauthorized link spam',
        policy_name: 'DEFAULT_POLICY',
        rule: 'Link Filter',
        warning_id: 'WARN-0042',
        severity: 'high',
        dm_status: 'delivered',
        discord_log_status: 'sent',
        created_at: '2026-10-03T12:00:00Z',
      };

      const onClose = vi.fn();
      render(<CaseDetailsModal caseItem={mockCase} onClose={onClose} />);

      expect(screen.getByText('CASE-2026-0042')).toBeInTheDocument();
      expect(screen.getByText('troublemaker#0001')).toBeInTheDocument();
      expect(screen.getByText(/Repeated unauthorized link spam/i)).toBeInTheDocument();
      expect(screen.getByText('WARN-0042')).toBeInTheDocument();
    });
  });

  describe('ChannelPolicyEditor Voice vs Text Mode', () => {
    it('renders voice controls when channel type is voice', () => {
      const voiceChannel: DiscordChannel = {
        id: 'voice-1',
        name: 'Community Lounge',
        type: 'voice',
        category: 'Voice Channels',
        position: 1,
      };

      render(
        <ChannelPolicyEditor
          channel={voiceChannel}
          policy={null}
          profiles={[]}
          onSave={vi.fn()}
          onOpenSimulator={vi.fn()}
        />
      );

      expect(screen.getByText(/Voice Channel Permissions & Moderation/i)).toBeInTheDocument();
      expect(screen.getByText(/Allow Connect/i)).toBeInTheDocument();
      expect(screen.getByText(/Allow Speak/i)).toBeInTheDocument();
      expect(screen.getByText(/Allow Video \(Camera\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Allow Screen Share \/ Stream/i)).toBeInTheDocument();
    });

    it('renders text controls when channel type is text', () => {
      const textChannel: DiscordChannel = {
        id: 'text-1',
        name: 'general-chat',
        type: 'text',
        category: 'Text Channels',
        position: 1,
      };

      render(
        <ChannelPolicyEditor
          channel={textChannel}
          policy={null}
          profiles={[]}
          onSave={vi.fn()}
          onOpenSimulator={vi.fn()}
        />
      );

      expect(screen.getByText(/Message Content Filtering/i)).toBeInTheDocument();
      expect(screen.getByText(/Allow Text Messages/i)).toBeInTheDocument();
      expect(screen.getByText(/Allow Embedded Links \(URLs\)/i)).toBeInTheDocument();
    });
  });
});
