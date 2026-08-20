import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AIVisibility from '../pages/AIVisibility';
import api from '../api/client';

// Mock the API client
vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe('AIVisibility Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    (api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockImplementation(() => new Promise(() => {}));
    
    render(
      <MemoryRouter initialEntries={['/clients/123/reports/2026-08/ai-visibility']}>
        <Routes>
          <Route path="/clients/:clientId/reports/:monthStr/ai-visibility" element={<AIVisibility />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText(/Loading AI Visibility/i)).toBeInTheDocument();
  });

  it('renders ai visibility data correctly', async () => {
    const mockData = {
      section1: {
        total_tracked_prompts: 15,
        platforms: {
          chatgpt: { mentions: 10 },
          claude: { mentions: 5 },
          gemini: { mentions: 2 },
          perplexity: { mentions: 8 }
        },
        cited_pages: [
          { url: 'https://example.com/blog/seo', mentions: 7 },
          { url: 'https://example.com/about', mentions: 3 }
        ]
      },
      section2: {
        total_ai_overview_keywords: 2,
        keywords: [
          { keyword_id: 'kw-1', term: 'best seo tools', position: 1 },
          { keyword_id: 'kw-2', term: 'seo agency', position: 3 }
        ]
      }
    };

    (api.get as any).mockResolvedValueOnce({ data: { name: 'Test Client' } }).mockResolvedValueOnce({ data: mockData });

    render(
      <MemoryRouter initialEntries={['/clients/123/reports/2026-08/ai-visibility']}>
        <Routes>
          <Route path="/clients/:clientId/reports/:monthStr/ai-visibility" element={<AIVisibility />} />
        </Routes>
      </MemoryRouter>
    );

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText(/LLM Brand Mentions/i)).toBeInTheDocument();
    });

    // Check Section 1
    expect(screen.getByText(/15 tracked prompts/i)).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument(); // ChatGPT mentions
    expect(screen.getByText('5')).toBeInTheDocument(); // Claude
    expect(screen.getByText('2')).toBeInTheDocument(); // Gemini
    expect(screen.getByText('8')).toBeInTheDocument(); // Perplexity
    expect(screen.getByText('https://example.com/blog/seo')).toBeInTheDocument();
    expect(screen.getByText('https://example.com/about')).toBeInTheDocument();

    // Check Section 2
    expect(screen.getByText(/2 keywords triggered AI Overviews/i)).toBeInTheDocument();
    expect(screen.getByText('best seo tools')).toBeInTheDocument();
    expect(screen.getByText('seo agency')).toBeInTheDocument();
  });
});
