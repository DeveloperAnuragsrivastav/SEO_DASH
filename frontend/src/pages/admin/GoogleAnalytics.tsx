import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../../api/client';

import * as XLSX from 'xlsx';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';
import { TrendingUp } from 'lucide-react';

const GoogleAnalytics: React.FC = () => {
  const { clientId } = useParams();
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);

  const fetchRecords = async () => {
    try {
      const res = await api.get(`/clients/${clientId}/audience/history`, {
        params: { page, page_size: pageSize }
      });
      setRecords(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      // Handled by global interceptor
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchRecords();
  }, [clientId, page, pageSize]);

  const exportExcel = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/audience/history`, {
        params: { page: 1, page_size: 100000 }
      });
      const ws = XLSX.utils.json_to_sheet(data.items);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Google Analytics");
      XLSX.writeFile(wb, `GA4_Data_${clientId}.xlsx`);
    } catch (err) {
      // Handled by global interceptor
    }
  };

  if (loading && !records.length) return <PageSkeleton />;

  return (
    <>
      <PageHeader 
        title="Google Analytics (GA4)"
        subtitle="View Google Analytics traffic data over time."
        actions={
          <button className="btn btn-secondary" onClick={exportExcel} disabled={records.length === 0}>
            Download Excel
          </button>
        }
      />

      {records.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <span className="empty-state-icon"><TrendingUp size={22} /></span>
            <h3>No Analytics data</h3>
            <p>Connect a GA4 property, or upload a spreadsheet from the Data Ingestion Hub.</p>
          </div>
        </div>
      ) : (
        <div className="card table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Dimension</th>
                <th>Value</th>
                <th className="num">Sessions</th>
                <th className="num">Users</th>
                <th className="num">Engaged Sessions</th>
                <th className="num">Conversions</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r, i) => (
                <tr key={i}>
                  <td>{r.captured_on}</td>
                  <td style={{ textTransform: 'capitalize' }}>{r.dimension_key}</td>
                  <td>{r.dimension_value}</td>
                  <td className="num">{r.sessions}</td>
                  <td className="num">{r.users}</td>
                  <td className="num">{r.engaged_sessions}</td>
                  <td className="num">{r.conversions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      
      {records.length > 0 && (
        <PaginationBar 
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      )}
    </>
  );
};

export default GoogleAnalytics;
