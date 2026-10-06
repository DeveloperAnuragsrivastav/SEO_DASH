import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom';
import api, { errorText } from '../api/client';
import { toast } from 'sonner';
import { SlidersHorizontal } from 'lucide-react';
import '../report.css';
import { confirmDialog } from '../components/ui/ConfirmDialog';

/** Width of one slide in report_slides.html — 1280×720px, i.e. 960×540pt. */
const SHEET_PX = 1280;

/* Screen-only adjustments layered onto the PDF template: drop the grey desk
   behind the sheet, and open links in a new tab rather than inside the frame. */
const SCREEN_HEAD = `<base target="_blank"><style>
  html, body { background: transparent !important; overflow: hidden !important; }
</style>`;

/* The deck is already a stack of fixed 1280×720 slides on screen and in
   print, so it needs no rewriting to preview — what the frame shows is what
   the PDF prints. */
const asPrinted = (html: string) => html;

const ReportView: React.FC = () => {
  const { clientId, snapshotId } = useParams<{ clientId: string; snapshotId: string }>();
  const [searchParams] = useSearchParams();
  const count = searchParams.get('count') || '1';
  const navigate = useNavigate();
  const [client, setClient] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [downloadingPDF, setDownloadingPDF] = useState(false);

  // Older links opened a composer over the finished report. Choosing what to
  // include now happens in the builder, before the report is shown.
  useEffect(() => {
    if (searchParams.get('compose') === '1' && snapshotId && snapshotId !== 'multi') {
      navigate(`/admin/clients/${clientId}/reports/${snapshotId}/build`, { replace: true });
    }
  }, []);

  // The report itself is the PDF's own template, rendered by the server.
  const [html, setHtml] = useState<string | null>(null);
  // Why the report could not be drawn or opened — said on the page, not "could not be loaded".
  const [htmlError, setHtmlError] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [sheetHeight, setSheetHeight] = useState(0);
  const [scale, setScale] = useState(1);
  const stageRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);

  const htmlEndpoint = snapshotId === 'multi'
    ? `/clients/${clientId}/reports/multi/html?count=${count}`
    : `/clients/${clientId}/reports/${snapshotId}/html`;

  const loadHtml = useCallback(async () => {
    setHtmlError(null);
    try {
      const { data } = await api.get(htmlEndpoint, { responseType: 'text', skipErrorToast: true } as any);
      setHtml(asPrinted(String(data)).replace('</head>', `${SCREEN_HEAD}</head>`));
    } catch (e) {
      setHtmlError(errorText(e, 'this report'));
    }
  }, [htmlEndpoint]);

  const windowLabel = report
    ? (report.snapshot?.period?.label
      || new Date(report.end_date).toLocaleDateString('default', { month: 'long', year: 'numeric' }))
    : '';

  useEffect(() => {
    if (!clientId || !snapshotId) return;
    setLoading(true);
    Promise.all([
      api.get(`/clients/${clientId}`),
      (snapshotId === 'multi'
        ? api.get(`/clients/${clientId}/reports/multi?count=${count}`, { skipErrorToast: true } as any)
        : api.get(`/clients/${clientId}/reports/${snapshotId}`, { skipErrorToast: true } as any))
        .catch((e: any) => { setReportError(errorText(e, 'this report')); return { data: null }; }),
    ]).then(([c, r]) => {
      setClient(c.data);
      setReport(r.data);
      if (r.data) loadHtml();
    }).catch((e) => {
      setReportError(errorText(e, 'this client'));
    }).finally(() => setLoading(false));
  }, [clientId, snapshotId]);

  // Fit the fixed-width sheet to whatever space the app shell leaves.
  useLayoutEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const fit = () => setScale(Math.min(1, el.clientWidth / SHEET_PX));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [html]);

  // The sheet is content-sized; size the frame to it so the app scrolls, not the frame.
  const frameObserver = useRef<ResizeObserver | null>(null);
  const measure = async () => {
    const doc = frameRef.current?.contentDocument;
    if (!doc) return;
    // Fit each slide to its page exactly as the PDF does: the deck carries its
    // own deckFit(), which the script-free frame cannot run, so it runs here
    // on the frame's document once the fonts are in.
    try {
      await (doc as any).fonts?.ready;
      const code = doc.getElementById('deck-fit')?.textContent;
      if (code) (new Function(`${code}\nreturn deckFit;`)() as (d: Document) => void)(doc);
    } catch {
      // The deck still shows, just without the tightening.
    }
    const update = () => setSheetHeight(doc.documentElement.scrollHeight);
    update();
    // Fonts and images land after load and change the height. Follow the
    // document instead of measuring once — a frame even a few px short grows
    // its own scrollbar beside the app's.
    frameObserver.current?.disconnect();
    frameObserver.current = new ResizeObserver(update);
    frameObserver.current.observe(doc.body);
  };
  useEffect(() => () => frameObserver.current?.disconnect(), []);

  /** Generate through the same page every other Generate button uses: it
   *  shows progress, a failure's reason at once, and opens the builder. */
  const handleGenerate = () => {
    setGenerating(true);
    navigate(`/admin/clients/${clientId}/reports/new?months=1`);
  };

  const handlePublish = async () => {
    const month = report?.end_date ? new Date(`${report.end_date}T00:00:00`).toLocaleString('en', { month: 'long', year: 'numeric' }) : 'this month';
    if (!(await confirmDialog({
      title: `Publish the ${month} report?`,
      message: `Its figures become ${month}'s column in every sheet (Search Console, Analytics, Keywords…). To change it later, use Make draft and publish again.`,
      confirmText: 'Publish',
    }))) return;
    try {
      await api.post(`/clients/${clientId}/reports/${snapshotId}/publish`);
      const full = await api.get(`/clients/${clientId}/reports/${snapshotId}`);
      setReport(full.data);
      toast.success(`Published — ${month} is now on every sheet.`);
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

  return (
    <div className="report-view">
      {/* Toolbar — the same actions as before; the report below is the PDF itself */}
      <div className="report-toolbar">
        <div className="report-toolbar-id">
          <span className="report-toolbar-name">{client?.name}</span>
          {windowLabel && <span className="report-toolbar-period">{windowLabel}</span>}
          {report && (
            <span className={`badge ${report.status === 'published' ? 'badge-success' : 'badge-warning'}`}>
              {String(report.status).toUpperCase()}
            </span>
          )}
        </div>

        <div className="report-toolbar-actions">
          <Link to={`/admin/clients/${clientId}`} className="btn ghost">Back to client</Link>

          {report && report.status === 'draft' && snapshotId !== 'multi' && (
            <button className="btn btn-secondary" onClick={() => navigate(`/admin/clients/${clientId}/reports/${snapshotId}/build`)}>
              <SlidersHorizontal size={14} /> Sections &amp; Data
            </button>
          )}

          {report && (
            <button className="btn btn-secondary" onClick={handleDownloadPDF} disabled={downloadingPDF}>
              {downloadingPDF ? 'Generating PDF…' : 'Download PDF'}
            </button>
          )}

          {report?.status === 'draft' && snapshotId !== 'multi' && (
            <button className="btn btn-primary" onClick={handlePublish}>Publish</button>
          )}
          {report?.status === 'published' && snapshotId !== 'multi' && (
            <button className="btn btn-secondary" onClick={async () => {
              if (!(await confirmDialog({ title: 'Make this report a draft again?', message: 'You can change anything in it. The sheets keep the published figures until you publish it again — then they are replaced with the new ones.', confirmText: 'Make draft' }))) return;
              try {
                await api.post(`/clients/${clientId}/reports/${snapshotId}/unpublish`);
                toast.success('The report is a draft again.');
                navigate(`/admin/clients/${clientId}/reports/${snapshotId}/build`);
              } catch { /* Handled by global interceptor */ }
            }}>Make draft</button>
          )}
        </div>
      </div>

      {!report ? (
        <div className="wrap" style={{ padding: '80px 24px', textAlign: 'center' }}>
          <h2 className="h1" style={{ marginBottom: '16px' }}>{reportError ? 'This report could not be opened' : 'Report not found'}</h2>
          <p className="text-subtle" style={{ marginBottom: '32px', maxWidth: 560, marginInline: 'auto' }}>
            {reportError || 'There is no report here yet. Generate one to bring this period’s data together.'}
          </p>
          <button className="btn btn-primary" onClick={handleGenerate} disabled={generating} style={{ padding: '12px 24px' }}>
            {generating ? 'Generating…' : 'Generate report'}
          </button>
        </div>
      ) : htmlError ? (
        <div className="wrap" style={{ padding: '64px 24px', textAlign: 'center' }}>
          <h3 style={{ marginBottom: 8 }}>This report could not be shown</h3>
          <p className="text-subtle" style={{ marginBottom: '20px', maxWidth: 560, marginInline: 'auto' }}>{htmlError}</p>
          <button className="btn btn-secondary" onClick={loadHtml}>Try again</button>
        </div>
      ) : !html ? (
        <div className="loader-container"><div className="spinner" /></div>
      ) : (
        <div className="report-stage" ref={stageRef}>
          <div
            className="report-sheet"
            style={{ width: SHEET_PX * scale, height: sheetHeight * scale }}
          >
            {/* No scripts are allowed in the frame: the template is static, and it
                carries text people typed. Same-origin only so it can be measured
                and fitted from here. */}
            <iframe
              ref={frameRef}
              title="Report"
              srcDoc={html}
              sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
              scrolling="no"
              onLoad={measure}
              style={{
                width: SHEET_PX,
                height: sheetHeight || 1200,
                transform: `scale(${scale})`,
                transformOrigin: 'top left',
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportView;
