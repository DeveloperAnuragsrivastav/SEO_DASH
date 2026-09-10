import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../../api/client';

import * as XLSX from 'xlsx';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';
import { MapPin } from 'lucide-react';

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
        <div className="card">
          <div className="empty-state">
            <span className="empty-state-icon"><MapPin size={22} /></span>
            <h3>No GBP data yet</h3>
            <p>Upload Google Business Profile metrics from the Data Ingestion Hub.</p>
          </div>
        </div>
      ) : (
        <div className="page-card-flush data-panel">
          <div className="data-panel-head">
            <div>
              <h2 className="h2">Business Profile Records</h2>
              <p className="section-sub">Calls, directions and website clicks by date.</p>
            </div>
          </div>
          <div className="table-wrapper">
          <table className="data-table">
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
