import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import WorkDone from '../pages/WorkDone';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    defaults: { baseURL: 'http://localhost:8000/api' }
  }
}));

describe('WorkDone Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter initialEntries={['/clients/123/reports/2026-08/work']}>
        <Routes>
          <Route path="/clients/:clientId/reports/:month/work" element={<WorkDone />} />
        </Routes>
      </MemoryRouter>
    );
  };

  it('renders data correctly', async () => {
    const mockData = {
      activities: [
        { id: '1', month: '2026-08-01', activity_type: 'On-Page Optimization', count: 5, notes: 'Homepage' }
      ],
      screenshots: [
        { id: '2', month: '2026-08-01', keyword_id: null, file_url: '/static/test.png', caption: 'Test screenshot' }
      ],
      next_month_plan: { text: 'Focus on local SEO.' }
    };
    (api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: mockData });

    renderComponent();

    expect(screen.getByText('Loading work done…')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Work Done & Execution')).toBeInTheDocument();
    });

    // Check Plan
    expect(screen.getByText('Focus on local SEO.')).toBeInTheDocument();

    // Check Activities
    expect(screen.getByText('On-Page Optimization')).toBeInTheDocument();

    // Check Screenshots
    expect(screen.getByText('Test screenshot')).toBeInTheDocument();
  });

  it('allows adding an activity', async () => {
    (api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: { activities: [], screenshots: [], next_month_plan: null } });
    (api.post as any).mockResolvedValueOnce({ data: { id: '3' } });

    vi.spyOn(window, 'prompt').mockImplementation((msg) => {
      if (msg.includes('type')) return 'New Content';
      if (msg.includes('How many')) return '2';
      if (msg.includes('Notes')) return 'Test notes';
      return '';
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Work Done & Execution')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Add Activity'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/clients/123/work/activities', expect.objectContaining({
        activity_type: 'New Content',
        count: 2,
        notes: 'Test notes'
      }));
    });
  });
  
  it('allows editing the plan', async () => {
    (api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: { activities: [], screenshots: [], next_month_plan: null } });
    (api.put as any).mockResolvedValueOnce({ data: { status: 'success' } });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Work Done & Execution')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Edit Plan'));

    const textarea = screen.getByPlaceholderText(/Enter next month's focus/);
    fireEvent.change(textarea, { target: { value: 'Test plan update' } });

    fireEvent.click(screen.getByText('Save Plan'));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/clients/123/work/2026-08/plan', expect.objectContaining({
        next_month_plan: { text: 'Test plan update' }
      }));
    });
  });
});
