import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Rankings from '../pages/Rankings';
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

describe('Rankings Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderPage = () => {
    return render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/clients/client123/reports/2026-08/rankings']}>
          <Routes>
            <Route path="/clients/:clientId/reports/:month/rankings" element={<Rankings />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );
  };

  const mockData = [
    {
      keyword_id: 'kw-1',
      term: 'seo services',
      group_tag: null,
      current_position: 2,
      previous_position: 5,
      best_position: 1,
      change: 3,
      history: [
        { date: '2026-05-01', position: 15 },
        { date: '2026-06-01', position: 5 },
        { date: '2026-07-01', position: 2 }
      ],
      source: 'api',
      screenshot: 'https://example.com/ss1.png'
    },
    {
      keyword_id: 'kw-2',
      term: 'marketing agency',
      group_tag: null,
      current_position: 12,
      previous_position: 10,
      best_position: 8,
      change: -2,
      history: [
        { date: '2026-05-01', position: 8 },
        { date: '2026-06-01', position: 10 },
        { date: '2026-07-01', position: 12 }
      ],
      source: 'manual'
    }
  ];

  it('renders rows with correct position-band coloring and provenance', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url === '/auth/me') return Promise.resolve({ data: { id: '1', email: 'test', role: 'agency_admin' } });
      if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });
      if (url === '/clients/client123/rankings/2026-08') return Promise.resolve({ data: { data: mockData } });
      return Promise.reject(new Error('not mocked'));
    });

    renderPage();

    expect(await screen.findByText('seo services')).toBeInTheDocument();
    
    // Check row 1
    const row1 = screen.getByText('seo services').closest('tr');
    expect(row1).toBeInTheDocument();
    
    // Check row 2
    expect(screen.getByText('marketing agency')).toBeInTheDocument();

    // Check provenance
    expect(screen.getByText('DataForSEO')).toBeInTheDocument();
    expect(screen.getByText('Manual Entry')).toBeInTheDocument();
  });

  it('filters rows correctly via chips', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url === '/auth/me') return Promise.resolve({ data: { id: '1', email: 'test', role: 'agency_admin' } });
      if (url === '/clients/client123') return Promise.resolve({ data: { name: 'Test Client' } });
      if (url === '/clients/client123/rankings/2026-08') return Promise.resolve({ data: { data: mockData } });
      return Promise.reject(new Error('not mocked'));
    });

    renderPage();

    expect(await screen.findByText('seo services')).toBeInTheDocument();

    const improvedFilter = screen.getByText('Improved');
    fireEvent.click(improvedFilter);

    await waitFor(() => {
      expect(screen.getByText('seo services')).toBeInTheDocument();
      expect(screen.queryByText('marketing agency')).not.toBeInTheDocument();
    });
  });
});
