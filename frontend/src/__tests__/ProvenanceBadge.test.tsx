import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ProvenanceBadge from '../components/ProvenanceBadge';

describe('ProvenanceBadge', () => {
  it('renders correctly for automated source', () => {
    render(<ProvenanceBadge label="GSC · daily" isManual={false} />);
    const badge = screen.getByTestId('provenance-badge');
    expect(badge).toHaveTextContent('GSC · daily');
    expect(badge).toHaveStyle({
      background: 'var(--line-2)',
      color: 'var(--ink-3)'
    });
    expect(screen.queryByTestId('manual-icon')).not.toBeInTheDocument();
  });

  it('renders correctly for manual source including non-color icon', () => {
    render(<ProvenanceBadge label="Agency: Manual Entry" isManual={true} />);
    const badge = screen.getByTestId('provenance-badge');
    expect(badge).toHaveTextContent('Agency: Manual Entry');
    expect(badge).toHaveStyle({
      background: 'var(--amber-soft)',
      color: 'var(--amber)'
    });
    // jsdom has trouble with shorthand border and css vars, verify it manually
    expect(badge.style.border).toContain('dashed');
    expect(badge.style.border).toContain('var(--amber)');
    // Explicitly verify the presence of the non-color distinguishing element
    expect(screen.getByTestId('manual-icon')).toBeInTheDocument();
  });
});
