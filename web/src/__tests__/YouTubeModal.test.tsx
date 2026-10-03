import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { YouTubeChannelModal } from '../components/YouTubeChannelModal';
import { DiscordChannel } from '../types';

const mockChannels: DiscordChannel[] = [
  { id: '1001', name: 'youtube-feed', type: 'text', category: 'FEED', position: 1 },
  { id: '1002', name: 'general', type: 'text', category: 'GENERAL', position: 2 }
];

describe('YouTubeChannelModal Component', () => {
  it('renders modal with required fields and NEVER renders an API Key input', () => {
    render(
      <YouTubeChannelModal
        isOpen={true}
        channels={mockChannels}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />
    );

    expect(screen.getByText('Add YouTube Channel')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/@handle/i)).toBeInTheDocument();
    expect(screen.getByText('Destination Discord Channel')).toBeInTheDocument();

    // STRICT CHECK: NO YOUTUBE API KEY FIELD
    expect(screen.queryByText(/api key/i)).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/api key/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/quota/i)).not.toBeInTheDocument();
  });

  it('validates URL before submitting', async () => {
    const handleSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <YouTubeChannelModal
        isOpen={true}
        channels={mockChannels}
        onClose={vi.fn()}
        onSubmit={handleSubmit}
      />
    );

    const input = screen.getByPlaceholderText(/@handle/i);
    const submitBtn = screen.getByRole('button', { name: /save channel/i });

    // Invalid url
    fireEvent.change(input, { target: { value: 'invalid_bad_input' } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText(/enter a valid/i)).toBeInTheDocument();
    expect(handleSubmit).not.toHaveBeenCalled();

    // Valid handle
    fireEvent.change(input, { target: { value: '@PBHeroOfficial' } });
    fireEvent.click(submitBtn);

    expect(handleSubmit).toHaveBeenCalled();
  });
});
