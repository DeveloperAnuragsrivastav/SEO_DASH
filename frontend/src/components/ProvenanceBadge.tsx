import React from 'react';
import { Pencil } from 'lucide-react';

interface ProvenanceBadgeProps {
  label: string;
  isManual: boolean;
}

const ProvenanceBadge: React.FC<ProvenanceBadgeProps> = ({ label, isManual }) => {
  if (isManual) {
    return (
      <div 
        data-testid="provenance-badge"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '5px',
          background: 'var(--amber-soft)',
          color: 'var(--amber)',
          border: '1px dashed var(--amber)',
          padding: '3px 8px',
          borderRadius: '4px',
          fontSize: '11px',
          fontFamily: 'var(--font-mono)',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.04em'
        }}
      >
        <Pencil size={11} data-testid="manual-icon" />
        {label}
      </div>
    );
  }

  return (
    <div 
      data-testid="provenance-badge"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        background: 'var(--line-2)',
        color: 'var(--ink-3)',
        border: '1px solid transparent',
        padding: '3px 8px',
        borderRadius: '4px',
        fontSize: '11px',
        fontFamily: 'var(--font-mono)',
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '0.04em'
      }}
    >
      {label}
    </div>
  );
};

export default ProvenanceBadge;
