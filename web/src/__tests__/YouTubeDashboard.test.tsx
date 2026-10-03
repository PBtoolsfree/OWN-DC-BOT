import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import YouTube from '../pages/YouTube';
import { youtubeApi } from '../api/youtube';
import { channelsApi } from '../api/channels';
import { NotificationTemplate, YouTubeEventType } from '../types';

vi.mock('../api/youtube', () => ({
  youtubeApi: {
    getChannels: vi.fn(),
    getChannel: vi.fn(),
    getTemplates: vi.fn(),
    getTemplate: vi.fn(),
    updateTemplate: vi.fn(),
    resetTemplate: vi.fn(),
    addChannel: vi.fn(),
    toggleChannel: vi.fn(),
    testChannel: vi.fn(),
    deleteChannel: vi.fn(),
  },
}));

vi.mock('../api/channels', () => ({
  channelsApi: {
    getChannels: vi.fn(),
    getRoles: vi.fn(),
  },
}));

const mockTemplates: NotificationTemplate[] = [
  {
    event_type: 'upload',
    title_template: '🎬 NEW VIDEO — {channel_name}',
    description_template: '**{video_title}**\n\nA new video is now available on YouTube.',
    mention_role: 'PB Gang',
    footer_text: 'PB HERO Personal Bot',
    show_thumbnail: true,
    show_timestamp: true,
    enable_button: true,
  },
  {
    event_type: 'scheduled_live',
    title_template: '⏰ LIVE SCHEDULED — {channel_name}',
    description_template: '**{video_title}**\n\nThe livestream is scheduled to start soon.',
    mention_role: 'PB Gang',
    footer_text: 'PB HERO Personal Bot',
    show_thumbnail: true,
    show_timestamp: true,
    enable_button: true,
  },
  {
    event_type: 'live_started',
    title_template: '🔴 {channel_name} IS NOW LIVE!',
    description_template: '**{video_title}**\n\nJoin the stream now on YouTube.',
    mention_role: 'PB Gang',
    footer_text: 'PB HERO Personal Bot',
    show_thumbnail: true,
    show_timestamp: true,
    enable_button: true,
  },
  {
    event_type: 'premiere',
    title_template: '🎬 PREMIERE — {channel_name}',
    description_template: '**{video_title}**\n\nA new YouTube Premiere is scheduled.',
    mention_role: 'PB Gang',
    footer_text: 'PB HERO Personal Bot',
    show_thumbnail: true,
    show_timestamp: true,
    enable_button: true,
  },
];

