import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../../api/client';

import * as XLSX from 'xlsx';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';
import { Link2 } from 'lucide-react';

const LinksManagement: React.FC = () => {
  const { clientId } = useParams();
  const [links, setLinks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);

  const fetchLinks = async () => {
    try {
      const res = await api.get(`/clients/${clientId}/links`, {
        params: { page, page_size: pageSize }
      });
      setLinks(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      // Handled by global interceptor
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchLinks();
  }, [clientId, page, pageSize]);

  const exportExcel = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/links`, {
        params: { page: 1, page_size: 100000 }
      });
      const ws = XLSX.utils.json_to_sheet(data.items);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Backlinks");
      XLSX.writeFile(wb, `Backlinks_${clientId}.xlsx`);
    } catch (err) {
      // Handled by global interceptor
    }
  };

  if (loading && !links.length) return <PageSkeleton />;

  return (
    <>
      <PageHeader 
        title="Performed Backlinks Activities"
        subtitle="View and manually track built backlinks."
        actions={
          <button className="btn btn-secondary" onClick={exportExcel} disabled={links.length === 0}>
            Download Excel
          </button>
        }
      />

      {links.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <span className="empty-state-icon"><Link2 size={22} /></span>
            <h3>No backlinks recorded</h3>
            <p>Track built links by uploading them from the Data Ingestion Hub.</p>
          </div>
        </div>
      ) : (
        <div className="card table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Month</th>
                <th>Activity Type</th>
                <th>URL</th>
                <th className="num">Count</th>
              </tr>
            </thead>
            <tbody>
              {links.map((link, i) => {
                let monthDisplay = link.created_on;
                if (link.created_on) {
                  const parts = link.created_on.split('-');
                  if (parts.length === 3) {
                    const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
                    monthDisplay = `${d.toLocaleString('default', { month: 'long' })}'${parts[0].slice(2)}`;
                  }
                }
                return (
                <tr key={i}>
                  <td style={{ fontWeight: 500, textTransform: 'capitalize' }}>{monthDisplay}</td>
                  <td><span className="badge">{link.activity_type}</span></td>
                  <td>{link.url ? <a href={link.url} target="_blank" rel="noreferrer" className="link">{link.domain || 'Link'}</a> : '—'}</td>
                  <td className="num">{link.count || 1}</td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      
      {links.length > 0 && (
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

export default LinksManagement;
