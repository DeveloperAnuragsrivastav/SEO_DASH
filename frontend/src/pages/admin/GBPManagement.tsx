import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../../api/client';

import * as XLSX from 'xlsx';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';

const GBPManagement: React.FC = () => {
  const { clientId } = useParams();
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);

  const fetchRecords = async () => {
    try {
      const res = await api.get(`/clients/${clientId}/manual-gbp`, {
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
      const { data } = await api.get(`/clients/${clientId}/manual-gbp`, {
        params: { page: 1, page_size: 100000 }
      });
      const ws = XLSX.utils.json_to_sheet(data.items);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "GBP Data");
      XLSX.writeFile(wb, `GBP_Data_${clientId}.xlsx`);
    } catch (err) {
      // Handled by global interceptor
    }
  };

  if (loading && !records.length) return <PageSkeleton />;

  return (
    <>
      <PageHeader 
        title="GBP Data Management"
        subtitle="View and manage manually entered Google Business Profile metrics."
        actions={
          <button className="btn btn-secondary" onClick={exportExcel} disabled={records.length === 0}>
            Download Excel
          </button>
        }
      />

      {records.length === 0 ? (
        <div className="card" style={{ padding: '64px', textAlign: 'center' }}>
          <p className="text-subtle">No manual GBP data found.</p>
        </div>
      ) : (
        <div className="card table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th className="num">Maps (D/M)</th>
                <th className="num">Search (D/M)</th>
                <th className="num">Calls</th>
                <th className="num">Directions</th>
                <th className="num">Clicks</th>
                <th className="num">Bookings</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 500 }}>{r.captured_on}</td>
                  <td className="num">{r.impressions_desktop_maps} / {r.impressions_mobile_maps}</td>
                  <td className="num">{r.impressions_desktop_search} / {r.impressions_mobile_search}</td>
                  <td className="num">{r.calls}</td>
                  <td className="num">{r.direction_requests}</td>
                  <td className="num">{r.website_clicks}</td>
                  <td className="num">{r.bookings}</td>
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

export default GBPManagement;