describe('YouTube Dashboard Navigation & Notification Templates', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(youtubeApi.getChannels).mockResolvedValue([]);
    vi.mocked(channelsApi.getChannels).mockResolvedValue([]);
    vi.mocked(channelsApi.getRoles).mockResolvedValue([]);
    vi.mocked(youtubeApi.getTemplates).mockResolvedValue(mockTemplates);
    vi.mocked(youtubeApi.updateTemplate).mockImplementation(async (eventType: string, data: Partial<NotificationTemplate>) => ({
      success: true,
      template: {
        event_type: eventType as YouTubeEventType,
        title_template: data.title_template || '',
        description_template: data.description_template || '',
        mention_role: data.mention_role,
        footer_text: data.footer_text,
        show_thumbnail: data.show_thumbnail ?? true,
        show_timestamp: data.show_timestamp ?? true,
        enable_button: data.enable_button ?? true,
      },
    }));
    vi.mocked(youtubeApi.resetTemplate).mockImplementation(async (eventType: string) => {
      const match = mockTemplates.find((t) => t.event_type === eventType) || mockTemplates[0];
      return { success: true, template: match };
    });
  });

  const renderWithRoute = (initialEntry: string) => {
    return render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/youtube" element={<YouTube />} />
        </Routes>
      </MemoryRouter>
    );
  };

  it('1. Channels tab loads correctly by default', async () => {
    renderWithRoute('/youtube?tab=channels');
    expect(await screen.findByText(/No YouTube Channels Monitored/i)).toBeInTheDocument();
    expect(screen.queryByText(/Discord Embed Live Preview/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/YouTube Monitoring Polling Intervals/i)).not.toBeInTheDocument();
  });

  it('2. Notifications tab loads correctly when accessed via URL', async () => {
    renderWithRoute('/youtube?tab=notifications');
    expect(await screen.findByText(/Discord Embed Live Preview/i)).toBeInTheDocument();
    expect(screen.getByText('New Video')).toBeInTheDocument();
    expect(screen.getByText('Scheduled Live')).toBeInTheDocument();
    expect(screen.getByText('Live Started')).toBeInTheDocument();
    expect(screen.getByText('Premiere')).toBeInTheDocument();
  });

  it('3. Settings tab loads correctly when accessed via URL', async () => {
    renderWithRoute('/youtube?tab=settings');
    expect(await screen.findByText(/YouTube Monitoring Polling Intervals/i)).toBeInTheDocument();
    expect(screen.queryByText(/Discord Embed Live Preview/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/No YouTube Channels Monitored/i)).not.toBeInTheDocument();
  });

  it('4. Switching tabs updates view content properly', async () => {
    renderWithRoute('/youtube?tab=channels');
    expect(await screen.findByText(/No YouTube Channels Monitored/i)).toBeInTheDocument();

    // Click Notification Templates tab
    fireEvent.click(screen.getByRole('button', { name: /Notification Templates/i }));
    expect(await screen.findByText(/Discord Embed Live Preview/i)).toBeInTheDocument();

    // Click Settings tab
    fireEvent.click(screen.getByRole('button', { name: /Settings/i }));
    expect(await screen.findByText(/YouTube Monitoring Polling Intervals/i)).toBeInTheDocument();
  });

  it('5. Event template subtabs: New Video, Scheduled Live, Live Started, Premiere load independently', async () => {
    renderWithRoute('/youtube?tab=notifications');
    await screen.findByText(/Discord Embed Live Preview/i);

    // Default is New Video
    expect(screen.getByText(/New Video Template/i)).toBeInTheDocument();
    expect(screen.getByText('NEW VIDEO')).toBeInTheDocument();
    expect(screen.getByText('Watch Video')).toBeInTheDocument();

    // Switch to Scheduled Live
    fireEvent.click(screen.getByRole('button', { name: /Scheduled Live/i }));
    expect(screen.getByText(/Scheduled Live Template/i)).toBeInTheDocument();
    expect(screen.getByText('SCHEDULED')).toBeInTheDocument();
    expect(screen.getByText('Watch Live')).toBeInTheDocument();

    // Switch to Live Started
    fireEvent.click(screen.getByRole('button', { name: /Live Started/i }));
    expect(screen.getByText(/Live Started Template/i)).toBeInTheDocument();
    expect(screen.getByText('LIVE')).toBeInTheDocument();

    // Switch to Premiere
    fireEvent.click(screen.getByRole('button', { name: /Premiere/i }));
    expect(screen.getByText(/Premiere Template/i)).toBeInTheDocument();
    expect(screen.getByText('PREMIERE')).toBeInTheDocument();
    expect(screen.getByText('Watch Premiere')).toBeInTheDocument();
  });

  it('6. Modifying one template does NOT alter another event template', async () => {
    renderWithRoute('/youtube?tab=notifications');
    await screen.findByText(/Discord Embed Live Preview/i);

    // Modify New Video Title
    const titleInput = screen.getByPlaceholderText(/🎬 NEW VIDEO/i);
    fireEvent.change(titleInput, { target: { value: 'MODIFIED NEW VIDEO TITLE {channel_name}' } });
    expect(titleInput).toHaveValue('MODIFIED NEW VIDEO TITLE {channel_name}');

    // Switch to Live Started
    fireEvent.click(screen.getByRole('button', { name: /Live Started/i }));
    expect(screen.getByText(/Live Started Template/i)).toBeInTheDocument();
    // Live Started title should still be default
    const liveTitleInput = screen.getByPlaceholderText(/🎬 NEW VIDEO/i);
    expect(liveTitleInput).toHaveValue('🔴 {channel_name} IS NOW LIVE!');

    // Switch back to New Video
    fireEvent.click(screen.getByRole('button', { name: /New Video/i }));
    const backToNewVideoInput = screen.getByPlaceholderText(/🎬 NEW VIDEO/i);
    expect(backToNewVideoInput).toHaveValue('MODIFIED NEW VIDEO TITLE {channel_name}');
  });

  it('7. Reset template triggers confirmation modal with event name', async () => {
    renderWithRoute('/youtube?tab=notifications');
    await screen.findByText(/Discord Embed Live Preview/i);

    // Switch to Live Started
    fireEvent.click(screen.getByRole('button', { name: /Live Started/i }));
    expect(screen.getByText(/Live Started Template/i)).toBeInTheDocument();

    // Click Reset to Default
    fireEvent.click(screen.getByRole('button', { name: /Reset to Default/i }));

    // Modal should be open with event-specific message
    expect(screen.getByRole('heading', { name: /Reset Live Started Template/i })).toBeInTheDocument();
    expect(screen.getByText(/Reset Live Started template to default\?/i)).toBeInTheDocument();

    // Click confirm in modal
    const confirmButtons = screen.getAllByRole('button', { name: /Reset to Default/i });
    // The last button is inside the modal
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(youtubeApi.resetTemplate).toHaveBeenCalledWith('live_started');
    });
  });

  it('8. Variable helper inserts clicked variable tag into template', async () => {
    renderWithRoute('/youtube?tab=notifications');
    await screen.findByText(/Discord Embed Live Preview/i);

    // Click {published_at} button
    const varBtn = screen.getByRole('button', { name: '{published_at}' });
    fireEvent.click(varBtn);

    // Verify description textarea got the variable appended
    const descArea = screen.getByPlaceholderText(/\*\*\{video_title\}\*\*/i) as HTMLTextAreaElement;
    expect(descArea.value).toContain('{published_at}');
  });

  it('9. Saving template validates fields and calls updateTemplate', async () => {
    renderWithRoute('/youtube?tab=notifications');
    await screen.findByText(/Discord Embed Live Preview/i);

    // Click Save Template
    fireEvent.click(screen.getByRole('button', { name: /Save Template/i }));

    await waitFor(() => {
      expect(youtubeApi.updateTemplate).toHaveBeenCalledWith(
        'upload',
        expect.objectContaining({
          title_template: expect.stringContaining('🎬 NEW VIDEO'),
        })
      );
    });
  });
});
