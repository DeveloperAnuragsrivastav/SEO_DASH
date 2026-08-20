import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import KpiCard from '../components/KpiCard';

describe('KpiCard', () => {
  it('renders title, value, and provenance badge', () => {
    render(
      <KpiCard 
        title="Search Clicks" 
        value="1,200" 
        sourceLabel="GSC · daily" 
        isManual={false} 
      />
    );
    expect(screen.getByText('Search Clicks')).toBeInTheDocument();
    expect(screen.getByText('1,200')).toBeInTheDocument();
    expect(screen.getByTestId('provenance-badge')).toHaveTextContent('GSC · daily');
  });

  it('renders positive delta correctly', () => {
    const { container } = render(
      <KpiCard 
        title="Sessions" 
        value="500" 
        delta={150} 
        sourceLabel="GA4" 
        isManual={false} 
      />
    );
    expect(screen.getByText('150')).toBeInTheDocument();
    // Check that up-soft background is applied
    expect(container.innerHTML).toContain('var(--up-soft)');
  });

  it('renders negative delta correctly', () => {
    const { container } = render(
      <KpiCard 
        title="Clicks" 
        value="100" 
        delta={-20} 
        sourceLabel="GSC" 
        isManual={false} 
      />
    );
    expect(screen.getByText('20')).toBeInTheDocument(); // Absolute value is shown
    // Check that down-soft background is applied
    expect(container.innerHTML).toContain('var(--down-soft)');
  });
});
