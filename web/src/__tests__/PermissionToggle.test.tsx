import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PermissionToggle } from '../components/PermissionToggle';

describe('PermissionToggle Component', () => {
  it('renders with label and description', () => {
    const handleChange = vi.fn();
    render(
      <PermissionToggle
        label="Embed Links"
        description="Allow posting hyperlinks with rich embeds"
        value="inherit"
        onChange={handleChange}
      />
    );

    expect(screen.getByText('Embed Links')).toBeInTheDocument();
    expect(screen.getByText('Allow posting hyperlinks with rich embeds')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /inherit/i })).toBeInTheDocument();
  });

  it('correctly displays and triggers ALLOW, DENY, and INHERIT states', () => {
    const handleChange = vi.fn();
    const { rerender } = render(
      <PermissionToggle
        label="Attach Files"
        value="inherit"
        onChange={handleChange}
      />
    );

    // INHERIT button should have active amber class
    const inheritBtn = screen.getByRole('button', { name: /inherit/i });
    expect(inheritBtn).toHaveClass('text-amber-400');

    // Click ALLOW
    const allowBtn = screen.getByRole('button', { name: /allow/i });
    fireEvent.click(allowBtn);
    expect(handleChange).toHaveBeenCalledWith('allow');

    // Re-render as ALLOW
    rerender(
      <PermissionToggle
        label="Attach Files"
        value="allow"
        onChange={handleChange}
      />
    );
    expect(screen.getByRole('button', { name: /allow/i })).toHaveClass('text-emerald-400');

    // Click DENY
    const denyBtn = screen.getByRole('button', { name: /deny/i });
    fireEvent.click(denyBtn);
    expect(handleChange).toHaveBeenCalledWith('deny');
  });

  it('disables buttons when disabled prop is true', () => {
    const handleChange = vi.fn();
    render(
      <PermissionToggle
        label="Manage Messages"
        value="deny"
        disabled={true}
        onChange={handleChange}
      />
    );

    const allowBtn = screen.getByRole('button', { name: /allow/i });
    const denyBtn = screen.getByRole('button', { name: /deny/i });
    const inheritBtn = screen.getByRole('button', { name: /inherit/i });

    expect(allowBtn).toBeDisabled();
    expect(denyBtn).toBeDisabled();
    expect(inheritBtn).toBeDisabled();

    fireEvent.click(allowBtn);
    expect(handleChange).not.toHaveBeenCalled();
  });
});
