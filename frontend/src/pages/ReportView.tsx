import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom';
import api from '../api/client';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { fmt, deltaEl } from '../components/report/ReportUtils';
import ExecutiveSummary from '../components/report/ExecutiveSummary';
import TrafficSection from '../components/report/TrafficSection';
import RankingsSection from '../components/report/RankingsSection';
import AIVisibilitySection from '../components/report/AIVisibilitySection';
import LinksSection from '../components/report/LinksSection';
import WorkDoneSection from '../components/report/WorkDoneSection';
import { MousePointerClick, Users, TrendingUp, Bot, SlidersHorizontal } from 'lucide-react';
import ReportComposer from '../components/ReportComposer';
import '../report.css';

const ReportView: React.FC = () => {
  const { clientId, snapshotId } = useParams<{ clientId: string; snapshotId: string }>();
  const [searchParams] = useSearchParams();
  const count = searchParams.get('count') || '1';
  const navigate = useNavigate();
  const { user } = useAuth();
  const [client, setClient] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [downloadingPDF, setDownloadingPDF] = useState(false);
  const [activeSection, setActiveSection] = useState('executive-summary');
  const [showComposer, setShowComposer] = useState(searchParams.get('compose') === '1');

  const snap = report?.snapshot || {};
  const months = snap.months || [];
  const windowLabel = months.length > 0 
    ? (months.length === 1 ? months[0] : `${months[0]} – ${months[months.length - 1]}`)
    : (report ? new Date(report.end_date).toLocaleDateString('default', { month: 'long', year: 'numeric' }) : '');

  const gsc = snap.gsc || {};
  const ga4 = snap.ga4 || {};
  const gbp = snap.gbp || {};
  const deltas = snap.kpi_deltas || { gsc: {}, ga4: {}, gbp: {} };

  // Rows the composer unticked never reach the page. Ids mirror the server's
  // report_composer module, so app and PDF drop exactly the same rows.
  const chosenItems = snap.included_items || {};
  const keepRow = (id: string) => chosenItems[id] !== false;

  const rawRankings = snap.rankings || { summary: {}, keywords: [] };
  const rankings = {
    ...rawRankings,
    keywords: (rawRankings.keywords || []).filter(
      (kw: any, i: number) => keepRow(`rankings.kw.${kw.keyword_id ?? `i${i}`}`)
    ),
  };
  const aiVis = (snap.ai_visibility || []).filter(
    (m: any, i: number) => keepRow(`ai_visibility.${m.prompt_id ?? i}.${m.platform ?? 'unknown'}`)
  );
  const links = (snap.links || []).filter(
    (l: any, i: number) => keepRow(`links.${l.id ?? `i${i}`}`)
  );
  const activities = (snap.activities || []).filter((_: any, i: number) => keepRow(`work.act.${i}`));
  const screenshots = (snap.screenshots || []).filter(
    (sh: any, i: number) => keepRow(`work.shot.${sh.id ?? `i${i}`}`)
  );

  const gscClicks = gsc.clicks || 0;
  const ga4Sessions = ga4.sessions || 0;
  const ga4Users = ga4.users || 0;

  const aiMentioned = aiVis.filter((m: any) => m.mentioned).length;
  const aiTotal = aiVis.length;

  // Smart section detection — determine which sections have real data
  // A section shows only if it has data AND the composer left it switched on.
  // An absent selection means "show whatever has data", i.e. the old behaviour.
  const included = snap.included_sections || {};
  const on = (key: string) => included[key] !== false;

  const showMetric = (id: string) => chosenItems[id] !== false;
  const metricOn = chosenItems;

  const hasGSC = on('gsc') && (gscClicks > 0 || (gsc.impressions || 0) > 0);
  const hasGA4 = on('ga4') && (ga4Sessions > 0 || (ga4.users || 0) > 0);
  const hasGBP = on('gbp') && ((gbp.calls || 0) > 0 || (gbp.direction_requests || 0) > 0 || (gbp.website_clicks || 0) > 0 || (gbp.searches || 0) > 0);
  const hasRankings = on('rankings') && (rankings.keywords || []).length > 0;
  const hasAI = on('ai_visibility') && aiTotal > 0;
  const hasLinks = on('links') && links.length > 0;
  const hasWork = on('work') && (activities.length > 0 || screenshots.length > 0);

  useEffect(() => {
    if (!clientId || !snapshotId) return;
    setLoading(true);
    Promise.all([
      api.get(`/clients/${clientId}`),
      snapshotId === 'multi' 
        ? api.get(`/clients/${clientId}/reports/multi?count=${count}`).catch(() => ({ data: null }))
        : api.get(`/clients/${clientId}/reports/${snapshotId}`).catch(() => ({ data: null })),
    ]).then(([c, r]) => {
      setClient(c.data);
      setReport(r.data);
    }).finally(() => setLoading(false));
  }, [clientId, snapshotId]);

  // Intersection observer for nav highlighting
  useEffect(() => {
    const sections = document.querySelectorAll('section.report-section');
    const obs = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) setActiveSection(e.target.id); });
    }, { rootMargin: '-120px 0px -70% 0px' });
    sections.forEach(s => obs.observe(s));
    return () => obs.disconnect();
  }, [report]);

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
          if (full.data && full.data.id && (!report || full.data.id !== report.id)) {
            reportData = full.data;
            break;
          }
        } catch (e) {
          // ignore 404s while processing
        }
      }
      
      toast.dismiss(toastId);
      if (reportData) {
        toast.success('Report snapshot generated!');
        navigate(`/admin/clients/${clientId}/reports/${reportData.id}`);
      } else {
        toast.error('Report generation is taking too long. Please refresh later.');
      }
    } catch (err: any) {
      toast.dismiss(toastId);
      // Handled by global interceptor
    }
    setGenerating(false);
  };

  const handlePublish = async () => {
    try {
      await api.post(`/clients/${clientId}/reports/${snapshotId}/publish`);
      const full = await api.get(`/clients/${clientId}/reports/${snapshotId}`);
      setReport(full.data);
      toast.success('Report published!');
    } catch (err: any) {
      // Handled by global interceptor
    }
  };

  const handleDownloadPDF = async () => {
    setDownloadingPDF(true);
    const toastId = toast.loading('Generating PDF...', { duration: 60000 });
    try {
      const endpoint = snapshotId === 'multi'
        ? `/clients/${clientId}/reports/multi/pdf?count=${count}`
        : `/clients/${clientId}/reports/${snapshotId}/pdf`;
      const response = await api.get(endpoint, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${client.name.replace(/\s+/g, '_')}_SEO_Report.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.dismiss(toastId);
      toast.success('PDF downloaded successfully!');
    } catch (err: any) {
      toast.dismiss(toastId);
      // Handled by global interceptor
    }
    setDownloadingPDF(false);
  };

  if (loading) return <div className="loader-container"><div className="spinner" /></div>;

  // Build dynamic nav — only show sections with data
  const sections = [
    { id: 'executive-summary', label: 'Executive Summary', show: true },
    { id: 'search', label: 'Traffic & Conversions', show: hasGSC || hasGA4 || hasGBP },
    { id: 'rankings', label: 'Rankings', show: hasRankings },
    { id: 'ai', label: 'AI Visibility', show: hasAI },
    { id: 'links', label: 'Links Built', show: hasLinks },
    { id: 'work', label: 'Work Done', show: hasWork },
  ].filter(s => s.show);

  // Build dynamic top KPIs — only show cards with non-zero values
  const topKpis = [
    hasGSC && showMetric('gsc.clicks') && gscClicks > 0 && { icon: <MousePointerClick size={16} color="var(--brand)" />, label: 'Search Clicks', value: fmt(gscClicks), sub: <>{deltaEl(gscClicks, gscClicks - (deltas.gsc?.clicks || 0))} vs prev</> },
    hasGA4 && showMetric('ga4.sessions') && ga4Sessions > 0 && { icon: <Users size={16} color="var(--brand)" />, label: 'Website Sessions', value: fmt(ga4Sessions), sub: `${fmt(ga4Users)} users` },
    hasRankings && (rankings.summary?.improved || 0) > 0 && { icon: <TrendingUp size={16} color="var(--brand)" />, label: 'Rankings Improved', value: rankings.summary?.improved || 0, sub: `${rankings.summary?.declined || 0} declined` },
    hasAI && aiMentioned > 0 && { icon: <Bot size={16} color="var(--brand)" />, label: 'AI Brand Mentions', value: aiMentioned, sub: `of ${aiTotal} tracked prompts` },
  ].filter(Boolean) as { icon: any; label: string; value: any; sub: any }[];

  return (
    <div className="report-view">
      {showComposer && clientId && snapshotId && snapshotId !== 'multi' && (
        <ReportComposer
          clientId={clientId}
          snapshotId={snapshotId}
          onClose={() => setShowComposer(false)}
          onSaved={async () => {
            setShowComposer(false);
            try {
              const full = await api.get(`/clients/${clientId}/reports/${snapshotId}`);
              setReport(full.data);
            } catch (e) {
              // Handled by global interceptor
            }
          }}
        />
      )}

      {/* Report cover — the same masthead the PDF opens with */}
      <div className="report-cover">
        <div className="report-cover-inner">
          <div className="report-cover-id">
            {client?.logo_url
              ? <span className="report-logo"><img src={client.logo_url} alt="" /></span>
              : <span className="report-logo is-empty">Client logo</span>}
            <div className="report-head-text">
              <h2 className="report-cover-name">{client?.name}</h2>
              <p className="report-cover-domain">{client?.domain}</p>
            </div>
          </div>

          <p className="report-eyebrow">Monthly SEO Report</p>
          <h1 className="report-cover-title">
            Performance Report
            {windowLabel && <span>{windowLabel}</span>}
          </h1>

          <div className="report-cover-meta">
            <span className="report-status">{(report?.status || 'no report').toUpperCase()}</span>
            {report?.generated_at && <span>Generated {new Date(report.generated_at).toLocaleString()}</span>}
          </div>

          <div className="report-cover-actions">
            <Link to={`/admin/clients/${clientId}`} className="btn ghost">Back to client</Link>

            {report && report.status === 'draft' && snapshotId !== 'multi' && (
              <button className="btn btn-secondary" onClick={() => setShowComposer(true)}>
                <SlidersHorizontal size={14} /> Sections &amp; Data
              </button>
            )}

            {report && (
              <button className="btn btn-secondary" onClick={handleDownloadPDF} disabled={downloadingPDF}>
                {downloadingPDF ? 'Generating PDF…' : 'Download PDF'}
              </button>
            )}

            {report?.status === 'draft' && (user?.role === 'agency_admin' || user?.role === 'super_admin') && (
              <button className="btn btn-primary" onClick={handlePublish}>Publish</button>
            )}
          </div>
        </div>
      </div>

      {/* Section nav */}
      <nav className="nav">
        <div className="wrap">
          {sections.map(s => (
            <a key={s.id} href={`#${s.id}`} className={activeSection === s.id ? 'act' : ''}>
              {s.label}
            </a>
          ))}
        </div>
      </nav>

      {/* No report state */}
      {!report ? (
        <div className="wrap" style={{ padding: '80px 24px', textAlign: 'center' }}>
          <h2 className="h1" style={{ marginBottom: '16px' }}>Snapshot not found</h2>
          <p className="text-subtle" style={{ marginBottom: '32px' }}>Generate one to aggregate all data sources.</p>
          <button className="btn btn-primary" onClick={handleGenerate} disabled={generating} style={{ padding: '12px 24px' }}>
            {generating ? 'Generating…' : 'Generate report'}
          </button>
        </div>
      ) : (
        <div className="wrap">
          
          <ExecutiveSummary 
            narrative={report.narrative} 
            monthLabel={windowLabel} 
            status={report.status} 
            publishedAt={report.published_at} 
          />
          
          {topKpis.length > 0 && (
            <div className={`grid g${topKpis.length}`} style={{ marginBottom: 'var(--space-xl)' }}>
              {topKpis.map((kpi, i) => (
                <div className="kpi" key={i}>
                  <div className="lab">{kpi.icon} {kpi.label}</div>
                  <div className="val">{kpi.value}</div>
                  <div className="sub">{kpi.sub}</div>
                </div>
              ))}
            </div>
          )}

          {(hasGSC || hasGA4 || hasGBP) && (
            <TrafficSection metricOn={metricOn} gsc={gsc} ga4={ga4} gbp={gbp} deltas={deltas} />
          )}
          
          {hasRankings && (
            <RankingsSection rankings={rankings} keywords={rankings.keywords || []} months={months} />
          )}
          
          {hasAI && (
            <AIVisibilitySection aiVisibility={aiVis} totalKeywords={rankings.keywords?.length || 0} aiMentioned={aiMentioned} aiTotal={aiTotal} months={months} />
          )}
          
          {hasLinks && (
            <LinksSection links={links} months={months} />
          )}
          
          {hasWork && (
            <WorkDoneSection activities={activities} screenshots={screenshots} months={months} />
          )}

        </div>
      )}
    </div>
  );
};

export default ReportView;
