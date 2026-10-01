import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import api from '../../api/client';
import { toast } from 'sonner';
import { fmt } from '../../components/report/ReportUtils';
import {
  Palette, RefreshCw, FileText, Download, ArrowRight, ArrowUpRight,
  SearchX, Loader2, MousePointerClick, Users, TrendingUp, Bot,
  Crosshair, BarChart2, MapPin, Search, Link as LinkIcon, CheckSquare,
  Image as ImageIcon, Plug, Pencil
} from 'lucide-react';

import Page from '../../components/ui/Page';
import PageSkeleton from '../../components/ui/PageSkeleton';
import Sparkline from '../../components/ui/Sparkline';
import PeriodPicker from '../../components/PeriodPicker';
import type { PeriodsInfo } from '../../components/PeriodPicker';
import { confirmDialog } from '../../components/ui/ConfirmDialog';

const ClientDashboard: React.FC = () => {
  const { clientId } = useParams();
  const navigate = useNavigate();

  /** Reopen a published report for changes. Publishing it again rewrites
   *  its month on every sheet with the new figures. */
  const makeDraft = async (id: string) => {
    if (!(await confirmDialog({ title: 'Make this report a draft again?', message: 'You can change anything in it. The sheets keep the published figures until you publish it again — then they are replaced with the new ones.', confirmText: 'Make draft' }))) return;
    try {
      await api.post(`/clients/${clientId}/reports/${id}/unpublish`);
      toast.success('The report is a draft again.');
      navigate(`/admin/clients/${clientId}/reports/${id}/build`);
    } catch {
      // Handled by global interceptor
    }
  };
  const [client, setClient] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [reportCount, setReportCount] = useState<number>(0);
  const [connections, setConnections] = useState<any[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sections, setSections] = useState<any[] | null>(null);
  const [trends, setTrends] = useState<any>(null);
  const [savingMode, setSavingMode] = useState<string | null>(null);

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
  const [openingDraft, setOpeningDraft] = useState(false);

  useEffect(() => {
    if (!clientId) return;
    Promise.all([
      api.get(`/clients/${clientId}`).catch(() => null),
      // A client with no report yet is a normal first-run state, not an error —
      // opt these two out of the global error toast.
      api.get(`/clients/${clientId}/reports/latest`, { skipErrorToast: true } as any).catch(() => ({ data: null })),
      api.get(`/clients/${clientId}/connections`).catch(() => ({ data: [] })),
      api.get(`/clients/${clientId}/reports/count`, { skipErrorToast: true } as any).catch(() => ({ data: { count: 0 } })),
      api.get(`/clients/${clientId}/sections`, { skipErrorToast: true } as any).catch(() => ({ data: [] })),
      api.get(`/clients/${clientId}/reports/trends?days=30`, { skipErrorToast: true } as any).catch(() => ({ data: null })),
    ]).then(([c, r, conn, rCount, sec, tr]) => {
      if (!c) {
        setClient(null);
        return;
      }
      setClient(c.data);
      setReport(r.data);
      setConnections(conn.data || []);
      setReportCount(rCount.data?.count || 0);
      setSections(sec.data || []);
      setTrends(tr.data || null);
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

  /** Record that this client's traffic source is hand-entered rather than API-linked. */
  const chooseManual = async (provider: 'gsc' | 'ga4') => {
    setSavingMode(provider);
    try {
      await api.put(`/clients/${clientId}/sections/${provider}_manual`, { enabled: true });
      const res = await api.get(`/clients/${clientId}/sections`);
      setSections(res.data || []);
      toast.success(`${provider.toUpperCase()} set to manual entry. Add it under Add Data.`);
    } catch (err: any) {
      // Handled by global interceptor
    }
    setSavingMode(null);
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

  /** A period was chosen: generate a new report, or reopen this cycle's draft. */
  const onPickPeriod = async (months: number, info: PeriodsInfo) => {
    if (info.mode === 'new') {
      setShowGenerateModal(false);
      navigate(`/admin/clients/${clientId}/reports/new?months=${months}`);
      return;
    }
    if (info.mode === 'draft' && info.report_id) {
      if (months !== (info.months || 1)) {
        setOpeningDraft(true);
        try {
          await api.post(`/clients/${clientId}/reports/${info.report_id}/period`, { months });
        } catch (err: any) {
          // Handled by global interceptor
          setOpeningDraft(false);
          return;
        }
        setOpeningDraft(false);
      }
      setShowGenerateModal(false);
      navigate(`/admin/clients/${clientId}/reports/${info.report_id}/build`);
    }
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
    setLoadingHistory(true);
    try {
      const res = await api.get(`/clients/${clientId}/reports/history`);
      setHistory(res.data || []);
    } catch (err) {
      // Handled by global interceptor
    }
    setLoadingHistory(false);
  };

  /** A report's name: its month, or the first and last month it combines. */
  const reportName = (snap: any) => {
    const start = new Date(snap.start_date);
    const end = new Date(snap.end_date);
    const month = (d: Date) => d.toLocaleString('default', { month: 'long', year: 'numeric' });
    const days = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
    if (days <= 31) return month(end);
    return `${month(new Date(start.getTime() + 29 * 86400000))} – ${month(end)}`;
  };


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

  // How each traffic source is supplied. A connection row means the API path
  // was taken; a `<provider>_manual` section toggle means it is hand-entered.
  // Neither means nobody has said yet — so we ask.
  const trafficMode = (provider: 'gsc' | 'ga4'): 'api' | 'manual' | 'unset' => {
    if (connections.some((c: any) => c.provider === provider)) return 'api';
    if ((sections || []).some((r: any) => r.section_key === `${provider}_manual` && r.enabled)) return 'manual';
    return 'unset';
  };

  const TRAFFIC_SOURCES = [
    {
      key: 'ga4' as const,
      name: 'Google Analytics',
      icon: <BarChart2 size={16} />,
      question: 'Can you sign in to this client\'s Google Analytics?',
    },
    {
      key: 'gsc' as const,
      name: 'Search Console',
      icon: <Search size={16} />,
      question: 'Can you sign in to this client\'s Search Console?',
    },
  ];

  // Don't ask until the section preferences have actually loaded.
  const unresolved = sections === null ? [] : TRAFFIC_SOURCES.filter(s => trafficMode(s.key) === 'unset');

  // A report names its own period — one month, or the months it combines.
  const periodLabel = report?.snapshot?.period?.label || (report?.end_date
    ? new Date(report.end_date).toLocaleString('default', { month: 'long', year: 'numeric' })
    : '');

  /** Real recorded series only — an absent metric renders without a chart. */
  const seriesOf = (provider: string, key: string): number[] => {
    const pts = trends?.series?.[provider]?.[key];
    return Array.isArray(pts) ? pts.map((p: any) => Number(p.v) || 0) : [];
  };

  const pctChange = (current: number, delta: number): number | null => {
    const previous = current - delta;
    if (!previous) return null;
    return (delta / previous) * 100;
  };

  const kpis = [
    {
      key: 'clicks',
      icon: <MousePointerClick size={16} />,
      tone: 'amber',
      label: 'Search Clicks',
      value: fmt(gscClicks),
      change: pctChange(gscClicks, deltas.gsc?.clicks || 0),
      series: seriesOf('gsc', 'clicks'),
      foot: 'vs previous period',
      note: (c: number | null) =>
        c === null ? 'No previous period to compare against.'
        : c > 0 ? 'More people are finding your site in search results.'
        : c < 0 ? 'Fewer clicks from search than the period before.'
        : 'Search clicks held steady this period.',
    },
    {
      key: 'sessions',
      icon: <Users size={16} />,
      tone: 'blue',
      label: 'Website Sessions',
      value: fmt(ga4Sessions),
      change: pctChange(ga4Sessions, deltas.ga4?.sessions || 0),
      series: seriesOf('ga4', 'sessions'),
      foot: 'vs previous period',
      note: () => `${fmt(ga4Users)} users in ${periodLabel || 'this period'}.`,
    },
    {
      key: 'rankings',
      icon: <TrendingUp size={16} />,
      tone: 'violet',
      label: 'Rankings Improved',
      value: fmt(rankSummary.improved || 0),
      change: null,
      series: [],
      foot: `${fmt(rankSummary.top_10 || 0)} in top 10 · ${fmt(rankSummary.declined || 0)} declined`,
      note: () =>
        (rankSummary.improved || 0) > 0
          ? `${fmt(rankSummary.improved)} keywords moved up this period.`
          : 'No ranking changes this period.',
    },
    {
      key: 'ai',
      icon: <Bot size={16} />,
      tone: 'green',
      label: 'AI Brand Mentions',
      value: fmt(aiMentioned),
      change: null,
      series: [],
      foot: `of ${fmt(aiTotal)} tracked prompts`,
      note: () =>
        aiMentioned > 0
          ? 'Your brand is being mentioned in AI tools.'
          : 'No AI tool mentioned your brand yet.',
    },
  ];

  // Each area summarised in one line, with the full table one click away.
  const areas = [
    {
      tone: 'amber', series: [], bars: true,
      icon: <Crosshair size={15} />, label: 'Keyword Performance',
      to: `/clients/${clientId}/keywords`,
      value: fmt((rankings.keywords || []).length),
      unit: 'keywords tracked',
      detail: `${fmt(rankSummary.top_10 || 0)} in top 10 · ${fmt(rankSummary['11_20'] || 0)} in 11–20`,
    },
    {
      tone: 'blue', series: seriesOf('gsc', 'impressions'),
      icon: <Search size={15} />, label: 'Search Console',
      to: `/clients/${clientId}/search-console`,
      value: fmt(gsc.impressions || 0),
      unit: 'impressions',
      detail: `${fmt(gscClicks)} clicks · avg position ${(gsc.position || 0).toFixed(1)}`,
    },
    {
      tone: 'orange', series: seriesOf('ga4', 'sessions'),
      icon: <BarChart2 size={15} />, label: 'Google Analytics',
      to: `/clients/${clientId}/google-analytics`,
      value: fmt(ga4Sessions),
      unit: 'sessions',
      detail: `${fmt(ga4Users)} users · ${fmt(ga4.conversions || 0)} conversions`,
    },
    {
      tone: 'rose', series: seriesOf('gbp', 'calls'),
      icon: <MapPin size={15} />, label: 'Google Business Profile',
      to: `/clients/${clientId}/gbp`,
      value: fmt(gbp.calls || 0),
      unit: 'calls',
      detail: `${fmt(gbp.direction_requests || 0)} directions · ${fmt(gbp.website_clicks || 0)} site clicks`,
    },
    {
      tone: 'green', series: [],
      icon: <Bot size={15} />, label: 'AI Visibility',
      to: `/clients/${clientId}/ai-mentions-data`,
      value: fmt(aiMentioned),
      unit: 'prompts mentioning brand',
      detail: `${fmt(aiTotal - aiMentioned)} not mentioned`,
    },
    {
      tone: 'violet', series: [],
      icon: <LinkIcon size={15} />, label: 'Backlinks',
      to: `/clients/${clientId}/links`,
      value: fmt(links.length),
      unit: 'links built',
      detail: 'Recorded this period',
    },
    {
      tone: 'green', series: [],
      icon: <CheckSquare size={15} />, label: 'Work Done',
      to: `/clients/${clientId}/work`,
      value: fmt(activities.length),
      unit: 'activities',
      detail: 'On-site SEO performed',
    },
    {
      tone: 'blue', series: [], bars: true,
      icon: <ImageIcon size={15} />, label: 'Screenshots',
      to: `/clients/${clientId}/screenshots`,
      value: fmt(screenshots.length),
      unit: 'uploaded',
      detail: 'Evidence attached to the report',
    },
  ];

  return (
      <Page
        screen="overview"
        title={client.name}
        badge={
          <span className={`status-pill ${client.status === 'active' ? 'on' : ''}`}>
            {client.status === 'active' ? 'Active Client' : String(client.status || '').toUpperCase()}
          </span>
        }
        lede={`${client.domain} · ${client.package_keywords} keywords in package`}
        actions={
          <button className="btn btn-secondary" onClick={() => setShowWhitelabel(true)}>
            <Palette size={15} /> Whitelabel Settings
          </button>
        }
      >

      {!report ? (
        /* ── Nothing generated yet: state the next step plainly ───────── */
        <div className="page-card" style={{ marginBottom: 24 }}>
          <div className="empty-state">
            <span className="empty-state-icon"><FileText size={22} /></span>
            <h3>No report generated yet</h3>
            <p>
              Choose the period and generate the first report. This month is fetched from Google
              where it is connected; everything else is added with a sheet inside the report builder.
            </p>
            <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap', justifyContent: 'center' }}>
              <button className="btn btn-primary" onClick={openGenerateModal}>Generate First Report</button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* ── 1. The answer: headline performance ────────────────────── */}
          <div className="section-title">
            <div>
              <h2 className="h2">Performance · {periodLabel}</h2>
              <p className="section-sub">How this client is doing against the period before.</p>
            </div>
            <Link to={`/admin/clients/${clientId}/reports/${report.id}`} className="btn ghost btn-sm">
              Open full report <ArrowUpRight size={14} />
            </Link>
          </div>

          <div className="kpi-row">
            {kpis.map(k => (
              <div key={k.key} className="stat">
                <div className="stat-top">
                  <span className={`stat-chip tone-${k.tone}`}>{k.icon}</span>
                  <span className="stat-label">{k.label}</span>
                </div>

                <div className="stat-figure">
                  <span className="stat-value">{k.value}</span>
                  {k.change !== null && (
                    <span className={`trend ${k.change > 0 ? 'up' : k.change < 0 ? 'down' : 'flat'}`}>
                      {k.change > 0 ? '↑' : k.change < 0 ? '↓' : '—'} {Math.abs(k.change).toFixed(0)}%
                    </span>
                  )}
                  <span className="stat-spark">
                    <Sparkline
                      values={k.series}
                      color={`var(--tone-${k.tone})`}
                      label={`${k.label} trend`}
                    />
                  </span>
                </div>

                <div className="stat-foot">{k.foot}</div>
                <div className="stat-note">{k.note(k.change)}</div>
              </div>
            ))}
          </div>

          {/* ── 2. Where the report stands ─────────────────────────────── */}
          <div className="section-title">
            <div>
              <h2 className="h2">This Month's Report</h2>
              <p className="section-sub">What the client will receive, and where it stands.</p>
            </div>
            <Link to={`/admin/clients/${clientId}/reports/${report.id}`} className="section-link">
              Open full report <ArrowUpRight size={14} />
            </Link>
          </div>

          <div className="report-card">
            <span className="stat-chip lg tone-amber"><FileText size={20} /></span>

            <div className="report-card-body">
              <div className="report-card-head">
                <span className={`badge ${report.status === 'published' ? 'badge-success' : 'badge-warning'}`}>
                  {report.status.toUpperCase()}
                </span>
                <span className="report-card-title">{periodLabel} report</span>
              </div>
              <div className="text-subtle text-xs">
                Generated {report.generated_at ? new Date(report.generated_at).toLocaleString() : '—'}
                {' · '}{reportCount} total {reportCount === 1 ? 'report' : 'reports'}
              </div>
            </div>

            <div className="report-card-actions">
              <button className="btn ghost" onClick={openGenerateModal}>All reports</button>
              {report.status === 'published' && (
                <button className="btn btn-secondary" onClick={() => makeDraft(report.id)}>
                  <Pencil size={14} /> Make draft
                </button>
              )}
              <Link
                to={report.status === 'draft'
                  ? `/admin/clients/${clientId}/reports/${report.id}/build`
                  : `/admin/clients/${clientId}/reports/${report.id}`}
                className="btn btn-primary"
              >
                {report.status === 'draft' ? 'Continue building' : 'Open report'} <ArrowRight size={14} />
              </Link>
            </div>
          </div>

          {/* ── 3. The detail, summarised — full tables one click away ─── */}
          <div className="section-title">
            <div>
              <h2 className="h2">Explore the Data</h2>
              <p className="section-sub">Dive deeper into this client's performance.</p>
            </div>
          </div>

          <div className="area-grid">
            {areas.map(a => (
              <Link key={a.label} to={a.to} className="area-card">
                <span className="area-top">
                  <span className={`stat-chip sm tone-${a.tone}`}>{a.icon}</span>
                  <span className="area-label">{a.label}</span>
                </span>

                <span className="area-figure">
                  <span className="area-value">{a.value} <small>{a.unit}</small></span>
                  <span className="area-spark">
                    <Sparkline
                      values={a.series}
                      color={`var(--tone-${a.tone})`}
                      variant={(a as any).bars ? 'bar' : 'line'}
                      width={72}
                      height={28}
                      label={`${a.label} trend`}
                    />
                  </span>
                </span>

                <span className="area-detail">{a.detail}</span>
                <span className="area-cta">View all <ArrowRight size={13} /></span>
              </Link>
            ))}
          </div>

        </>
      )}

      {/* ── 4. Where the traffic data comes from ─────────────────────── */}
      <div className="section-title"><h2 className="h2">Traffic Data</h2></div>

      {unresolved.length > 0 ? (
        /* Never answered for at least one source — ask, in plain language. */
        <div className="page-card setup-card">
          <div className="setup-head">
            <span className="empty-state-icon"><Plug size={20} /></span>
            <div>
              <h3 className="setup-title">Where does this client's traffic data come from?</h3>
              <p className="setup-desc">
                We can pull it automatically if you can sign in to their Google accounts.
                Otherwise you can type it in each month — the report works either way.
              </p>
            </div>
          </div>

          {unresolved.map(src => (
            <div key={src.key} className="setup-choice">
              <div className="setup-choice-label">
                {src.icon}
                <div>
                  <div className="data-row-name">{src.name}</div>
                  <div className="text-subtle text-xs">{src.question}</div>
                </div>
              </div>
              <div className="setup-choice-actions">
                <Link to={`/admin/clients/${clientId}/connections`} className="btn btn-primary btn-sm">
                  Yes, I can sign in
                </Link>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => chooseManual(src.key)}
                  disabled={savingMode === src.key}
                >
                  {savingMode === src.key
                    ? <><Loader2 size={13} className="spin" /> Saving…</>
                    : "No, I'll enter it manually"}
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Both answered — a slim status line is enough. */
        <div className="page-card panel">
          <div className="panel-head">
            <h3 className="h2">Data Sources</h3>
            <Link to={`/admin/clients/${clientId}/connections`} className="btn ghost btn-sm">Manage</Link>
          </div>

          <div className="panel-body">
            {TRAFFIC_SOURCES.map(src => {
              const mode = trafficMode(src.key);
              const c = connections.find((x: any) => x.provider === src.key);
              const isConnected = c?.status === 'connected';
              return (
                <div key={src.key} className="data-row">
                  <div className="data-row-label">
                    <span className={`dot ${mode === 'api' ? (isConnected ? 'on' : 'warn') : 'off'}`} />
                    <span className="data-row-name">{src.name}</span>
                  </div>
                  {mode === 'manual' ? (
                    <span className="src man" title="Added with a sheet inside the report builder">
                      Entered manually
                    </span>
                  ) : (
                    <span className="src" title={c ? (isConnected ? c.property_id : c.status) : ''}>
                      {isConnected ? c.property_id : (c?.status || 'not connected')}
                    </span>
                  )}
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
      )}

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
            <h2 className="modal-title">Reports</h2>
            <p className="modal-desc">Generate this month's report — on its own, or combined with earlier months — or open one already made.</p>

            <div className="overline" style={{ marginBottom: 10 }}>Report period</div>
            {clientId && (
              <PeriodPicker
                clientId={clientId}
                busy={openingDraft}
                confirmText={(m, label, info) => info.mode === 'draft'
                  ? (m === (info.months || 1) ? 'Open the draft' : `Update the draft to ${label}`)
                  : `Generate ${label}`}
                onConfirm={onPickPeriod}
              />
            )}

            <div className="overline" style={{ margin: '24px 0 10px' }}>All reports</div>
            {loadingHistory ? (
              <p className="text-subtle text-sm" style={{ textAlign: 'center', padding: '16px' }}>Loading reports…</p>
            ) : history.length > 0 ? (
              <div className="stack scroll-y" style={{ maxHeight: '240px' }}>
                {history.map(snap => {
                  const name = reportName(snap);
                  const draft = snap.status === 'draft';
                  return (
                    <div key={snap.id} className="list-row">
                      <div>
                        <span style={{ fontWeight: 600, fontSize: '13.5px', display: 'flex', alignItems: 'center', gap: 8 }}>
                          {name}
                          <span className={`badge ${draft ? 'badge-warning' : 'badge-success'}`}>{String(snap.status).toUpperCase()}</span>
                        </span>
                        <span className="text-subtle text-xs">
                          Generated {snap.generated_at ? new Date(snap.generated_at).toLocaleString() : '—'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <Link
                          to={draft ? `/admin/clients/${clientId}/reports/${snap.id}/build` : `/admin/clients/${clientId}/reports/${snap.id}`}
                          className="btn btn-secondary btn-sm"
                          onClick={() => setShowGenerateModal(false)}
                        >
                          {draft ? 'Continue' : 'Open'}
                        </Link>
                        <button className="btn btn-secondary btn-sm" onClick={() => handleDownloadHistoricalPDF(snap.id, name)} disabled={downloading}>
                          {downloading ? <Loader2 size={13} className="spin" /> : <Download size={13} />} PDF
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-subtle text-sm" style={{ textAlign: 'center', padding: '16px' }}>No reports yet.</p>
            )}

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowGenerateModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </Page>
  );
};

export default ClientDashboard;
