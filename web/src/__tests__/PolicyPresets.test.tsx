import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PolicyPresetCard } from '../components/PolicyPresetCard';
import { PolicyProfile } from '../types';

const mockProfile: PolicyProfile = {
  id: 1,
  name: 'Image Only',
  description: 'Only images are allowed. Text and links are blocked.',
  is_builtin: true,
  allow_text: 'deny',
  allow_links: 'deny',
  allow_images: 'allow',
  allow_videos: 'deny',
  allow_files: 'deny',
  allow_stickers: 'deny',
  allow_everyone: 'deny',
  allow_here: 'deny',
  allow_role_mentions: 'deny',
  allow_user_mentions: 'deny',
};

describe('PolicyPresetCard Component', () => {
  it('renders preset summary and status badges', () => {
    render(
      <PolicyPresetCard
        profile={mockProfile}
        onApply={vi.fn()}
      />
    );

    expect(screen.getByText('Image Only')).toBeInTheDocument();
    expect(screen.getByText('Only images are allowed. Text and links are blocked.')).toBeInTheDocument();

    // Check summary badges
    expect(screen.getByText('TEXT')).toBeInTheDocument();
    expect(screen.getByText('IMAGES')).toBeInTheDocument();
    expect(screen.getByText('LINKS')).toBeInTheDocument();
    expect(screen.getByText('FILES')).toBeInTheDocument();
  });

  it('triggers onApply callback when Apply button is clicked', () => {
    const handleApply = vi.fn();
    render(
      <PolicyPresetCard
        profile={mockProfile}
        onApply={handleApply}
      />
    );

    const applyBtn = screen.getByRole('button', { name: /apply to channel/i });
    fireEvent.click(applyBtn);

    expect(handleApply).toHaveBeenCalledWith(mockProfile);
  });
});
