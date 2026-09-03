import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../../api/client';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';

interface KeywordHistory {
  id: string;
  keyword: string;
  search_volume?: number;
  initial_rank?: number;
  history: Record<string, number>;
}

const Keywords: React.FC = () => {
  const { clientId } = useParams<{ clientId: string }>();
  const [keywords, setKeywords] = useState<KeywordHistory[]>([]);
  const [months, setMonths] = useState<string[]>([]);
  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);

  const fetchKeywords = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/keywords/history`, {
        params: { page, page_size: pageSize }
      });
      setKeywords(data.items);
      setTotal(data.total);

      // Extract all unique months across all keywords in current view
      const allMonths = new Set<string>();
      data.items.forEach((k: KeywordHistory) => {
        Object.keys(k.history || {}).forEach(m => allMonths.add(m));
      });
      // Sort months descending (newest first)
      setMonths(Array.from(allMonths).sort().reverse());
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to fetch keywords');
    }
  };

  const fetchClient = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}`);
      setClient(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchClient();
  }, [clientId]);

  useEffect(() => {
    setLoading(true);
    fetchKeywords().finally(() => setLoading(false));
  }, [clientId, page, pageSize]);

  if (loading && !keywords.length) return <PageSkeleton />;

  const exportExcel = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/keywords/history`, {
        params: { page: 1, page_size: 100000 }
      });
      const ws = XLSX.utils.json_to_sheet(data.items);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Keywords");
      XLSX.writeFile(wb, `Keywords_${clientId}.xlsx`);
    } catch (err) {
      toast.error('Failed to export data');
    }
  };

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Link to={`/admin/clients/${clientId}`} style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-tertiary)', textDecoration: 'none' }}>← Back to {client?.name}</Link>
      </div>
      <PageHeader
        title="Keyword Performance"
        subtitle="Track and manage target keywords for this client."
        actions={
          <button className="btn btn-secondary" onClick={exportExcel} disabled={keywords.length === 0}>
            Download Excel
          </button>
        }
      />

      <div className="card table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Keyword</th>
              <th className="num">SV</th>
              <th className="num">Initial Rank</th>
              {months.map(m => (
                <th key={m} className="num">{m}</th>
              ))}
              <th className="num">Change</th>
            </tr>
          </thead>
          <tbody>
            {keywords.map(kw => {
              const initial = kw.initial_rank || 0;
              // Latest month is the first one in the sorted `months` array
              const latestRank = months.length > 0 ? (kw.history[months[0]] || initial) : initial;
              const change = initial && latestRank ? initial - latestRank : 0;

              return (
                <tr key={kw.id}>
                  <td style={{ fontWeight: 500 }}>
                    {kw.keyword}
                  </td>
                  <td className="num">{kw.search_volume ? kw.search_volume.toLocaleString() : '-'}</td>
                  <td className="num">{kw.initial_rank || '-'}</td>
                  {months.map(m => (
                    <td key={m} className="num">{kw.history[m] || '-'}</td>
                  ))}
                  <td className="num">
                    <div className={`badge ${change > 0 ? 'badge-success' : change < 0 ? 'badge-error' : 'badge-neutral'}`} style={{ display: 'inline-flex', width: 'auto' }}>
                      {change > 0 ? `+${change}` : change}
                    </div>
                  </td>
                </tr>
              );
            })}
            {keywords.length === 0 && (
              <tr>
                <td colSpan={4 + months.length} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-subtle)' }}>
                  No active keywords found. Add them via Data Ingestion Hub.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <PaginationBar
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
      />
    </>
  );
};

export default Keywords;
