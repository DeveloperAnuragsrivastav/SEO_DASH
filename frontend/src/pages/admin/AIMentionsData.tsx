import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../../api/client';

import * as XLSX from 'xlsx';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';

const AIMentionsData: React.FC = () => {
  const { clientId } = useParams();
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (clientId) {
      setLoading(true);
      api.get(`/clients/${clientId}/ai_mentions`, {
        params: { page, page_size: pageSize }
      })
        .then(res => {
          setRecords(res.data.items || []);
          setTotal(res.data.total || 0);
        })
        .catch(() => {
          // Handled by global interceptor
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [clientId, page, pageSize]);

  const exportToExcel = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/ai_mentions`, {
        params: { page: 1, page_size: 100000 }
      });
      const ws = XLSX.utils.json_to_sheet(data.items);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "AI Mentions");
      XLSX.writeFile(wb, `AI_Mentions_${clientId}.xlsx`);
    } catch (err) {
      // Handled by global interceptor
    }
  };

  if (loading && !records.length) return <PageSkeleton />;

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <button className="btn btn-secondary" style={{ fontSize: '12px', padding: '4px 8px', border: 'none', background: 'transparent' }} onClick={() => window.history.back()}>
          ← Back
        </button>
      </div>
      <PageHeader 
        title="Target AI Prompts Tracking & Performance"
        subtitle="View and export manually uploaded AI Mentions data."
        actions={
          <button className="btn btn-secondary" onClick={exportToExcel} disabled={records.length === 0}>
            Download Excel
          </button>
        }
      />

      <div className="card">
        <div className="card-header">
          <h3 className="h2">Uploaded Records</h3>
        </div>
        
        {records.length === 0 ? (
          <div style={{ padding: '64px', textAlign: 'center', color: 'var(--text-subtle)' }}>
            No manual records found. Upload data via Data Ingestion Hub.
          </div>
        ) : (
          <div className="table-wrapper" style={{ overflowX: 'auto', borderTop: '1px solid var(--border-subtle)' }}>
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Platform</th>
                  <th>Prompt</th>
                  <th>Mentioned</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, i) => {
                  let monthDisplay = r.captured_on;
                  if (r.captured_on) {
                    const parts = r.captured_on.split('-');
                    if (parts.length === 3) {
                      const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
                      monthDisplay = `${d.toLocaleString('default', { month: 'long' })}'${parts[0].slice(2)}`;
                    }
                  }
                  return (
                  <tr key={i}>
                    <td style={{ fontWeight: 500, textTransform: 'capitalize' }}>{monthDisplay}</td>
                    <td>{r.platform || '-'}</td>
                    <td>{r.prompt || '-'}</td>
                    <td>{r.mentioned ? 'Yes' : 'No'}</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      
      {records.length > 0 && (
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

export default AIMentionsData;
