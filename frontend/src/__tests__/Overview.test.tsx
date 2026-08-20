import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Overview from '../pages/Overview';
import { AuthProvider } from '../context/AuthContext';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

vi.mock('axios', () => {
  return {
    default: {
      create: vi.fn(() => ({
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() },
        },
        get: vi.fn(),
        post: vi.fn(),
        put: vi.fn(),
      })),
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
    },
  };
});

import api from '../api/client';
vi.mock('../api/client', () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
    }
  };
});

describe('Overview Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderOverview = () => {
    return render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/clients/client123/reports/2026-08/overview']}>
          <Routes>
            <Route path="/clients/:clientId/reports/:month/overview" element={<Overview />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );
  };

  it('renders empty state and allows generation', async () => {
    // Auth context mock
    (api.get as any).mockImplementation((url: string) => {
      if (url === '/auth/me') return Promise.resolve({ data: { id: '1', email: 'test', role: 'agency_admin' } });
      if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });
      if (url === '/clients/client123/reports/2026-08') return Promise.reject({ response: { status: 404 } });
      return Promise.reject(new Error('not mocked'));
    });

    renderOverview();
    
    expect(await screen.findByText('No Report Generated')).toBeInTheDocument();
    
    // Click Generate
    (api.post as any).mockResolvedValueOnce({ data: { status: 'success' } });
    // After generation, it re-fetches the report
    (api.get as any).mockImplementation((url: string) => {
      if (url === '/auth/me') return Promise.resolve({ data: { id: '1', email: 'test', role: 'agency_admin' } });
      if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });
      if (url === '/clients/client123/reports/2026-08') return Promise.resolve({ data: { snapshot: {}, narrative: 'Generated narrative' } });
      return Promise.reject(new Error('not mocked'));
    });

    fireEvent.click(screen.getByRole('button', { name: 'Generate Report' }));

    await waitFor(() => {
      expect(screen.getByText('Performance snapshot for 2026-08')).toBeInTheDocument();
      expect(screen.getByText('Generated narrative')).toBeInTheDocument();
    });
  });

  it('renders correctly with real mock data', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url === '/auth/me') return Promise.resolve({ data: { id: '1', email: 'test', role: 'agency_admin' } });
      if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });
      if (url === '/clients/client123/reports/2026-08') return Promise.resolve({ 
        data: { 
          snapshot: {
            gsc: { clicks: 120 },
            ga4: { sessions: 1000 },
            rankings: { summary: { improved: 2, top_10: 1, '11_20': 1, '21_50': 1, '51_plus': 0 } },
            kpi_deltas: { gsc: { clicks: 40 }, ga4: { sessions: 150 } },
            ai_visibility: [{ mentioned: true }],
            sources: { gsc: 'manual', ga4: 'api', rankings: 'api' }
          }, 
          narrative: 'Executive summary text.' 
        } 
      });
      return Promise.reject(new Error('not mocked'));
    });

    renderOverview();

    // Check KPI cards
    expect(await screen.findByText('Search Clicks')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument(); // GSC clicks

    expect(screen.getByText('Website Sessions')).toBeInTheDocument();
    expect(screen.getByText('1,000')).toBeInTheDocument(); // GA4 sessions

    expect(screen.getByText('Rankings Improved')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();

    expect(screen.getByText('AI Mentions')).toBeInTheDocument();
    expect(screen.getAllByText('1').length).toBeGreaterThan(0);

    // Check Narrative
    expect(screen.getByText('Executive summary text.')).toBeInTheDocument();

    // Check Manual Provenance Badge for GSC
    const manualBadge = screen.getByText('Agency: Manual Entry');
    expect(manualBadge).toBeInTheDocument();
  });
});
