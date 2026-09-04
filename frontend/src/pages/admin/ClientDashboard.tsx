import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../../api/client';
import { toast } from 'sonner';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';

const ClientDashboard: React.FC = () => {
  const { clientId } = useParams();
  const [client, setClient] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [reportCount, setReportCount] = useState<number>(0);
  const [connections, setConnections] = useState<any[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);

  // Whitelabel Modal State
  const [showWhitelabel, setShowWhitelabel] = useState(false);
  const [editName, setEditName] = useState('');
  const [editTheme, setEditTheme] = useState('');
  const [editLogo, setEditLogo] = useState('');
  const [savingSettings, setSavingSettings] = useState(false);

  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (!clientId) return;
    Promise.all([
      api.get(`/clients/${clientId}`).catch(() => null),
      api.get(`/clients/${clientId}/reports/latest`).catch(() => ({ data: null })),
      api.get(`/clients/${clientId}/connections`).catch(() => ({ data: [] })),
      api.get(`/clients/${clientId}/reports/count`).catch(() => ({ data: { count: 0 } })),
    ]).then(([c, r, conn, rCount]) => {
      if (!c) {
        setClient(null);
        return;
      }
      setClient(c.data);
      setReport(r.data);
      setConnections(conn.data || []);
      setReportCount(rCount.data?.count || 0);
      setEditName(c.data.name || '');
      setEditTheme(c.data.theme_color || '#2563eb');
      setEditLogo(c.data.logo_url || '');
    }).finally(() => setLoading(false));
  }, [clientId]);

  const handleSaveWhitelabel = async () => {
    setSavingSettings(true);
    try {
      await api.put(`/clients/${clientId}`, {
        name: editName,
        theme_color: editTheme,
        logo_url: editLogo,
      });
      setClient({ ...client, name: editName, theme_color: editTheme, logo_url: editLogo });
      setShowWhitelabel(false);
      toast.success('Settings saved successfully.');
    } catch (err: any) {
      // Handled by global interceptor
    }
    setSavingSettings(false);
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.post(`/clients/${clientId}/connections/sync`);
      toast.success('GA4 + GSC data synced successfully.');
    } catch (err: any) {
      let synced = 0;
      for (const conn of connections) {
        if (['gsc', 'ga4'].includes(conn.provider) && conn.status === 'connected') {
          try {
            await api.post(`/connections/${conn.id}/verify`);
            synced++;
          } catch {}
        }
      }
      if (synced > 0) toast.success(`Verified ${synced} connection(s).`);
      // Global interceptor will handle the initial error toast if any
    }
    setSyncing(false);
  };

  const handleGenerate = async () => {
    setGenerating(true);
    const toastId = toast.info('Report generation started (this may take a minute)...', { duration: 60000 });
    try {
      await api.post(`/clients/${clientId}/reports/generate`, {});
      
      let reportData = null;
      for (let i = 0; i < 20; i++) {
        await new Promise(r => setTimeout(r, 3000));
        try {
          const full = await api.get(`/clients/${clientId}/reports/latest`);
          if (full.data && full.data.id) {
            // Check if the generated report is newer than the old one (or if there wasn't one)
            if (!report || full.data.id !== report.id) {
              reportData = full.data;
              break;
            }
          }
        } catch (e) {
          // ignore 404s while processing
        }
      }
      
      toast.dismiss(toastId);
      if (reportData) {
        setReport(reportData);
        setReportCount(prev => prev + 1); // Optimistically increment
        toast.success('Report generated successfully!');
      } else {
        toast.error('Report generation timed out.');
      }
    } catch (err: any) {
      toast.dismiss(toastId);
      // Handled by global interceptor
    }
    setGenerating(false);
  };

  const handleDownloadPDF = async (count: number) => {
    setDownloading(true);
    const toastId = toast.loading('Generating PDF...', { duration: 60000 });
    try {
      const response = await api.get(`/clients/${clientId}/reports/multi/pdf?count=${count}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${client.name.replace(/\s+/g, '_')}_${count}M_SEO_Report.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.dismiss(toastId);
      toast.success('PDF downloaded successfully!');
    } catch (err: any) {
      toast.dismiss(toastId);
      // Handled by global interceptor
    }
    setDownloading(false);
  };

  const handleDownloadHistoricalPDF = async (snapshotId: string, monthLabel: string) => {
    setDownloading(true);
    const toastId = toast.loading('Generating PDF...', { duration: 60000 });
    try {
      const response = await api.get(`/clients/${clientId}/reports/multi/pdf?count=1&snapshot_id=${snapshotId}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${client.name.replace(/\s+/g, '_')}_${monthLabel.replace(/\s+/g, '_')}_SEO_Report.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.dismiss(toastId);
      toast.success('PDF downloaded successfully!');
    } catch (err: any) {
      toast.dismiss(toastId);
      // Handled by global interceptor
    }
    setDownloading(false);
  };

  const openGenerateModal = async () => {
    setShowGenerateModal(true);
    if (history.length === 0) {
      setLoadingHistory(true);
      try {
        const res = await api.get(`/clients/${clientId}/reports/history`);
        setHistory(res.data || []);
      } catch (err) {
        // Handled by global interceptor
      }
      setLoadingHistory(false);
    }
  };

  let daysRemaining = 0;
  if (report && report.end_date) {
    const endDate = new Date(report.end_date);
    const today = new Date();
    const diffTime = today.getTime() - endDate.getTime();
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    if (diffDays < 30) {
      daysRemaining = 30 - diffDays;
    }
  }

  if (loading) return <PageSkeleton cards={2} header={true} stats={0} />;
  
  if (!client) return (
    <div className="page-card" style={{ textAlign: 'center', margin: '40px auto', maxWidth: '600px' }}>
      <h2 className="h2" style={{ marginBottom: '16px' }}>Project Not Found</h2>
      <p className="text-subtle" style={{ marginBottom: '32px' }}>This project may have been deleted or you don't have access to it.</p>
      <Link to="/admin/clients" className="btn btn-primary">Go back to Clients</Link>
    </div>
  );

  return (
    <>
      <PageHeader 
        title={`${client.name} Overview`}
        subtitle={`${client.domain} · ${client.package_keywords} tracked keywords`}
        breadcrumbs={[{ label: 'Home', href: '/' }, { label: 'Clients', href: '/admin/clients' }, { label: client.name }]}
        actions={
          <button className="btn btn-secondary" onClick={() => setShowWhitelabel(true)}>
            🎨 Whitelabel Settings
          </button>
        }
      />

      <div className="grid-cols-2" style={{ marginBottom: '24px' }}>
        {/* API Connections */}
        <div className="page-card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h3 className="h2">API Connections</h3>
            <Link to={`/admin/clients/${clientId}/connections`} className="btn btn-secondary btn-sm">Manage</Link>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '24px', flex: 1 }}>
            {['gsc', 'ga4'].map(p => {
              const c = connections.find((x: any) => x.provider === p);
              const isConnected = c?.status === 'connected';
              return (
                <div key={p} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '12px', borderBottom: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span className={`badge ${isConnected ? 'badge-success' : 'badge-neutral'}`} style={{ width: '8px', height: '8px', padding: 0, borderRadius: '50%' }} />
                    <span style={{ fontWeight: 600, fontSize: '14px', textTransform: 'uppercase' }}>{p}</span>
                  </div>
                  <span className="text-subtle text-xs mono">
                    {c ? (isConnected ? c.property_id : c.status) : 'Manual / Not Linked'}
                  </span>
                </div>
              );
            })}
          </div>
          <button className="btn btn-secondary" onClick={handleSync} disabled={syncing} style={{ width: '100%', justifyContent: 'center' }}>
            {syncing ? 'Syncing...' : 'Sync Connected Sources'}
          </button>
        </div>

        {/* Report Generation */}
        <div className="page-card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h3 className="h2">Latest Report Snapshot</h3>
            {report && (
              <span className={`badge ${report.status === 'published' ? 'badge-success' : 'badge-warning'}`}>
                {report.status.toUpperCase()}
              </span>
            )}
          </div>
          
          {!report ? (
            <div style={{ textAlign: 'center', padding: '24px 0', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <p className="text-subtle" style={{ marginBottom: '8px' }}>No report snapshot generated yet.</p>
              <p className="text-subtle text-xs" style={{ marginBottom: '24px' }}>Ensure all bulk data is uploaded before generating.</p>
              <button className="btn btn-primary" onClick={handleGenerate} disabled={generating} style={{ width: '100%', justifyContent: 'center' }}>
                {generating ? 'Generating...' : 'Generate Snapshot'}
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '12px', borderBottom: '1px solid var(--border-subtle)' }}>
                <span className="text-subtle text-sm">Total Snapshots</span>
                <span className="mono" style={{ fontWeight: 600 }}>
                  {reportCount}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '12px', borderBottom: '1px solid var(--border-subtle)' }}>
                <span className="text-subtle text-sm">Latest Generated</span>
                <span className="mono text-xs">{report.generated_at ? new Date(report.generated_at).toLocaleString() : '—'}</span>
              </div>
              
              <div style={{ marginTop: 'auto', paddingTop: '16px' }}>
                <button className="btn btn-primary" onClick={openGenerateModal} style={{ width: '100%', justifyContent: 'center' }}>
                  Generate / View Reports
                </button>
                
                {daysRemaining > 0 && report.status !== 'published' && (
                  <p className="text-xs" style={{ textAlign: 'center', marginTop: '12px', color: 'var(--amber)' }}>
                    Generating a new snapshot is blocked for {daysRemaining} more day(s).
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {showWhitelabel && (
        <div className="modal-backdrop">
          <div className="modal">
            <h2 className="h2" style={{ marginBottom: '24px' }}>Whitelabel Settings</h2>
            
            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label className="form-label">Client Name</label>
              <input type="text" className="form-input" value={editName} onChange={e => setEditName(e.target.value)} />
            </div>

            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label className="form-label">Theme Color (Hex)</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input type="color" value={editTheme} onChange={e => setEditTheme(e.target.value)} style={{ width: '40px', height: '40px', padding: 0, border: 'none', cursor: 'pointer', borderRadius: '4px' }} />
                <input type="text" className="form-input" value={editTheme} onChange={e => setEditTheme(e.target.value)} style={{ flex: 1 }} />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: '32px' }}>
              <label className="form-label">Logo URL (Optional)</label>
              <input type="text" className="form-input" placeholder="https://..." value={editLogo} onChange={e => setEditLogo(e.target.value)} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button className="btn btn-secondary" onClick={() => setShowWhitelabel(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSaveWhitelabel} disabled={savingSettings}>
                {savingSettings ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showGenerateModal && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: '500px' }}>
            <h2 className="h2" style={{ marginBottom: '24px' }}>Generate / View Reports</h2>
            
            {reportCount > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                {Array.from({ length: Math.min(reportCount, 12) }, (_, i) => i + 1).map(num => (
                  <div key={num} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', background: 'var(--bg-app)' }}>
                    <span style={{ fontWeight: 600 }}>{num === 1 ? 'This Month' : `${num} Months`}</span>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <Link to={`/admin/clients/${clientId}/reports/multi?count=${num}`} className="btn btn-primary btn-sm">Open in App</Link>
                      <button className="btn btn-secondary btn-sm" onClick={() => handleDownloadPDF(num)} disabled={downloading}>
                        {downloading ? '...' : 'PDF'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div style={{ marginTop: '24px', marginBottom: '12px' }}>
              <h3 className="text-subtle text-sm" style={{ fontWeight: 600, textTransform: 'uppercase' }}>Past Single-Month Snapshots</h3>
            </div>
            
            {loadingHistory ? (
              <p className="text-subtle text-sm" style={{ textAlign: 'center', padding: '16px' }}>Loading history...</p>
            ) : history.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '250px', overflowY: 'auto' }}>
                {history.map(snap => {
                  const dateLabel = new Date(snap.end_date).toLocaleString('default', { month: 'long', year: 'numeric' });
                  return (
                    <div key={snap.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', background: 'var(--bg-app)' }}>
                      <div>
                        <span style={{ fontWeight: 500, fontSize: '14px', display: 'block' }}>{dateLabel}</span>
                        <span className="text-subtle text-xs">{new Date(snap.generated_at).toLocaleString()}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button className="btn btn-secondary btn-sm" onClick={() => handleDownloadHistoricalPDF(snap.id, dateLabel)} disabled={downloading}>
                          {downloading ? '...' : 'PDF'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-subtle text-sm" style={{ textAlign: 'center', padding: '16px' }}>No past snapshots available.</p>
            )}
            
            <div style={{ marginTop: '24px', paddingTop: '20px', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
               <div>
                 <h4 className="h2" style={{ margin: 0, fontSize: '15px', marginBottom: '4px' }}>Generate New Snapshot</h4>
                 <p className="text-subtle text-xs" style={{ margin: 0, maxWidth: '240px' }}>Captures the latest data to append to the report history.</p>
               </div>
               <button 
                  className="btn btn-secondary" 
                  onClick={() => { setShowGenerateModal(false); handleGenerate(); }}
                  disabled={generating || (daysRemaining > 0 && report?.status !== 'published')}
                >
                  {generating ? 'Generating...' : 'Generate New'}
               </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '32px' }}>
              <button className="btn btn-secondary" onClick={() => setShowGenerateModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ClientDashboard;
