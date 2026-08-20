import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SearchPerformance from '../pages/SearchPerformance';
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

describe('SearchPerformance Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderPage = () => {
    return render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/clients/client123/reports/2026-08/search']}>
          <Routes>
            <Route path="/clients/:clientId/reports/:month/search" element={<SearchPerformance />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );
  };

  it('renders table correctly with mock data and tests trend classification logic', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/auth/me')) return Promise.resolve({ data: { id: '1', email: 'test', role: 'agency_admin' } });
      if (url.includes('/search/2026-08')) return Promise.resolve({ 
        data: {
          data: [
            {
              url: '/top-page',
              clicks: 1000,
              impressions: 10000,
              ctr: 0.1,
              position: 2.5,
              categories: ['Top', 'Trending Up'],
              source: 'api'
            },
            {
              url: '/new-page',
              clicks: 50,
              impressions: 500,
              ctr: 0.1,
              position: 10,
              categories: ['New'],
              source: 'api'
            },
            {
              url: '/dropped-page',
              clicks: 100,
              impressions: 2000,
              ctr: 0.05,
              position: 15,
              categories: ['Trending Down'],
              source: 'api'
            }
          ]
        } 
      });
      if (url.includes('/clients/client123')) return Promise.resolve({ data: { name: 'Test Client' } });
      return Promise.reject(new Error('not mocked: ' + url));
    });

    renderPage();

    // Wait for the table to render
    expect(await screen.findByText('/top-page')).toBeInTheDocument();
    expect(screen.getByText('/new-page')).toBeInTheDocument();
    expect(screen.getByText('/dropped-page')).toBeInTheDocument();

    // Verify badges rendered
    expect(screen.getAllByText('Top').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Trending Up').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Trending Down').length).toBeGreaterThan(0);
    expect(screen.getAllByText('New').length).toBeGreaterThan(0);

    // Test Top filter
    fireEvent.click(screen.getByRole('button', { name: 'Top' }));
    await waitFor(() => {
      expect(screen.getByText('/top-page')).toBeInTheDocument();
      expect(screen.queryByText('/new-page')).not.toBeInTheDocument();
      expect(screen.queryByText('/dropped-page')).not.toBeInTheDocument();
    });

    // Test Trending Up filter (Top page is also Trending Up)
    fireEvent.click(screen.getByRole('button', { name: 'Trending Up' }));
    await waitFor(() => {
      expect(screen.getByText('/top-page')).toBeInTheDocument();
      expect(screen.queryByText('/new-page')).not.toBeInTheDocument();
      expect(screen.queryByText('/dropped-page')).not.toBeInTheDocument();
    });

    // Test New filter
    fireEvent.click(screen.getByRole('button', { name: 'New' }));
    await waitFor(() => {
      expect(screen.queryByText('/top-page')).not.toBeInTheDocument();
      expect(screen.getByText('/new-page')).toBeInTheDocument();
    });
  });
});
