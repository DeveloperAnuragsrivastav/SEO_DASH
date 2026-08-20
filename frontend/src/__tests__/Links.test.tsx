import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Links from '../pages/Links';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  }
}));

describe('Links Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter initialEntries={['/clients/123/reports/2026-08/links']}>
        <Routes>
          <Route path="/clients/:clientId/reports/:month/links" element={<Links />} />
        </Routes>
      </MemoryRouter>
    );
  };

  it('renders loading state and then data correctly', async () => {
    const mockData = {
      kpis: {
        total_links: 5,
        unique_domains: 4,
        activity_breakdown: { "Guest Post": 3, "Niche Edit": 2 }
      },
      links: [
        {
          id: '1',
          domain: 'example.com',
          url: 'https://example.com/post',
          activity_type: 'Guest Post',
          status: 'active',
          dr: 45,
          last_checked: '2026-08-15T00:00:00Z',
          created_on: '2026-08-01'
        }
      ]
    };
    (api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: mockData });

    renderComponent();

    expect(screen.getByText('Loading links…')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Links Built')).toBeInTheDocument();
    });

    expect(screen.getByText('5')).toBeInTheDocument(); // Total Links
    expect(screen.getByText('4')).toBeInTheDocument(); // Unique Domains
    expect(screen.getByText('example.com')).toBeInTheDocument();
    expect(screen.getAllByText('Guest Post').length).toBeGreaterThan(0);
  });

  it('allows adding a new link', async () => {
    (api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: { kpis: { total_links: 0, unique_domains: 0, activity_breakdown: {} }, links: [] } });
    (api.post as any).mockResolvedValueOnce({ data: { id: '2' } });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Links Built')).toBeInTheDocument();
    });

    expect(screen.getByText('Add Manual Link')).toBeInTheDocument();

    // The fields in ManualEntryCard are labeled by their title
    fireEvent.change(screen.getByLabelText('Domain (e.g. forbes.com)'), { target: { value: 'forbes.com' } });
    fireEvent.change(screen.getByLabelText('URL'), { target: { value: 'https://forbes.com/article' } });
    fireEvent.change(screen.getByLabelText('Activity Type (e.g. Guest Post)'), { target: { value: 'Guest Post' } });

    fireEvent.click(screen.getByText('Save Link'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/clients/123/links', expect.objectContaining({
        domain: 'forbes.com',
        url: 'https://forbes.com/article',
        activity_type: 'Guest Post'
      }));
    });
  });
});
