import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Connections from '../pages/admin/Connections';
import { AuthProvider } from '../context/AuthContext';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}));

const mockConnections = [
  { id: '1', client_id: 'c1', provider: 'gsc', property_id: 'sc-domain:test.com', status: 'not_connected', access_mode: 'platform_shared' },
];

describe('Connections Admin Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderWithRole = (role: string) => {
    (api.get as any).mockImplementation((url: string) => {
      if (url === '/auth/me') return Promise.resolve({ data: { id: 'user1', email: 'u@u.com', role } });
      if (url === '/clients/c1') return Promise.resolve({ data: { name: 'Test Client' } });
      if (url === '/clients/c1/connections') return Promise.resolve({ data: mockConnections });
      return Promise.reject(new Error('not found'));
    });
    localStorage.setItem('token', 'dummy');

    return render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/admin/clients/c1/connections']}>
          <Routes>
            <Route path="/admin/clients/:clientId/connections" element={<Connections />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );
  };

  it('renders connections', async () => {
    renderWithRole('agency_admin');
    await waitFor(() => {
      expect(screen.getByText('sc-domain:test.com')).toBeInTheDocument();
    });
  });

  it('hides controls for agency_staff', async () => {
    renderWithRole('agency_staff');
    await waitFor(() => {
      expect(screen.getByText('sc-domain:test.com')).toBeInTheDocument();
    });
    
    expect(screen.queryByText('Add Connection')).not.toBeInTheDocument();
    expect(screen.queryByText('Verify')).not.toBeInTheDocument();
  });

  it('shows controls for agency_admin and handles verification success', async () => {
    (api.post as any).mockResolvedValue({ data: { status: 'connected' } });

    renderWithRole('agency_admin');
    await waitFor(() => {
      expect(screen.getByText('sc-domain:test.com')).toBeInTheDocument();
    });
    
    const verifyBtn = screen.getByText('Verify');
    fireEvent.click(verifyBtn);
    
    await waitFor(() => {
      expect(screen.getByText('Connection verified successfully.')).toBeInTheDocument();
    });
    expect(api.post).toHaveBeenCalledWith('/connections/1/verify');
  });

  it('handles verification failure', async () => {
    (api.post as any).mockRejectedValue({ response: { data: { detail: "Google Service Account credentials not found." } } });

    renderWithRole('agency_admin');
    await waitFor(() => {
      expect(screen.getByText('sc-domain:test.com')).toBeInTheDocument();
    });
    
    const verifyBtn = screen.getByText('Verify');
    fireEvent.click(verifyBtn);
    
    await waitFor(() => {
      expect(screen.getByText('Google Service Account credentials not found.')).toBeInTheDocument();
    });
  });
});
