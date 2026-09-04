import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api, { API_BASE_URL } from '../../api/client';
import { toast } from 'sonner';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';

const Screenshots: React.FC = () => {
  const { clientId } = useParams();
  const [screenshots, setScreenshots] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    api.get(`/clients/${clientId}/screenshots`, {
      params: { page, page_size: pageSize }
    })
      .then(res => {
        setScreenshots(res.data.items || []);
        setTotal(res.data.total || 0);
      })
      .catch(() => {
        // Handled by global interceptor
      })
      .finally(() => setLoading(false));
  }, [clientId, page, pageSize]);

  if (loading && !screenshots.length) return <PageSkeleton />;

  return (
    <div>
      <PageHeader 
        title="Uploaded Screenshots"
        subtitle="View screenshots uploaded via the Data Ingestion Hub."
      />

      <div className="card">
        <div className="card-header">
          <h2 className="h2">All Screenshots</h2>
        </div>
        {screenshots.length === 0 ? (
          <div style={{ padding: '48px', textAlign: 'center', color: 'var(--ink-3)' }}>
            No screenshots uploaded yet. Use the Data Ingestion Hub to upload.
          </div>
        ) : (
          <div style={{ padding: '24px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '24px' }}>
            {screenshots.map((s) => (
              <div key={s.id} style={{ display: 'flex', flexDirection: 'column', gap: '8px', border: '1px solid var(--border-subtle)', borderRadius: '8px', overflow: 'hidden' }}>
                <a href={`${API_BASE_URL}${s.file_url}`} target="_blank" rel="noreferrer" style={{ display: 'block', height: '150px', background: 'var(--neutral-bg)' }}>
                  <img src={`${API_BASE_URL}${s.file_url}`} alt={s.caption || 'screenshot'} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </a>
                <div style={{ padding: '12px', fontSize: '13px' }}>
                  <div style={{ fontWeight: 600, marginBottom: '4px' }}>{s.month}</div>
                  <div style={{ color: 'var(--ink-2)' }}>{s.caption || 'No caption'}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {screenshots.length > 0 && (
        <PaginationBar 
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      )}
    </div>
  );
};

export default Screenshots;
