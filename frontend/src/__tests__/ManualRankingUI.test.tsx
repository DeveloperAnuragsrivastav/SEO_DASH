import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ManualRankingUI from '../components/ManualRankingUI';
import api from '../api/client';

vi.mock('../api/client', () => {
  return {
    default: {
      post: vi.fn(),
    }
  };
});

describe('ManualRankingUI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows specific per-row errors from a mocked malformed-row API response', async () => {
    const mockOnSuccess = vi.fn();
    render(<ManualRankingUI clientId="client123" onSuccess={mockOnSuccess} />);

    // Mock file upload
    const file = new File(['keyword,position,date,url\nmissing_date,1,,'], 'test.csv', { type: 'text/csv' });
    const input = screen.getByTestId('csv-input');
    fireEvent.change(input, { target: { files: [file] } });

    (api.post as any).mockResolvedValueOnce({
      data: {
        status: 'error',
        rows_inserted: 0,
        errors: [{ row: 2, error: 'Missing keyword or date' }]
      }
    });

    const submitBtn = screen.getByTestId('csv-submit');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByTestId('upload-errors')).toBeInTheDocument();
      expect(screen.getByText('Row 2: Missing keyword or date')).toBeInTheDocument();
    });
  });

  it('validates and submits manual single-keyword form', async () => {
    const mockOnSuccess = vi.fn();
    render(<ManualRankingUI clientId="client123" onSuccess={mockOnSuccess} />);

    (api.post as any).mockResolvedValueOnce({ data: { status: 'success' } });

    const kwInput = screen.getByTestId('kw-input');
    const posInput = screen.getByTestId('pos-input');
    
    fireEvent.change(kwInput, { target: { value: 'uuid-123' } });
    fireEvent.change(posInput, { target: { value: '5' } });

    const form = screen.getByTestId('manual-form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/clients/client123/rankings/manual', expect.objectContaining({
        keyword_id: 'uuid-123',
        position: 5
      }));
      expect(screen.getByText('Saved!')).toBeInTheDocument();
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });
});
