import React from 'react';

interface PageSkeletonProps {
  /** Number of skeleton cards to show */
  cards?: number;
  /** Show a header skeleton */
  header?: boolean;
  /** Show stat KPI row */
  stats?: number;
}

const PageSkeleton: React.FC<PageSkeletonProps> = ({ cards = 2, header = true, stats = 0 }) => {
  return (
    <div className="page-skeleton">
      {header && (
        <div className="skeleton-header">
          <div className="skeleton-line skeleton-breadcrumb" />
          <div className="skeleton-line skeleton-title" />
          <div className="skeleton-line skeleton-subtitle" />
        </div>
      )}
      {stats > 0 && (
        <div className="skeleton-stats-row">
          {Array.from({ length: stats }).map((_, i) => (
            <div key={i} className="skeleton-stat-card page-card">
              <div className="skeleton-line" style={{ width: '60%', height: 12, marginBottom: 12 }} />
              <div className="skeleton-line" style={{ width: '40%', height: 28 }} />
            </div>
          ))}
        </div>
      )}
      <div className="skeleton-cards">
        {Array.from({ length: cards }).map((_, i) => (
          <div key={i} className="skeleton-card page-card">
            <div className="skeleton-line" style={{ width: '30%', height: 14, marginBottom: 16 }} />
            <div className="skeleton-line" style={{ width: '100%', height: 12, marginBottom: 10 }} />
            <div className="skeleton-line" style={{ width: '85%', height: 12, marginBottom: 10 }} />
            <div className="skeleton-line" style={{ width: '70%', height: 12 }} />
          </div>
        ))}
      </div>
    </div>
  );
};

export default PageSkeleton;
