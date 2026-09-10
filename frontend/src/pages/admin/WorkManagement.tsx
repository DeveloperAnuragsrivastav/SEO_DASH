import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../../api/client';

import * as XLSX from 'xlsx';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';
import { CheckSquare } from 'lucide-react';

const WorkManagement: React.FC = () => {
  const { clientId } = useParams();
  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);

  const fetchActivities = async () => {
    try {
      const res = await api.get(`/clients/${clientId}/work`, {
        params: { page, page_size: pageSize }
      });
      setActivities(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      // Handled by global interceptor
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchActivities();
  }, [clientId, page, pageSize]);

  const exportExcel = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/work`, {
        params: { page: 1, page_size: 100000 }
      });
      const ws = XLSX.utils.json_to_sheet(data.items);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Work Activity");
      XLSX.writeFile(wb, `Work_Activity_${clientId}.xlsx`);
    } catch (err) {
      // Handled by global interceptor
    }
  };

  if (loading && !activities.length) return <PageSkeleton />;

  return (
    <>
      <PageHeader 
        title="On-Site SEO Activities Performed"
        subtitle="View and manually track on-site SEO activities."
        actions={
          <button className="btn btn-secondary" onClick={exportExcel} disabled={activities.length === 0}>
            Download Excel
          </button>
        }
      />

      {activities.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <span className="empty-state-icon"><CheckSquare size={22} /></span>
            <h3>No activities logged</h3>
            <p>Record on-site SEO work from the Data Ingestion Hub.</p>
          </div>
        </div>
      ) : (
        <div className="page-card-flush data-panel">
          <div className="data-panel-head">
            <div>
              <h2 className="h2">On-Site Activities</h2>
              <p className="section-sub">Work delivered on the site.</p>
            </div>
          </div>
          <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Activity Type</th>
                <th className="num">Count</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {activities.map((act, i) => (
                <tr key={i}>
                  <td><span className="badge" style={{ fontWeight: 500 }}>{act.activity_type}</span></td>
                  <td className="num">{act.count}</td>
                  <td className="text-subtle">{act.notes || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}
      
      {activities.length > 0 && (
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

export default WorkManagement;
