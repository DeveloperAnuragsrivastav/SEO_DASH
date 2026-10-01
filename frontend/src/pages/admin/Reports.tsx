import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Download, FileText, Loader2, Pencil, ExternalLink, Table2 } from 'lucide-react';
import api from '../../api/client';
import Page, { Empty } from '../../components/ui/Page';
import PageSkeleton from '../../components/ui/PageSkeleton';
import '../../sheets.css';

type Row = {
  id: string; label: string; range: string; months: number; status: 'draft' | 'published';
  generated_at: string | null; published_at: string | null; on_sheets: boolean;
};

const when = (d: string | null) => (d ? new Date(d).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '—');

/** Every report this client has had, newest first — the archive. */
export default function Reports() {
  const { clientId } = useParams();
  const navigate = useNavigate();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => api.get(`/clients/${clientId}/reports/history`).then(r => setRows(r.data || [])).catch(() => setRows([]));
  useEffect(() => { load(); }, [clientId]);

  const download = async (r: Row) => {
    setBusy(r.id);
    try {
      const res = await api.get(`/clients/${clientId}/reports/${r.id}/pdf`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url; a.download = `${r.label.replace(/\s+/g, '-')}-report.pdf`;
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    } catch {
      // Handled by global interceptor
    }
    setBusy(null);
  };

  const makeDraft = async (r: Row) => {
    if (!window.confirm(`Make the ${r.label} report a draft again?\n\nYou can change anything in it. The sheets keep its published figures until you publish it again — then they are replaced with the new ones.`)) return;
    try {
      await api.post(`/clients/${clientId}/reports/${r.id}/unpublish`);
      toast.success('The report is a draft again.');
      navigate(`/admin/clients/${clientId}/reports/${r.id}/build`);
    } catch {
      // Handled by global interceptor
    }
  };

  if (rows === null) return <PageSkeleton />;

  return (
    <Page screen="reports">
      <section className="surface sh-surface">
        {rows.length === 0 ? (
          <Empty icon={<FileText size={22} />} title="No reports yet"
            hint="Generate this month's report from the client overview; every report is kept here, month by month."
            action={<Link className="btn btn-secondary" to={`/admin/clients/${clientId}`}>Go to overview</Link>} />
        ) : (
          <div className="sh-scroll" style={{ maxHeight: 'none' }}>
            <table className="sh-table rp-table">
              <thead>
                <tr>
                  <th className="sh-name">Report</th>
                  <th>Period</th>
                  <th>Status</th>
                  <th>Generated</th>
                  <th>Published</th>
                  <th className="sh-num">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id}>
                    <th scope="row" className="sh-name">
                      <div className="sh-name-in">
                        <Link className="rp-title" to={`/admin/clients/${clientId}/reports/${r.id}`}>{r.label}</Link>
                        {r.months > 1 && <span className="rp-tag">{r.months} months</span>}
                      </div>
                    </th>
                    <td>{r.range}</td>
                    <td>
                      <span className={`rp-status ${r.status}`}>{r.status === 'published' ? 'Published' : 'Draft'}</span>
                      {r.status === 'draft' && r.on_sheets && <span className="rp-note" title="The sheets still show this month as it was last published">on sheets</span>}
                    </td>
                    <td>{when(r.generated_at)}</td>
                    <td>{when(r.published_at)}</td>
                    <td className="sh-num">
                      <div className="rp-actions">
                        <Link className="btn ghost btn-sm" to={`/admin/clients/${clientId}/reports/${r.id}`}><ExternalLink size={13} /> Open</Link>
                        {r.status === 'draft'
                          ? <Link className="btn btn-secondary btn-sm" to={`/admin/clients/${clientId}/reports/${r.id}/build`}><Pencil size={13} /> Edit</Link>
                          : <button className="btn btn-secondary btn-sm" onClick={() => makeDraft(r)}><Pencil size={13} /> Make draft</button>}
                        <button className="btn ghost btn-sm" onClick={() => download(r)} disabled={busy === r.id}>
                          {busy === r.id ? <Loader2 size={13} className="spin" /> : <Download size={13} />} PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {rows.length > 0 && (
        <p className="sh-meta" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Table2 size={13} /> Published months are also kept, figure by figure, on the Search Console, Analytics, Keywords… sheets.
        </p>
      )}
    </Page>
  );
}
