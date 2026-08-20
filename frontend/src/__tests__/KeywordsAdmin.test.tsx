import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Keywords from '../pages/admin/Keywords';
import { AuthContext } from '../context/AuthContext';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  }
}));

describe('Keywords Admin Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderWithAuth = () => {
    return render(
      <BrowserRouter>
        <AuthContext.Provider value={{
          token: 'fake-token',
          user: { id: '1', email: 'admin@test.com', role: 'agency_admin' },
          login: vi.fn(),
          logout: vi.fn(),
          isLoading: false,
        }}>
          <Routes>
            <Route path="/clients/:clientId/keywords" element={<Keywords />} />
          </Routes>
        </AuthContext.Provider>
      </BrowserRouter>
    );
  };

  it('renders and fetches keywords', async () => {
    vi.mocked(api.get).mockImplementation(async (url) => {
      if (url.endsWith('/keywords')) {
        return { data: [{ id: '1', term: 'seo agency', search_volume: 1000, is_active: true, added_at: '2026-08-18' }] };
      }
      return { data: { name: 'Test Client' } };
    });

    window.history.pushState({}, '', '/clients/client-id/keywords');
    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByText('Keyword Management')).toBeInTheDocument();
      expect(screen.getByText('seo agency')).toBeInTheDocument();
      expect(screen.getByText('1,000')).toBeInTheDocument();
    });
  });

  it('can deactivate a keyword', async () => {
    let fetchCount = 0;
    vi.mocked(api.get).mockImplementation(async (url) => {
      if (url.endsWith('/keywords')) {
        fetchCount++;
        return { data: [{ id: '1', term: 'seo agency', search_volume: 1000, is_active: fetchCount === 1, added_at: '2026-08-18' }] };
      }
      return { data: { name: 'Test Client' } };
    });
    vi.mocked(api.put).mockResolvedValueOnce({});

    window.history.pushState({}, '', '/clients/client-id/keywords');
    renderWithAuth();

    const deactivateBtn = await screen.findByText('Deactivate');
    fireEvent.click(deactivateBtn);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/clients/client-id/keywords/1?is_active=false');
    });
  });
});
