import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';

describe('Sidebar Navigation Component', () => {
  it('enforces single server display and navigation items', () => {
    render(
      <BrowserRouter>
        <Sidebar onLogout={vi.fn()} />
      </BrowserRouter>
    );

    // Verify Brand
    expect(screen.getByText('PB HERO')).toBeInTheDocument();
    expect(screen.getByText('PERSONAL BOT')).toBeInTheDocument();

    // Verify Connected Server Badge
    expect(screen.getByText(/connected server/i)).toBeInTheDocument();
    expect(screen.getByText(/pb hero server/i)).toBeInTheDocument();

    // STRICT CHECK: NO SERVER SWITCHER / MULTI-SERVER UI
    expect(screen.queryByText(/select server/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/choose server/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/add server/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/switch server/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/guild manager/i)).not.toBeInTheDocument();

    // Verify Navigation Links
    expect(screen.getAllByText('Overview').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('YouTube')).toBeInTheDocument();
    expect(screen.getByText('Moderator')).toBeInTheDocument();
    expect(screen.getAllByText('Channels').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Security')).toBeInTheDocument();
    expect(screen.getByText('System')).toBeInTheDocument();
    expect(screen.getByText('Free Games')).toBeInTheDocument();
    const freeGamesLink = screen.getByText('Free Games').closest('a');
    expect(freeGamesLink).toHaveAttribute('href', '/moderator/freegames');
    expect(screen.getByText(/sign out|logout/i)).toBeInTheDocument();
  });
});
