import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../../api/client';
import { toast } from 'sonner';
import { fmt, deltaEl } from '../../components/report/ReportUtils';
import {
  Palette, RefreshCw, FileText, Download, ArrowRight, ArrowUpRight,
  SearchX, Loader2, MousePointerClick, Users, TrendingUp, Bot,
  Crosshair, BarChart2, MapPin, Search, Link as LinkIcon, CheckSquare,
  Image as ImageIcon, Inbox, Plug
} from 'lucide-react';

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
      // A client with no report yet is a normal first-run state, not an error —
      // opt these two out of the global error toast.
      api.get(`/clients/${clientId}/reports/latest`, { skipErrorToast: true } as any).catch(() => ({ data: null })),
      api.get(`/clients/${clientId}/connections`).catch(() => ({ data: [] })),
      api.get(`/clients/${clientId}/reports/count`, { skipErrorToast: true } as any).catch(() => ({ data: { count: 0 } })),
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
    let synced = 0;
    for (const conn of connections) {
      if (['gsc', 'ga4'].includes(conn.provider) && conn.status === 'connected') {
        try {
          await api.post(`/connections/${conn.id}/verify`);
          synced++;
        } catch (err: any) {
          err._toastHandled = true;
        }
      }
    }
    if (synced > 0) {
      toast.success(`Verified ${synced} connection(s).`);
    } else {
      toast.info('No active GA4 or GSC connections to sync.');
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

  if (loading) return <PageSkeleton cards={2} header={true} stats={4} />;

  if (!client) return (
    <div className="page-card" style={{ margin: '40px auto', maxWidth: '560px' }}>
      <div className="empty-state">
        <span className="empty-state-icon"><SearchX size={22} /></span>
        <h3>Project not found</h3>
        <p>This project may have been deleted, or you don't have access to it.</p>
        <Link to="/admin/clients" className="btn btn-primary">Back to Clients</Link>
      </div>
    </div>
  );

  // ── Read the headline numbers straight out of the latest report snapshot ──
  // Same fields and same delta convention the report itself uses, so the
  // overview and the report can never disagree.
  const snap = report?.snapshot || {};
  const gsc = snap.gsc || {};
  const ga4 = snap.ga4 || {};
  const gbp = snap.gbp || {};
  const rankings = snap.rankings || { summary: {}, keywords: [] };
  const aiVis = snap.ai_visibility || [];
  const links = snap.links || [];
  const activities = snap.activities || [];
  const screenshots = snap.screenshots || [];
  const deltas = snap.kpi_deltas || { gsc: {}, ga4: {}, gbp: {} };

  const gscClicks = gsc.clicks || 0;
  const ga4Sessions = ga4.sessions || 0;
  const ga4Users = ga4.users || 0;
  const aiMentioned = aiVis.filter((m: any) => m.mentioned).length;
  const aiTotal = aiVis.length;
  const rankSummary = rankings.summary || {};

  const periodLabel = report?.end_date
    ? new Date(report.end_date).toLocaleString('default', { month: 'long', year: 'numeric' })
    : '';

  const kpis = [
    {
      icon: <MousePointerClick size={15} />,
      label: 'Search Clicks',
      value: fmt(gscClicks),
      sub: <>{deltaEl(gscClicks, gscClicks - (deltas.gsc?.clicks || 0))} vs previous period</>,
    },
    {
      icon: <Users size={15} />,
      label: 'Website Sessions',
      value: fmt(ga4Sessions),
      sub: <>{deltaEl(ga4Sessions, ga4Sessions - (deltas.ga4?.sessions || 0))} · {fmt(ga4Users)} users</>,
    },
    {
      icon: <TrendingUp size={15} />,
      label: 'Rankings Improved',
      value: fmt(rankSummary.improved || 0),
      sub: <>{fmt(rankSummary.top_10 || 0)} in top 10 · {fmt(rankSummary.declined || 0)} declined</>,
    },
    {
      icon: <Bot size={15} />,
      label: 'AI Brand Mentions',
      value: fmt(aiMentioned),
      sub: <>of {fmt(aiTotal)} tracked prompts</>,
    },
  ];

  // Each area summarised in one line, with the full table one click away.
  const areas = [
    {
      icon: <Crosshair size={15} />, label: 'Keyword Performance',
      to: `/clients/${clientId}/keywords`,
      value: fmt((rankings.keywords || []).length),
      unit: 'keywords tracked',
      detail: `${fmt(rankSummary.top_10 || 0)} in top 10 · ${fmt(rankSummary['11_20'] || 0)} in 11–20`,
    },
    {
      icon: <Search size={15} />, label: 'Search Console',
      to: `/clients/${clientId}/search-console`,
      value: fmt(gsc.impressions || 0),
      unit: 'impressions',
      detail: `${fmt(gscClicks)} clicks · avg position ${(gsc.position || 0).toFixed(1)}`,
    },
    {
      icon: <BarChart2 size={15} />, label: 'Google Analytics',
      to: `/clients/${clientId}/google-analytics`,
      value: fmt(ga4Sessions),
      unit: 'sessions',
      detail: `${fmt(ga4Users)} users · ${fmt(ga4.conversions || 0)} conversions`,
    },
    {
      icon: <MapPin size={15} />, label: 'Google Business Profile',
      to: `/clients/${clientId}/gbp`,
      value: fmt(gbp.calls || 0),
      unit: 'calls',
      detail: `${fmt(gbp.direction_requests || 0)} directions · ${fmt(gbp.website_clicks || 0)} site clicks`,
    },
    {
      icon: <Bot size={15} />, label: 'AI Visibility',
      to: `/clients/${clientId}/ai-mentions-data`,
      value: fmt(aiMentioned),
      unit: 'prompts mentioning brand',
      detail: `${fmt(aiTotal - aiMentioned)} not mentioned`,
    },
    {
      icon: <LinkIcon size={15} />, label: 'Backlinks',
      to: `/clients/${clientId}/links`,
      value: fmt(links.length),
      unit: 'links built',
      detail: 'Recorded this period',
    },
    {
      icon: <CheckSquare size={15} />, label: 'Work Done',
      to: `/clients/${clientId}/work`,
      value: fmt(activities.length),
      unit: 'activities',
      detail: 'On-site SEO performed',
    },
    {
      icon: <ImageIcon size={15} />, label: 'Screenshots',
      to: `/clients/${clientId}/screenshots`,
      value: fmt(screenshots.length),
      unit: 'uploaded',
      detail: 'Evidence attached to the report',
    },
  ];

  return (
    <>
      <PageHeader
        title={`${client.name} Overview`}
        subtitle={`${client.domain} · ${client.package_keywords} tracked keywords`}
        breadcrumbs={[{ label: 'Home', href: '/' }, { label: 'Clients', href: '/admin/clients' }, { label: client.name }]}
        actions={
          <>
            <Link to={`/admin/clients/${clientId}/manual-entry`} className="btn btn-secondary">
              <Inbox size={15} /> Add Data
            </Link>
            <button className="btn btn-secondary" onClick={() => setShowWhitelabel(true)}>
              <Palette size={15} /> Whitelabel Settings
            </button>
          </>
        }
      />

      {!report ? (
        /* ── Nothing generated yet: state the next step plainly ───────── */
        <div className="page-card" style={{ marginBottom: 24 }}>
          <div className="empty-state">
            <span className="empty-state-icon"><FileText size={22} /></span>
            <h3>No report generated yet</h3>
            <p>
              Add this client's data, then generate the first report. Once generated,
              this page shows headline performance at a glance.
            </p>
            <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap', justifyContent: 'center' }}>
              <Link to={`/admin/clients/${clientId}/manual-entry`} className="btn btn-secondary">
                <Inbox size={15} /> Add Data
              </Link>
              <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
                {generating ? <><Loader2 size={15} className="spin" /> Generating…</> : 'Generate First Report'}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* ── 1. The answer: headline performance ────────────────────── */}
          <div className="section-title">
            <h2 className="h2">Performance · {periodLabel}</h2>
            <Link to={`/admin/clients/${clientId}/reports/${report.id}`} className="btn ghost btn-sm">
              Open full report <ArrowUpRight size={14} />
            </Link>
          </div>

          <div className="kpi-row">
            {kpis.map(k => (
              <div key={k.label} className="kpi">
                <span className="lab">{k.icon} {k.label}</span>
                <span className="val">{k.value}</span>
                <span className="sub">{k.sub}</span>
              </div>
            ))}
          </div>

          {/* ── 2. Where the report stands ─────────────────────────────── */}
          <div className="section-title"><h2 className="h2">This Month's Report</h2></div>

          <div className="page-card report-status">
            <div className="report-status-main">
              <span className={`badge ${report.status === 'published' ? 'badge-success' : 'badge-warning'}`}>
                {report.status.toUpperCase()}
              </span>
              <div>
                <div className="report-status-title">{periodLabel} report</div>
                <div className="text-subtle text-xs">
                  Generated {report.generated_at ? new Date(report.generated_at).toLocaleString() : '—'}
                  {' · '}{reportCount} total {reportCount === 1 ? 'report' : 'reports'}
                </div>
              </div>
            </div>

            <div className="report-status-actions">
              <Link to={`/admin/clients/${clientId}/reports/${report.id}`} className="btn btn-secondary">
                <FileText size={15} /> View
              </Link>
              <button className="btn btn-primary" onClick={openGenerateModal}>
                Generate / View Reports <ArrowRight size={14} />
              </button>
            </div>

            {daysRemaining > 0 && report.status !== 'published' && (
              <p className="text-xs report-status-note">
                Generating a new snapshot is blocked for {daysRemaining} more day(s).
              </p>
            )}
          </div>

          {/* ── 3. The detail, summarised — full tables one click away ─── */}
          <div className="section-title"><h2 className="h2">Explore the Data</h2></div>

          <div className="area-grid">
            {areas.map(a => (
              <Link key={a.label} to={a.to} className="area-card">
                <span className="area-label">{a.icon} {a.label}</span>
                <span className="area-value">
                  {a.value} <small>{a.unit}</small>
                </span>
                <span className="area-detail">{a.detail}</span>
                <span className="area-cta">View all <ArrowRight size={13} /></span>
              </Link>
            ))}
          </div>
        </>
      )}

      {/* ── 4. The machinery, last ───────────────────────────────────── */}
      <div className="section-title"><h2 className="h2">Data Sources</h2></div>

      <div className="page-card panel">
        <div className="panel-head">
          <h3 className="h2"><Plug size={15} style={{ verticalAlign: '-2px', marginRight: 6, color: 'var(--ink-3)' }} />API Connections</h3>
          <Link to={`/admin/clients/${clientId}/connections`} className="btn ghost btn-sm">Manage</Link>
        </div>

        <div className="panel-body">
          {['gsc', 'ga4'].map(p => {
            const c = connections.find((x: any) => x.provider === p);
            const isConnected = c?.status === 'connected';
            return (
              <div key={p} className="data-row">
                <div className="data-row-label">
                  <span className={`dot ${isConnected ? 'on' : 'off'}`} />
                  <span className="data-row-name">{p.toUpperCase()}</span>
                </div>
                <span className={`src ${isConnected ? '' : 'man'}`} title={c ? (isConnected ? c.property_id : c.status) : 'Manual / Not Linked'}>
                  {c ? (isConnected ? c.property_id : c.status) : 'Manual / Not Linked'}
                </span>
              </div>
            );
          })}
        </div>

        <div className="panel-foot">
          <button className="btn btn-secondary btn-block" onClick={handleSync} disabled={syncing}>
            {syncing ? <><Loader2 size={15} className="spin" /> Syncing…</> : <><RefreshCw size={15} /> Sync Connected Sources</>}
          </button>
        </div>
      </div>

      {showWhitelabel && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowWhitelabel(false); }}>
          <div className="modal" role="dialog" aria-modal="true">
            <h2 className="modal-title">Whitelabel Settings</h2>
            <p className="modal-desc">Branding applied to this client's reports and portal.</p>

            <div className="form-group">
              <label className="form-label">Client Name</label>
              <input type="text" className="form-input" value={editName} onChange={e => setEditName(e.target.value)} />
            </div>

            <div className="form-group">
              <label className="form-label">Theme Color</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="color"
                  value={editTheme}
                  onChange={e => setEditTheme(e.target.value)}
                  className="color-swatch"
                  aria-label="Theme colour picker"
                />
                <input type="text" className="form-input mono" value={editTheme} onChange={e => setEditTheme(e.target.value)} style={{ flex: 1 }} />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Logo URL <span style={{ color: 'var(--ink-4)', fontWeight: 400 }}>· optional</span></label>
              <input type="text" className="form-input" placeholder="https://..." value={editLogo} onChange={e => setEditLogo(e.target.value)} />
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowWhitelabel(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSaveWhitelabel} disabled={savingSettings}>
                {savingSettings ? <><Loader2 size={15} className="spin" /> Saving…</> : 'Save Settings'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showGenerateModal && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowGenerateModal(false); }}>
          <div className="modal modal-lg" role="dialog" aria-modal="true">
            <h2 className="modal-title">Generate / View Reports</h2>
            <p className="modal-desc">Open a rolling multi-month view, or export any period as PDF.</p>

            {reportCount > 0 && (
              <>
                <div className="overline" style={{ marginBottom: 10 }}>Rolling Periods</div>
                <div className="stack scroll-y" style={{ maxHeight: '260px' }}>
                  {Array.from({ length: Math.min(reportCount, 12) }, (_, i) => i + 1).map(num => (
                    <div key={num} className="list-row">
                      <span style={{ fontWeight: 600, fontSize: 13.5 }}>{num === 1 ? 'This Month' : `${num} Months`}</span>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <Link to={`/admin/clients/${clientId}/reports/multi?count=${num}`} className="btn btn-primary btn-sm">Open in App</Link>
                        <button className="btn btn-secondary btn-sm" onClick={() => handleDownloadPDF(num)} disabled={downloading}>
                          {downloading ? <Loader2 size={13} className="spin" /> : <Download size={13} />} PDF
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            <div className="overline" style={{ margin: '22px 0 10px' }}>Past Single-Month Snapshots</div>

            {loadingHistory ? (
              <p className="text-subtle text-sm" style={{ textAlign: 'center', padding: '16px' }}>Loading history…</p>
            ) : history.length > 0 ? (
              <div className="stack scroll-y" style={{ maxHeight: '220px' }}>
                {history.map(snap => {
                  const dateLabel = new Date(snap.end_date).toLocaleString('default', { month: 'long', year: 'numeric' });
                  return (
                    <div key={snap.id} className="list-row">
                      <div>
                        <span style={{ fontWeight: 600, fontSize: '13.5px', display: 'block' }}>{dateLabel}</span>
                        <span className="text-subtle text-xs">{new Date(snap.generated_at).toLocaleString()}</span>
                      </div>
                      <button className="btn btn-secondary btn-sm" onClick={() => handleDownloadHistoricalPDF(snap.id, dateLabel)} disabled={downloading}>
                        {downloading ? <Loader2 size={13} className="spin" /> : <Download size={13} />} PDF
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-subtle text-sm" style={{ textAlign: 'center', padding: '16px' }}>No past snapshots available.</p>
            )}

            <div className="callout">
              <div>
                <h4 className="callout-title">Generate New Snapshot</h4>
                <p className="callout-desc">Captures the latest data to append to the report history.</p>
              </div>
              <button
                className="btn btn-secondary"
                onClick={() => { setShowGenerateModal(false); handleGenerate(); }}
                disabled={generating || (daysRemaining > 0 && report?.status !== 'published')}
              >
                {generating ? <><Loader2 size={15} className="spin" /> Generating…</> : 'Generate New'}
              </button>
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowGenerateModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ClientDashboard;
