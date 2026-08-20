import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Users from '../pages/admin/Users';
import { AuthContext } from '../context/AuthContext';
import api from '../api/client';

// Mock the API client
vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  }
}));

describe('Users Admin Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderWithAuth = (role: string) => {
    return render(
      <BrowserRouter>
        <AuthContext.Provider value={{
          token: 'test-token',
          user: { id: 'test-id', email: 'test@test.com', role: role as 'agency_admin' | 'agency_staff' },
          login: vi.fn(),
          logout: vi.fn(),
          isLoading: false
        }}>
          <Users />
        </AuthContext.Provider>
      </BrowserRouter>
    );
  };

  it('redirects staff users', () => {
    renderWithAuth('agency_staff');
    // Since Navigate replaces the component, we won't see "User Management"
    expect(screen.queryByText('User Management')).not.toBeInTheDocument();
  });

  it('renders correctly for admin users', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
    renderWithAuth('agency_admin');
    expect(await screen.findByText('User Management')).toBeInTheDocument();
  });

  it('shows users from API', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: [
        { id: '1', email: 'user1@test.com', role: 'agency_staff', is_active: true, last_login_at: null },
        { id: '2', email: 'user2@test.com', role: 'agency_admin', is_active: false, last_login_at: null }
      ]
    });
    renderWithAuth('agency_admin');
    await waitFor(() => {
      expect(screen.getByText('user1@test.com')).toBeInTheDocument();
      expect(screen.getByText('user2@test.com')).toBeInTheDocument();
    });
  });
});
