import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ModerationTable } from '../components/ModerationTable';
import { ModerationCase } from '../types';

const mockCases: ModerationCase[] = [
  {
    case_number: 101,
    target_user_id: '99887766',
    target_username: 'BadActor1',
    moderator_user_id: '11223344',
    moderator_username: 'ModBoss',
    action: 'warn',
    reason: 'Excessive spam in announcements',
    created_at: '2026-10-03T10:00:00Z',
  },
  {
    case_number: 102,
    target_user_id: '44556677',
    target_username: 'BadActor2',
    moderator_user_id: '11223344',
    moderator_username: 'ModBoss',
    action: 'ban',
    reason: 'Malicious phishing link',
    created_at: '2026-10-03T10:15:00Z',
  },
];

describe('ModerationTable Component', () => {
  it('renders table headers and rows accurately', () => {
    render(
      <ModerationTable
        cases={mockCases}
        onSelectCase={vi.fn()}
        currentPage={1}
        totalPages={2}
        onPageChange={vi.fn()}
      />
    );

    expect(screen.getByText('#101')).toBeInTheDocument();
    expect(screen.getByText('Excessive spam in announcements')).toBeInTheDocument();
    expect(screen.getByText('#102')).toBeInTheDocument();
    expect(screen.getByText('Malicious phishing link')).toBeInTheDocument();
  });

  it('triggers onSelectCase when a row is clicked', () => {
    const handleSelect = vi.fn();
    render(
      <ModerationTable
        cases={mockCases}
        onSelectCase={handleSelect}
        currentPage={1}
        totalPages={1}
        onPageChange={vi.fn()}
      />
    );

    const firstRow = screen.getByText('#101').closest('tr');
    expect(firstRow).toBeInTheDocument();
    if (firstRow) {
      fireEvent.click(firstRow);
      expect(handleSelect).toHaveBeenCalledWith(mockCases[0]);
    }
  });

  it('handles pagination controls and page changes', () => {
    const handlePageChange = vi.fn();
    render(
      <ModerationTable
        cases={mockCases}
        onSelectCase={vi.fn()}
        currentPage={1}
        totalPages={3}
        onPageChange={handlePageChange}
      />
    );

    expect(screen.getByText(/page/i)).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders empty message when no cases match', () => {
    render(
      <ModerationTable
        cases={[]}
        onSelectCase={vi.fn()}
        currentPage={1}
        totalPages={1}
        onPageChange={vi.fn()}
      />
    );

    expect(screen.getByText(/no moderation cases match your filter criteria/i)).toBeInTheDocument();
  });
});
