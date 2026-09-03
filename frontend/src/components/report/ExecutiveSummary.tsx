import React from 'react';

interface ExecutiveSummaryProps {
  narrative?: string;
  monthLabel: string;
  status: string;
  publishedAt?: string;
}

const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({ narrative, monthLabel, status, publishedAt }) => {
  if (!narrative) return null;

  return (
    <section id="executive-summary" className="report-section">
      <div className="head">
        <div>
          <div className="eyebrow">Executive Summary</div>
          <h2>{monthLabel} Insights</h2>
        </div>
        <span className="spacer" />
        <span className="src">
          {status === 'published' 
            ? `Published ${publishedAt ? new Date(publishedAt).toLocaleDateString() : ''}` 
            : 'Draft'}
        </span>
      </div>
      
      <div className="note" style={{ borderLeftColor: 'var(--brand)' }}>
        <p>{narrative}</p>
      </div>
    </section>
  );
};

export default ExecutiveSummary;
