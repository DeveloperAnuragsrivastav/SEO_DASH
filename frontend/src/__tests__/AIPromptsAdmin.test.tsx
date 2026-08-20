import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import AIPrompts from '../pages/admin/AIPrompts';
import { AuthContext } from '../context/AuthContext';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  }
}));

describe('AIPrompts Admin Component', () => {
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
            <Route path="/clients/:clientId/ai-prompts" element={<AIPrompts />} />
          </Routes>
        </AuthContext.Provider>
      </BrowserRouter>
    );
  };

  it('renders and fetches AI prompts', async () => {
    vi.mocked(api.get).mockImplementation(async (url) => {
      if (url.endsWith('/ai_prompts')) {
        return { data: [{ id: '1', prompt_text: 'Write a meta description', is_active: true, added_at: '2026-08-18' }] };
      }
      return { data: { name: 'Test Client' } };
    });

    window.history.pushState({}, '', '/clients/client-id/ai-prompts');
    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByText('AI Prompts Management')).toBeInTheDocument();
      expect(screen.getByText('Write a meta description')).toBeInTheDocument();
    });
  });

  it('can deactivate an AI prompt', async () => {
    let fetchCount = 0;
    vi.mocked(api.get).mockImplementation(async (url) => {
      if (url.endsWith('/ai_prompts')) {
        fetchCount++;
        return { data: [{ id: '1', prompt_text: 'Write a meta description', is_active: fetchCount === 1, added_at: '2026-08-18' }] };
      }
      return { data: { name: 'Test Client' } };
    });
    vi.mocked(api.put).mockResolvedValueOnce({});

    window.history.pushState({}, '', '/clients/client-id/ai-prompts');
    renderWithAuth();

    const deactivateBtn = await screen.findByText('Deactivate');
    fireEvent.click(deactivateBtn);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/clients/client-id/ai_prompts/1', { is_active: false });
    });
  });
});
