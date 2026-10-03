import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Login } from '../pages/Login';
import { authApi } from '../api/auth';

vi.mock('../api/auth', () => ({
  authApi: {
    login: vi.fn(),
    getMe: vi.fn().mockResolvedValue({ authenticated: false }),
  },
}));

describe('Login Page Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('renders login page with credentials form', () => {
    render(
      <MemoryRouter>
        <Login onLoginSuccess={vi.fn()} />
      </MemoryRouter>
    );

    expect(screen.getByText('PB HERO PERSONAL BOT')).toBeInTheDocument();
    expect(screen.getByText(/private.*control panel/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  });

  it('handles successful login and does not store credentials in localStorage', async () => {
    const handleSuccess = vi.fn();
    vi.mocked(authApi.login).mockResolvedValueOnce({
      success: true,
      username: 'admin',
      guild_id: '123456789012345678',
    });

    render(
      <MemoryRouter>
        <Login onLoginSuccess={handleSuccess} />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'secretpass' } });
    fireEvent.click(screen.getByRole('button', { name: /login/i }));

    await waitFor(() => {
      expect(handleSuccess).toHaveBeenCalled();
    });

    // SECURITY VERIFICATION: No passwords or tokens in localStorage
    expect(localStorage.getItem('password')).toBeNull();
    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('bot_token')).toBeNull();
  });

  it('displays invalid credentials message on 401', async () => {
    vi.mocked(authApi.login).mockRejectedValueOnce({
      response: { status: 401, data: { detail: 'Invalid username or password' } },
    });

    render(
      <MemoryRouter>
        <Login onLoginSuccess={vi.fn()} />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrongpass' } });
    fireEvent.click(screen.getByRole('button', { name: /login/i }));

    expect(await screen.findByText(/invalid username or password/i)).toBeInTheDocument();
  });

  it('displays rate limit error on 429', async () => {
    vi.mocked(authApi.login).mockRejectedValueOnce({
      response: { status: 429, data: { detail: 'Too many requests' } },
    });

    render(
      <MemoryRouter>
        <Login onLoginSuccess={vi.fn()} />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'admin' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: /login/i }));

    expect(await screen.findByText(/too many/i)).toBeInTheDocument();
  });
});
