import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Audience from '../pages/Audience';
import { AuthProvider } from '../context/AuthContext';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import api from '../api/client';

vi.mock('../api/client', () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
    }
  };
});

describe('Audience Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderPage = () => {
    return render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/clients/client123/reports/2026-08/audience']}>
          <Routes>
            <Route path="/clients/:clientId/reports/:month/audience" element={<Audience />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );
  };

  it('renders all three breakdown tables correctly with mock data', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url === '/auth/me') return Promise.resolve({ data: { id: '1', email: 'test', role: 'agency_admin' } });
      if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });
      if (url === '/clients/client123/audience/2026-08') return Promise.resolve({ 
        data: {
          data: {
            channel: [{ dimension: 'Organic Search', sessions: 500, users: 400, engaged_sessions: 300, conversions: 10, revenue: 0, source: 'api' }],
            device: [{ dimension: 'Mobile', sessions: 300, users: 200, engaged_sessions: 150, conversions: 5, revenue: 0, source: 'api' }],
            country: [{ dimension: 'United States', sessions: 450, users: 350, engaged_sessions: 250, conversions: 8, revenue: 0, source: 'api' }]
          }
        } 
      });
      return Promise.reject(new Error('not mocked'));
    });

    renderPage();

    expect(await screen.findByText('Organic Search')).toBeInTheDocument();
    expect(screen.getByText('Mobile')).toBeInTheDocument();
    expect(screen.getByText('United States')).toBeInTheDocument();

    // Verify volumes rendered properly
    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getByText('400')).toBeInTheDocument();

    // Tables headers
    expect(screen.getAllByText('Acquisition Channels').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Device Categories').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Top Countries').length).toBeGreaterThan(0);
  });
});
