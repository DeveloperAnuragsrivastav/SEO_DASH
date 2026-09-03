import React from 'react';

interface PaginationBarProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

const PaginationBar: React.FC<PaginationBarProps> = ({ page, pageSize, total, onPageChange, onPageSizeChange }) => {
  const totalPages = Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px', borderTop: '1px solid var(--border-subtle)', background: 'var(--bg-app)', borderBottomLeftRadius: 'var(--r)', borderBottomRightRadius: 'var(--r)' }}>
      <div className="text-subtle text-sm">
        {total > 0 ? (
          <span>Showing <strong>{start}</strong> to <strong>{end}</strong> of <strong>{total}</strong> entries</span>
        ) : (
          <span>No entries</span>
        )}
      </div>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="text-subtle text-xs">Rows per page:</span>
          <select 
            className="form-input" 
            style={{ padding: '4px 28px 4px 8px', minHeight: 'auto', width: 'auto', fontSize: '13px' }}
            value={pageSize}
            onChange={(e) => {
              onPageSizeChange(Number(e.target.value));
              onPageChange(1);
            }}
          >
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
        
        <div style={{ display: 'flex', gap: '4px' }}>
          <button 
            className="btn btn-secondary btn-sm" 
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            ← Prev
          </button>
          
          <div style={{ display: 'flex', alignItems: 'center', padding: '0 12px', fontSize: '13px', fontWeight: 500 }} className="mono">
            {page} / {Math.max(1, totalPages)}
          </div>
          
          <button 
            className="btn btn-secondary btn-sm" 
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
};

export default PaginationBar;
