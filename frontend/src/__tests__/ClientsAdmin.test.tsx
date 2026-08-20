import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Clients from '../pages/admin/Clients';
import { AuthProvider } from '../context/AuthContext';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}));

const mockClients = [
  { id: '1', name: 'Client A', domain: 'a.com', business_type: 'saas', status: 'active' },
  { id: '2', name: 'Client B', domain: 'b.com', business_type: 'local', status: 'paused' }
];

describe('Clients Admin Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockResolvedValue({ data: mockClients });
  });

  const renderWithRole = (role: string) => {
    // Mock localStorage for role if needed, or mock useAuth instead
    // But since useAuth fetches /auth/me, we can mock that
    (api.get as any).mockImplementation((url: string) => {
      if (url === '/auth/me') return Promise.resolve({ data: { id: 'user1', email: 'u@u.com', role } });
      if (url === '/clients') return Promise.resolve({ data: mockClients });
      return Promise.reject(new Error('not found'));
    });
    // Set dummy token to trigger fetchUser
    localStorage.setItem('token', 'dummy');

    return render(
      <AuthProvider>
        <MemoryRouter>
          <Clients />
        </MemoryRouter>
      </AuthProvider>
    );
  };

  it('renders list of clients', async () => {
    renderWithRole('agency_admin');
    await waitFor(() => {
      expect(screen.getByText('Client A')).toBeInTheDocument();
      expect(screen.getByText('Client B')).toBeInTheDocument();
    });
  });

  it('hides Add/Edit controls for agency_staff', async () => {
    renderWithRole('agency_staff');
    await waitFor(() => {
      expect(screen.getByText('Client A')).toBeInTheDocument();
    });
    
    expect(screen.queryByText('Add Client')).not.toBeInTheDocument();
    expect(screen.queryByText('Edit')).not.toBeInTheDocument();
  });

  it('shows Add/Edit controls for agency_admin', async () => {
    renderWithRole('agency_admin');
    await waitFor(() => {
      expect(screen.getByText('Client A')).toBeInTheDocument();
    });
    
    expect(screen.getByText('Add Client')).toBeInTheDocument();
    expect(screen.getAllByText('Edit').length).toBeGreaterThan(0);
  });
});
