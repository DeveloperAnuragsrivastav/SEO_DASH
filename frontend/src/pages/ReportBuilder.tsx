import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import api from '../api/client';
import { toast } from 'sonner';
import {
  Sparkles, Loader2, Info, Pencil, Check, ArrowLeft, ArrowRight,
  Search, BarChart2, MapPin, Crosshair, Bot, Link as LinkIcon, CheckSquare,
  ListChecks, FileText, Plug, RefreshCw, ImagePlus, Trash2, Type, SlidersHorizontal,
  Upload, Download, CalendarRange,
} from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import PageSkeleton from '../components/ui/PageSkeleton';
import PeriodPicker from '../components/PeriodPicker';
import '../builder.css';

type Format = 'int' | 'percent' | 'decimal' | 'bool' | 'none';

interface Item {
  id: string;
  section: string;
  label: string;
  value: number | boolean | null;
  format: Format;
  editable: boolean;
  kind: 'headline' | 'summary' | 'row';
  unit?: string;
  /** The figure has a saved copy an edit can also correct. */
  writable?: boolean;
}

interface Period {
  months: number;
  start: string;
  end: string;
  labels: string[];
  label: string;
  range?: string;
  compare?: { range?: string; hasData?: boolean };
}

interface PeriodRow {
  label: string;
  range?: string;
  start: string;
  end: string;
  [provider: string]: any;
}

interface UploadSpec {
  title: string;
  hint: string;
  endpoint: string;
  columns: string;
  sample: string;
  accept?: string;
}

interface Section { key: string; label: string }
interface Heading { key: string; section: string; title: string }
interface Copy { brand_line: string; titles: Record<string, string>; subtitles: Record<string, string> }
interface Step { key: string; kind: 'basics' | 'overview' | 'section' | 'review'; label: string }

const EMPTY_COPY: Copy = { brand_line: '', titles: {}, subtitles: {} };

const SECTION_ICON: Record<string, React.ReactNode> = {
  gsc: <Search size={15} />,
  ga4: <BarChart2 size={15} />,
  gbp: <MapPin size={15} />,
  rankings: <Crosshair size={15} />,
  ai_visibility: <Bot size={15} />,
  links: <LinkIcon size={15} />,
  work: <CheckSquare size={15} />,
};

const SECTION_SUB: Record<string, string> = {
  gsc: 'Clicks, impressions, click-through rate and average position from Google search.',
  ga4: 'Visits, users and conversions on the website.',
  gbp: 'Calls, direction requests and website clicks from the Google Business Profile.',
  rankings: 'Where each tracked keyword ranks this period.',
  ai_visibility: 'Whether AI assistants mention the brand for each tracked prompt.',
  links: 'Backlinks built this period.',
  work: 'Work delivered this period, with screenshots as proof.',
};

/** Sections whose figures come from a Google connection when there is one. */
const PROVIDER_NAME: Record<string, string> = {
  gsc: 'Google Search Console',
  ga4: 'Google Analytics 4',
  gbp: 'Google Business Profile',
};

/** Sources the builder can pull fresh figures from on demand. */
const FETCHABLE: Record<string, string> = { gsc: 'GSC', ga4: 'GA4' };

/** What a provider section needs before the server will include it. */
const NEEDS: Record<string, string> = {
  gsc: 'clicks or impressions',
  ga4: 'sessions or users',
  gbp: 'at least one of calls, direction requests, website clicks or bookings',
};

/** Where each hand-kept section's data lives, for the "add more" links. */
const DATA_PAGE: Record<string, (clientId: string) => string> = {
  gbp: id => `/clients/${id}/gbp`,
  rankings: id => `/clients/${id}/keywords`,
  ai_visibility: id => `/clients/${id}/ai-mentions-data`,
  links: id => `/clients/${id}/links`,
  work: id => `/clients/${id}/work`,
};

const KIND_LABEL: Record<Item['kind'], string> = { headline: 'Figures', summary: 'Summary', row: 'Rows' };

const COVER_MAX = 5 * 1024 * 1024;

/** Month columns for a combined report, one per cycle. */
const PERIOD_COLS: Record<string, [string, string, Format][]> = {
  gsc: [['clicks', 'Clicks', 'int'], ['impressions', 'Impressions', 'int'], ['ctr', 'CTR', 'percent'], ['position', 'Avg. position', 'decimal']],
  ga4: [['sessions', 'Sessions', 'int'], ['users', 'Users', 'int'], ['engaged_sessions', 'Engaged', 'int'], ['conversions', 'Conversions', 'int']],
  gbp: [['calls', 'Calls', 'int'], ['direction_requests', 'Directions', 'int'], ['website_clicks', 'Website clicks', 'int'], ['bookings', 'Bookings', 'int']],
};

const COMBINED_NOTE: Record<string, string> = {
  gsc: 'Clicks and impressions add up across the months; CTR and position are recalculated from them, not averaged.',
  ga4: 'Sessions, engaged sessions and conversions add up; users show the average month, since the same person visits in several months.',
  gbp: 'Business Profile figures add up across the months.',
};

const fmtCell = (v: any, f: Format): string => {
  if (v === undefined || v === null || v === '') return '—';
  const n = Number(v) || 0;
  if (f === 'percent') return `${(n * 100).toFixed(2)}%`;
  if (f === 'decimal') return n.toFixed(1);
  return Math.round(n).toLocaleString();
};

/** "September 2026" → "Sep'26", the month header the upload sheets use. */
const monthCol = (label: string): string | null => {
  const d = new Date(`1 ${label}`);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.toLocaleString('en', { month: 'short' })}'${String(d.getFullYear()).slice(2)}`;
};

/* Values are held as the text a person types. Percentages are typed as
   percent ("0.13") but the snapshot stores fractions (0.0013). */
const toText = (i: Item): string => {
  if (i.format === 'bool') return i.value ? 'true' : 'false';
  if (i.value === null || i.value === undefined) return '';
  const n = Number(i.value) || 0;
  return i.format === 'percent' ? String(parseFloat((n * 100).toFixed(4))) : String(n);
};

const fromText = (i: Item, text: string): number | boolean | null => {
  if (i.format === 'bool') return text === 'true';
  if (text.trim() === '') return null;
  const n = Number(text);
  if (!Number.isFinite(n) || n < 0) return null;
  return i.format === 'percent' ? n / 100 : n;
};

function display(text: string, format: Format): string {
  if (format === 'bool') return text === 'true' ? 'Mentioned' : 'Not found';
  if (format === 'none' || text.trim() === '') return '—';
  const n = Number(text) || 0;
  if (format === 'percent') return `${n.toFixed(2)}%`;
  if (format === 'decimal') return n.toFixed(1);
  if (Math.abs(n) >= 10000) {
    return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(n);
  }
  return Math.round(n).toLocaleString();
}

const ReportBuilder: React.FC = () => {
  const { clientId, snapshotId } = useParams<{ clientId: string; snapshotId: string }>();
  const navigate = useNavigate();
  const base = `/clients/${clientId}/reports/${snapshotId}`;

  const [loading, setLoading] = useState(true);
  const [client, setClient] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [connections, setConnections] = useState<any[]>([]);
  const [editable, setEditable] = useState(true);

  const [sections, setSections] = useState<Section[]>([]);
  const [available, setAvailable] = useState<Record<string, boolean>>({});
  const [sectionOn, setSectionOn] = useState<Record<string, boolean>>({});
  const [items, setItems] = useState<Item[]>([]);
  const [itemOn, setItemOn] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);

  // Headings, subtitles and the cover's brand line
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [copy, setCopy] = useState<Copy>(EMPTY_COPY);
  const [brandDefault, setBrandDefault] = useState('Monthly SEO Report');
  const savedCopy = useRef(JSON.stringify(EMPTY_COPY));

  // Cover screenshot
  const [hasCover, setHasCover] = useState(false);
  const [coverUrl, setCoverUrl] = useState<string | null>(null);
  const [coverBusy, setCoverBusy] = useState(false);

  const [fetching, setFetching] = useState<string | null>(null);

  // The months this report covers
  const [period, setPeriod] = useState<Period | null>(null);
  const [periods, setPeriods] = useState<PeriodRow[]>([]);
  const [showPeriod, setShowPeriod] = useState(false);
  const [periodBusy, setPeriodBusy] = useState(false);

  // Figures whose edit should also correct the saved data they came from
  const [writeBack, setWriteBack] = useState<Set<string>>(() => new Set());

  // A section busy reading an uploaded sheet
  const [sectionBusy, setSectionBusy] = useState<{ key: string; text: string } | null>(null);

  const [instruction, setInstruction] = useState('');
  const [asking, setAsking] = useState(false);
  const [aiNote, setAiNote] = useState<{ text: string; ignored: boolean } | null>(null);

  const [step, setStep] = useState(0);
  const [visited, setVisited] = useState<Set<number>>(() => new Set([0]));
  const [saveState, setSaveState] = useState<{ text: string; err?: boolean }>({ text: '' });
  const [finishing, setFinishing] = useState(false);
  const [leaveTo, setLeaveTo] = useState<string | null>(null);

  /** Take a composer payload as the new truth for every figure and tick. */
  const applyComposer = (d: any) => {
    setEditable(d.editable !== false);
    setSections(d.sections || []);
    setAvailable(d.available || {});
    setSectionOn(d.selectedSections || {});
    setItems(d.items || []);
    setItemOn(d.selectedItems || {});
    // In a provider section with nothing in it yet, zero only means "not
    // entered": show the field empty so typing 7 gives 7, not 07.
    const avail = d.available || {};
    const text = Object.fromEntries((d.items || []).map((i: Item) => {
      const t = toText(i);
      return [i.id, i.section in PROVIDER_NAME && !avail[i.section] && Number(t) === 0 ? '' : t];
    }));
    setValues(text);
    setSaved(text);
    setEditing(null);
    if (d.copyHeadings) setHeadings(d.copyHeadings);
    if (d.brandLineDefault) setBrandDefault(d.brandLineDefault);
    const c: Copy = { ...EMPTY_COPY, ...(d.copy || {}) };
    setCopy(c);
    savedCopy.current = JSON.stringify(c);
    setHasCover(!!d.hasCover);
    setPeriod(d.period || null);
    setPeriods(d.periods || []);
    setWriteBack(new Set());
  };

  const loadCover = useCallback(async () => {
    try {
      const res = await api.get(`${base}/cover`, { responseType: 'blob', skipErrorToast: true } as any);
      setCoverUrl(URL.createObjectURL(res.data));
    } catch (e) {
      setCoverUrl(null);
    }
  }, [base]);

  // Release the previous preview whenever it is replaced, and on the way out.
  useEffect(() => () => { if (coverUrl) URL.revokeObjectURL(coverUrl); }, [coverUrl]);

  useEffect(() => {
    if (!clientId || !snapshotId) return;
    let cancelled = false;
    Promise.all([
      api.get(`/clients/${clientId}`),
      api.get(base),
      api.get(`${base}/composer`),
      api.get(`/clients/${clientId}/connections`).catch(() => ({ data: [] })),
    ]).then(([c, r, comp, conn]) => {
      if (cancelled) return;
      setClient(c.data);
      setReport(r.data);
      setConnections(conn.data || []);
      applyComposer(comp.data || {});
      if (comp.data?.hasCover) loadCover();
    }).catch(() => {
      // Handled by global interceptor
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [clientId, snapshotId]);

  const bySection = useMemo(() => {
    const map: Record<string, Item[]> = {};
    for (const i of items) (map[i.section] ||= []).push(i);
    return map;
  }, [items]);

  const isProvider = (key: string) => key in PROVIDER_NAME;
  const connected = (key: string) => connections.some(c => c.provider === key && c.status === 'connected');
  /** A provider section with no data becomes usable once figures are typed in. */
  const hasData = (key: string) =>
    !!available[key] || (isProvider(key) && (bySection[key] || []).some(i => Number(values[i.id]) > 0));

  // ── Saving: queued one at a time, like the reference builder's autosave ──
  const dirty = useRef(false);
  const latest = useRef({ items, values, saved, sectionOn, itemOn, copy, writeBack });
  latest.current = { items, values, saved, sectionOn, itemOn, copy, writeBack };
  const chain = useRef<Promise<unknown>>(Promise.resolve());

  const persist = useCallback(async () => {
    if (!dirty.current) return;
    dirty.current = false;
    const { items, values, saved, sectionOn, itemOn, copy, writeBack } = latest.current;
    setSaveState({ text: 'Saving…' });
    try {
      const edits: Record<string, number | boolean> = {};
      const sent: Record<string, string> = {};
      for (const i of items) {
        if (!i.editable || values[i.id] === saved[i.id]) continue;
        const next = fromText(i, values[i.id] ?? '');
        if (next === null) continue;
        edits[i.id] = next;
        sent[i.id] = values[i.id];
      }
      // Figures first: a typed-in section only counts as having data once its
      // numbers are stored, and the server checks that before switching it on.
      if (Object.keys(edits).length > 0) {
        const alsoSaved = Object.keys(edits).filter(id => writeBack.has(id));
        const res = await api.put(`${base}/values`, { edits, writeBack: alsoSaved });
        setSaved(prev => ({ ...prev, ...sent }));
        if (alsoSaved.length > 0) {
          setWriteBack(prev => {
            const next = new Set(prev);
            alsoSaved.forEach(id => next.delete(id));
            return next;
          });
          const done = (res.data?.wroteBack || []).length;
          if (done) toast.success(`Saved data updated for ${done} figure${done === 1 ? '' : 's'}.`);
        }
      }
      const res = await api.put(`${base}/composer`, { sections: sectionOn, items: itemOn });
      if (res.data?.selectedSections) setSectionOn(res.data.selectedSections);

      const copyJson = JSON.stringify(copy);
      if (copyJson !== savedCopy.current) {
        await api.put(`${base}/copy`, copy);
        savedCopy.current = copyJson;
      }

      const t = new Date();
      setSaveState({ text: `Saved ✓ ${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}` });
    } catch (e) {
      dirty.current = true;
      setSaveState({ text: 'Could not save — check connection', err: true });
      throw e;
    }
  }, [base]);

  const queueSave = useCallback(() => {
    const run = chain.current.then(persist, persist);
    chain.current = run.catch(() => {});
    return run;
  }, [persist]);

  // ── Leaving with unsaved changes ──
  useEffect(() => {
    // Closing or reloading the tab: the browser's own prompt.
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!dirty.current) return;
      e.preventDefault();
      e.returnValue = '';
    };
    // Any link inside the app — sidebar, breadcrumbs, "Connect it" — is held
    // until the person chooses what to do with their changes.
    const onClick = (e: MouseEvent) => {
      if (!dirty.current || e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as HTMLElement | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (!a || a.target === '_blank' || a.hasAttribute('download')) return;
      const url = new URL(a.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      e.preventDefault();
      e.stopPropagation();
      setLeaveTo(url.pathname + url.search + url.hash);
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    document.addEventListener('click', onClick, true);
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload);
      document.removeEventListener('click', onClick, true);
    };
  }, []);

  const saveAndLeave = async () => {
    const to = leaveTo;
    if (!to) return;
    try { await queueSave(); } catch (e) { return; }
    setLeaveTo(null);
    navigate(to);
  };

  const leaveWithoutSaving = () => {
    const to = leaveTo;
    dirty.current = false;
    setLeaveTo(null);
    if (to) navigate(to);
  };

  // ── Edits ──
  const autoIncluded = useRef<Set<string>>(new Set());

  const toggleSection = (key: string) => {
    if (!editable || !hasData(key)) return;
    setSectionOn(s => ({ ...s, [key]: !s[key] }));
    dirty.current = true;
    setAiNote(null);
  };

  const toggleItem = (id: string) => {
    if (!editable) return;
    setItemOn(s => ({ ...s, [id]: s[id] === false }));
    dirty.current = true;
    setAiNote(null);
  };

  const setAllIn = (key: string, on: boolean) => {
    if (!editable) return;
    setItemOn(s => {
      const next = { ...s };
      for (const i of bySection[key] || []) if (i.kind === 'row') next[i.id] = on;
      return next;
    });
    dirty.current = true;
    setAiNote(null);
  };

  const setValue = (id: string, text: string) => {
    setValues(v => ({ ...v, [id]: text }));
    dirty.current = true;
    // Typing the first figure into an empty, unconnected section switches it on —
    // once. After that the tick is the person's to change.
    const item = items.find(x => x.id === id);
    if (item && isProvider(item.section) && !available[item.section]
        && Number(text) > 0 && !autoIncluded.current.has(item.section)) {
      autoIncluded.current.add(item.section);
      setSectionOn(s => ({ ...s, [item.section]: true }));
    }
  };

  const setWB = (id: string, on: boolean) => {
    setWriteBack(prev => {
      const next = new Set(prev);
      if (on) next.add(id); else next.delete(id);
      return next;
    });
    dirty.current = true;
  };

  /** Upload a sheet for one section, then re-read that section from saved data. */
  const uploadSheet = async (key: string, spec: UploadSpec, file: File) => {
    setSectionBusy({ key, text: 'Reading the sheet and updating this section…' });
    // Save first — the refreshed section replaces what is on screen.
    try { await queueSave(); } catch (e) { setSectionBusy(null); return; }
    try {
      const fd = new FormData();
      fd.append('file', file);
      await api.post(spec.endpoint, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      const res = await api.post(`${base}/refresh/${key}`);
      applyComposer(res.data || {});
      toast.success('Sheet added — this section is updated.');
    } catch (err: any) {
      // Handled by global interceptor
    }
    setSectionBusy(null);
  };

  const uploadShots = async (files: FileList) => {
    if (files.length === 0) return;
    setSectionBusy({ key: 'work', text: 'Adding the screenshots…' });
    try { await queueSave(); } catch (e) { setSectionBusy(null); return; }
    try {
      const fd = new FormData();
      fd.append('month', `${(period?.end || new Date().toISOString()).slice(0, 7)}-01`);
      Array.from(files).forEach(f => fd.append('files', f));
      await api.post(`/clients/${clientId}/screenshots/bulk`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      const res = await api.post(`${base}/refresh/work`);
      applyComposer(res.data || {});
      toast.success(`${files.length} screenshot${files.length === 1 ? '' : 's'} added.`);
    } catch (err: any) {
      // Handled by global interceptor
    }
    setSectionBusy(null);
  };

  const downloadSample = (key: string, spec: UploadSpec) => {
    const blob = new Blob([`${spec.columns}\n${spec.sample}\n`], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${key}-sample.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  /** Recalculate the report for a different number of months — nothing is pulled. */
  const changePeriod = async (months: number) => {
    setPeriodBusy(true);
    try { await queueSave(); } catch (e) { setPeriodBusy(false); return; }
    try {
      const res = await api.post(`${base}/period`, { months });
      applyComposer(res.data || {});
      setShowPeriod(false);
      toast.success(`The report now covers ${res.data?.period?.label || `${months} months`}.`);
    } catch (err: any) {
      // Handled by global interceptor
    }
    setPeriodBusy(false);
  };

  const setBrand = (text: string) => { setCopy(c => ({ ...c, brand_line: text })); dirty.current = true; };
  const setTitle = (key: string, text: string) => {
    setCopy(c => ({ ...c, titles: { ...c.titles, [key]: text } }));
    dirty.current = true;
  };
  const setSubtitle = (key: string, text: string) => {
    setCopy(c => ({ ...c, subtitles: { ...c.subtitles, [key]: text } }));
    dirty.current = true;
  };

  const askAi = async () => {
    if (!instruction.trim()) return;
    setAsking(true);
    setAiNote(null);
    try {
      const res = await api.post(`${base}/composer/suggest`, { instruction });
      setSectionOn(res.data.sections || {});
      setItemOn(res.data.items || {});
      dirty.current = true;
      setAiNote({ text: res.data.note || '', ignored: !!res.data.ignored });
    } catch (err: any) {
      // Handled by global interceptor
    }
    setAsking(false);
  };

  /** Replace one source's figures with fresh ones from Google, for this report's window. */
  const fetchFrom = async (key: string) => {
    setFetching(key);
    // Save first, so nothing typed elsewhere is lost when the payload comes back.
    try { await queueSave(); } catch (e) { setFetching(null); return; }
    try {
      const res = await api.post(`${base}/fetch/${key}`);
      applyComposer(res.data || {});
      toast.success(`Fresh ${PROVIDER_NAME[key]} figures fetched.`);
    } catch (err: any) {
      // Handled by global interceptor
    }
    setFetching(null);
  };

  const uploadCover = async (file: File) => {
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) { toast.error('Use a PNG, JPEG or WebP image.'); return; }
    if (file.size > COVER_MAX) { toast.error('The screenshot must be 5 MB or smaller.'); return; }
    setCoverBusy(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      await api.put(`${base}/cover`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setHasCover(true);
      await loadCover();
      toast.success('Cover screenshot added.');
    } catch (err: any) {
      // Handled by global interceptor
    }
    setCoverBusy(false);
  };

  const removeCover = async () => {
    setCoverBusy(true);
    try {
      await api.delete(`${base}/cover`);
      setHasCover(false);
      setCoverUrl(null);
    } catch (err: any) {
      // Handled by global interceptor
    }
    setCoverBusy(false);
  };

  // ── Steps ──
  const steps = useMemo<Step[]>(() => [
    { key: 'basics', kind: 'basics', label: 'Report basics' },
    { key: 'overview', kind: 'overview', label: 'Sections to include' },
    ...sections.map(s => ({ key: s.key, kind: 'section' as const, label: s.label })),
    { key: 'review', kind: 'review', label: 'Review & generate' },
  ], [sections]);

  const go = (i: number) => {
    if (i < 0 || i >= steps.length || i === step) return;
    setEditing(null);
    if (editable) queueSave().catch(() => {});
    setStep(i);
    setVisited(v => new Set(v).add(i));
    document.querySelector('.app-content')?.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const goTo = (key: string) => go(steps.findIndex(s => s.key === key));

  const reportPage = `/admin/clients/${clientId}/reports/${snapshotId}`;

  const finish = async () => {
    if (!editable) { navigate(reportPage); return; }
    setFinishing(true);
    // Always write once, so even an untouched draft stores its selection.
    dirty.current = true;
    try {
      await queueSave();
      toast.success('Report generated.');
      navigate(reportPage);
    } catch (err: any) {
      // Handled by global interceptor
    }
    setFinishing(false);
  };

  const leave = async () => {
    if (editable) {
      try { await queueSave(); } catch (e) { return; }
    }
    navigate(`/admin/clients/${clientId}`);
  };

  if (loading) return <PageSkeleton cards={2} header={true} />;

  if (!client || sections.length === 0) {
    return (
      <div className="page-card" style={{ margin: '40px auto', maxWidth: 560 }}>
        <div className="empty-state">
          <h3>This report could not be opened</h3>
          <Link to={`/admin/clients/${clientId}`} className="btn btn-secondary" style={{ marginTop: 12 }}>Back to client</Link>
        </div>
      </div>
    );
  }

  const periodLabel = period?.label || (report?.end_date
    ? new Date(report.end_date).toLocaleDateString('default', { month: 'long', year: 'numeric' })
    : '');
  const monthCols = (period?.labels || []).map(monthCol).filter(Boolean) as string[];
  const lastCol = monthCols[monthCols.length - 1] || "Sep'26";
  const sampleDay = period?.end || new Date().toISOString().slice(0, 10);
  const sectionsOnCount = sections.filter(s => sectionOn[s.key]).length;
  const customHeadings = Object.keys(copy.titles).filter(k => copy.titles[k]?.trim()).length
    + Object.keys(copy.subtitles).filter(k => copy.subtitles[k]?.trim()).length;
  const cur = steps[step];

  // ── Pieces (plain render functions, not components — a component defined
  //    here would remount on every keystroke and drop the input's focus) ──
  const valueInput = (i: Item, autoFocus: boolean, wide = false) => (
    i.format === 'bool' ? (
      <select
        className="form-select metric-input"
        value={values[i.id] === 'true' ? 'true' : 'false'}
        autoFocus={autoFocus}
        disabled={!editable}
        onChange={e => setValue(i.id, e.target.value)}
      >
        <option value="true">Mentioned</option>
        <option value="false">Not found</option>
      </select>
    ) : (
      <input
        className={`form-input metric-input ${wide ? 'wide' : ''}`}
        type="number"
        inputMode="decimal"
        min="0"
        step={i.format === 'int' ? '1' : '0.01'}
        placeholder="0"
        value={values[i.id] ?? ''}
        autoFocus={autoFocus}
        disabled={!editable}
        aria-label={i.label}
        onChange={e => setValue(i.id, e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Escape') setEditing(null); }}
      />
    )
  );

  const card = (i: Item, isRow = false) => {
    const shown = itemOn[i.id] !== false;
    const isEditing = editing === i.id && i.editable && editable;
    return (
      <div key={i.id} className={`metric-card ${shown ? '' : 'off'} ${isRow ? 'is-row' : ''} ${isEditing ? 'editing' : ''}`}>
        <label className="metric-card-head">
          <input type="checkbox" checked={shown} disabled={!editable} onChange={() => toggleItem(i.id)} />
          <span title={i.label}>{i.label}</span>
        </label>
        <div className="metric-card-value">
          {isEditing ? (
            <>
              {valueInput(i, true)}
              <button className="metric-pencil done" onClick={() => setEditing(null)} aria-label="Done">
                <Check size={13} />
              </button>
            </>
          ) : (
            <>
              <span className="metric-number">
                {display(values[i.id] ?? '', i.format)}
                {i.unit === 'position' && <small> pos</small>}
              </span>
              {i.editable && editable && (
                <button className="metric-pencil" onClick={() => setEditing(i.id)} aria-label={`Edit ${i.label}`}>
                  <Pencil size={12} />
                </button>
              )}
            </>
          )}
        </div>
        {isEditing
          ? writeBackChoice(i)
          : writeBack.has(i.id) && <span className="rb-wb-tag">Also updates saved data</span>}
      </div>
    );
  };

  /** A figure typed straight in — for sources with no connection to fill it. */
  const field = (i: Item) => (
    <div key={i.id} className={`rb-field ${itemOn[i.id] !== false ? '' : 'off'}`}>
      <label className="metric-card-head">
        <input type="checkbox" checked={itemOn[i.id] !== false} disabled={!editable} onChange={() => toggleItem(i.id)} />
        <span title={i.label}>{i.label}</span>
      </label>
      {valueInput(i, false, true)}
      {values[i.id] !== saved[i.id] && writeBackChoice(i)}
      {i.format === 'percent' && <div className="rb-field-unit">Percent — e.g. 2.4</div>}
      {i.id.endsWith('.position') && <div className="rb-field-unit">Average position — e.g. 18.5</div>}
    </div>
  );

  /** Where a changed figure applies: only this report, or the saved data too. */
  const writeBackChoice = (i: Item) => {
    if (!i.writable || !editable) return null;
    const on = writeBack.has(i.id);
    return (
      <div className="rb-wb" role="radiogroup" aria-label={`Where the change to ${i.label} applies`}>
        <button type="button" role="radio" aria-checked={!on} className={`rb-wb-opt ${on ? '' : 'on'}`} onClick={() => setWB(i.id, false)}>
          This report only
        </button>
        <button type="button" role="radio" aria-checked={on} className={`rb-wb-opt ${on ? 'on' : ''}`} onClick={() => setWB(i.id, true)}>
          Also update saved data
        </button>
      </div>
    );
  };

  /** Which sheet a section takes, when its data is entered by hand. */
  const uploadSpecFor = (key: string): UploadSpec | null => {
    const m = lastCol;
    switch (key) {
      case 'gsc':
        return connected('gsc') ? null : {
          title: 'Upload a Search Console sheet', hint: 'One row per day.',
          endpoint: `/clients/${clientId}/manual-gsc/upload_csv`,
          columns: 'date,clicks,impressions,ctr,position', sample: `${sampleDay},120,4500,0.027,12.4`,
        };
      case 'ga4':
        return connected('ga4') ? null : {
          title: 'Upload an Analytics sheet', hint: 'One row per day.',
          endpoint: `/clients/${clientId}/manual-ga4/upload_csv`,
          columns: 'date,sessions,users,engaged_sessions,conversions,revenue', sample: `${sampleDay},761,589,147,3,0`,
        };
      case 'gbp':
        return connected('gbp') ? null : {
          title: 'Upload a Business Profile sheet', hint: 'One row per month.',
          endpoint: `/clients/${clientId}/manual-gbp/upload_csv`,
          columns: 'Date,Impressions Desktop Maps,Impressions Desktop Search,Impressions Mobile Maps,Impressions Mobile Search,Calls,Direction Requests,Website Clicks,Bookings',
          sample: `${m},100,50,300,150,5,2,10,1`,
        };
      case 'rankings': {
        const cols = monthCols.length ? monthCols : [m];
        return {
          title: 'Upload keyword rankings', hint: 'One row per keyword, one column per month.',
          endpoint: `/clients/${clientId}/keywords/upload_csv`,
          columns: `Keyword,SV,Initial Ranking,${cols.join(',')}`,
          sample: `best seo agency,1900,24,${cols.map((_, n) => Math.max(1, 18 - n * 3)).join(',')}`,
          accept: '.csv,.xlsx',
        };
      }
      case 'ai_visibility':
        return {
          title: 'Upload AI prompt checks', hint: 'One row per prompt — Yes or No for each AI tool.',
          endpoint: `/clients/${clientId}/ai_mentions/upload_csv`,
          columns: 'Month,Prompts,ChatGPT,AI Overview,Google Gemini,Perplexity,Claude', sample: `${m},Best pizza in NY,Yes,No,Yes,Yes,No`,
        };
      case 'links':
        return {
          title: 'Upload links built', hint: 'One row per link.',
          endpoint: `/clients/${clientId}/links/upload_csv`,
          columns: 'Month,Activity Name,URL,Count', sample: `${m},Guest Post,https://example.com/article,1`,
        };
      case 'work':
        return {
          title: 'Upload work delivered', hint: 'One row per task.',
          endpoint: `/clients/${clientId}/work/upload_csv`,
          columns: 'Activity Type,Count,Notes', sample: 'Optimized Homepage,1,Updated meta titles',
        };
      default:
        return null;
    }
  };

  const uploadBox = (key: string) => {
    const spec = uploadSpecFor(key);
    if (!spec || !editable) return null;
    return (
      <div className="rb-upload">
        <div className="rb-upload-text">
          <Upload size={16} />
          <span>
            <strong>{spec.title}</strong>
            {spec.hint}{' '}
            {(() => {
              // A long header list wraps into noise; name a few, the sample has them all.
              const cols = spec.columns.split(',');
              return cols.length <= 5
                ? <>Columns: <code>{cols.join(', ')}</code></>
                : <span title={cols.join(', ')}>Columns: <code>{cols.slice(0, 3).join(', ')}</code> and {cols.length - 3} more — download the sample for the full layout.</span>;
            })()}
          </span>
        </div>
        <div className="rb-upload-actions">
          <button className="btn ghost btn-sm" onClick={() => downloadSample(key, spec)}>
            <Download size={13} /> Sample
          </button>
          {key === 'work' && (
            <label className={`btn btn-secondary btn-sm ${sectionBusy ? 'is-disabled' : ''}`}>
              <ImagePlus size={13} /> Add screenshots
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                multiple
                hidden
                disabled={!!sectionBusy}
                onChange={e => { const f = e.target.files; if (f) uploadShots(f); e.target.value = ''; }}
              />
            </label>
          )}
          <label className={`btn btn-primary btn-sm ${sectionBusy ? 'is-disabled' : ''}`}>
            <Upload size={13} /> Upload sheet
            <input
              type="file"
              accept={spec.accept || '.csv'}
              hidden
              disabled={!!sectionBusy}
              onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) uploadSheet(key, spec, f); }}
            />
          </label>
        </div>
      </div>
    );
  };

  /** Each month of a combined report, beside the combined figure. */
  const monthTable = (key: string) => {
    const cols = PERIOD_COLS[key];
    if (!cols || periods.length < 2) return null;
    return (
      <div className="rb-group">
        <div className="rb-group-label">Month by month</div>
        <div className="rb-month-table">
          <table>
            <thead>
              <tr><th>Month</th>{cols.map(([k, name]) => <th key={k}>{name}</th>)}</tr>
            </thead>
            <tbody>
              {periods.map(p => (
                <tr key={p.end}>
                  <td title={p.range}>{p.label}</td>
                  {cols.map(([k, , f]) => <td key={k}>{fmtCell(p[key]?.[k], f)}</td>)}
                </tr>
              ))}
              <tr className="total">
                <td>Combined</td>
                {cols.map(([k, , f]) => <td key={k}>{display(values[`${key}.${k}`] ?? '', f)}</td>)}
              </tr>
            </tbody>
          </table>
        </div>
        <p className="rb-note">{COMBINED_NOTE[key]}</p>
      </div>
    );
  };

  const includeToggle = (key: string) => {
    const has = hasData(key);
    const on = !!sectionOn[key];
    return (
      <label className={`rb-include ${on ? 'on' : ''} ${has && editable ? '' : 'disabled'}`}>
        <input type="checkbox" checked={on} disabled={!has || !editable} onChange={() => toggleSection(key)} />
        Include in report
      </label>
    );
  };

  /** Title + subtitle for each heading this step prints. */
  const headingEditor = (group: string) => {
    const list = headings.filter(h => h.section === group);
    if (list.length === 0) return null;
    return (
      <div className="rb-group">
        <div className="rb-group-label"><span className="rb-inline"><Type size={12} /> Headings in the report</span></div>
        <div className="rb-copy">
          {list.map(h => (
            <div key={h.key} className="rb-copy-row">
              {list.length > 1 && <div className="rb-copy-caption">{h.title.replace('{period}', periodLabel)}</div>}
              <label className="rb-copy-field">
                <span>Title</span>
                <input
                  className="form-input"
                  maxLength={120}
                  placeholder={h.title}
                  value={copy.titles[h.key] ?? ''}
                  disabled={!editable}
                  onChange={e => setTitle(h.key, e.target.value)}
                />
              </label>
              <label className="rb-copy-field">
                <span>Subtitle <em>optional</em></span>
                <input
                  className="form-input"
                  maxLength={280}
                  placeholder="A supporting line under the title"
                  value={copy.subtitles[h.key] ?? ''}
                  disabled={!editable}
                  onChange={e => setSubtitle(h.key, e.target.value)}
                />
              </label>
            </div>
          ))}
        </div>
        <p className="rb-note">
          A blank title keeps the default shown in grey. Write {'{period}'} for the report month
          and {'{client}'} for the client's name.
        </p>
      </div>
    );
  };

  const fetchButton = (key: string) => {
    if (!FETCHABLE[key] || !editable) return null;
    const live = connected(key);
    return (
      <button
        className="btn btn-secondary btn-sm rb-fetch"
        onClick={() => fetchFrom(key)}
        disabled={!!fetching || !live}
        title={live ? `Replace these figures with fresh ones from ${PROVIDER_NAME[key]}` : 'Connect it first'}
      >
        {fetching === key
          ? <><Loader2 size={13} className="spin" /> Fetching…</>
          : <><RefreshCw size={13} /> Fetch from {FETCHABLE[key]}</>}
      </button>
    );
  };

  const renderBasics = () => (
    <>
      <div className="rb-panel-head">
        <div>
          <h2 className="rb-panel-title"><SlidersHorizontal size={18} /> Report basics</h2>
          <p className="rb-panel-sub">
            The cover and the opening page. Everything here is optional — blank fields keep the defaults.
          </p>
        </div>
      </div>

      {period && (
        <div className="rb-period">
          <div className="rb-period-main">
            <CalendarRange size={18} />
            <div>
              <div className="rb-period-title">
                {period.label}{period.months > 1 ? ` · ${period.months} months combined` : ''}
              </div>
              <div className="rb-period-sub">
                {period.range || ''}{period.range ? ' · ' : ''}
                {period.compare?.hasData
                  ? `compared with ${period.compare.range || 'the period before'}`
                  : 'no earlier period saved, so figures are shown without a comparison'}
              </div>
            </div>
          </div>
          {editable && (
            <button className="btn btn-secondary btn-sm" onClick={() => setShowPeriod(true)} disabled={periodBusy}>
              <CalendarRange size={14} /> Change period
            </button>
          )}
        </div>
      )}

      <div className="rb-group">
        <div className="rb-group-label">Brand line</div>
        <input
          className="form-input rb-brand"
          maxLength={80}
          placeholder={brandDefault}
          value={copy.brand_line}
          disabled={!editable}
          onChange={e => setBrand(e.target.value)}
        />
        <p className="rb-note">The small gold label above the title on the cover.</p>
      </div>

      <div className="rb-group">
        <div className="rb-group-label">Website homepage screenshot</div>
        <div className="rb-cover">
          {coverUrl ? (
            <div className="rb-cover-frame">
              <div className="rb-cover-bar"><i /><i /><i /><span>{client?.domain}</span></div>
              <img src={coverUrl} alt="Cover screenshot" />
            </div>
          ) : (
            <div className="rb-cover-empty"><ImagePlus size={22} /><span>No screenshot yet</span></div>
          )}
          <div className="rb-cover-actions">
            <p className="rb-note" style={{ marginTop: 0 }}>
              Shown on the cover inside a browser frame, beside the title. A clean capture of the
              homepage works best. PNG, JPEG or WebP, up to 5 MB.
            </p>
            {editable && (
              <div className="rb-cover-buttons">
                <label className={`btn btn-secondary btn-sm ${coverBusy ? 'is-disabled' : ''}`}>
                  {coverBusy ? <Loader2 size={14} className="spin" /> : <ImagePlus size={14} />}
                  {hasCover ? 'Replace' : 'Upload screenshot'}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    hidden
                    disabled={coverBusy}
                    onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) uploadCover(f); }}
                  />
                </label>
                {hasCover && (
                  <button className="btn ghost btn-sm" onClick={removeCover} disabled={coverBusy}>
                    <Trash2 size={14} /> Remove
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {headingEditor('basics')}
    </>
  );

  const renderOverview = () => (
    <>
      <div className="rb-panel-head">
        <div>
          <h2 className="rb-panel-title"><ListChecks size={18} /> Sections to include</h2>
          <p className="rb-panel-sub">
            Unticked sections are left out of the report and the PDF, even when they have data.
            Each section has its own step where every figure can be checked and corrected.
          </p>
        </div>
      </div>

      {editable && (
        <div className="composer-ai" style={{ marginBottom: 22 }}>
          <label className="composer-ai-label" htmlFor="rb-instruction">
            <Sparkles size={14} /> Describe what to include
          </label>
          <div className="composer-ai-row">
            <input
              id="rb-instruction"
              className="form-input"
              placeholder="e.g. hide average CTR and drop the business profile section"
              value={instruction}
              onChange={e => setInstruction(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); askAi(); } }}
            />
            <button className="btn btn-secondary" onClick={askAi} disabled={asking || !instruction.trim()}>
              {asking ? <><Loader2 size={14} className="spin" /> Reading…</> : 'Apply'}
            </button>
          </div>
          {aiNote && (
            <div className={`composer-ai-note ${aiNote.ignored ? 'ignored' : ''}`}>
              <Info size={13} />
              {aiNote.ignored
                ? (aiNote.text || 'That did not look like a report instruction, so nothing changed.')
                : (aiNote.text || 'Selection updated.')}
            </div>
          )}
        </div>
      )}

      <div className="rb-group-label">Sections · {sectionsOnCount} of {sections.length} included</div>
      <div className="rb-toggle-grid">
        {sections.map(sec => {
          const has = hasData(sec.key);
          const on = !!sectionOn[sec.key];
          const list = bySection[sec.key] || [];
          const shown = list.filter(i => itemOn[i.id] !== false).length;
          const src = isProvider(sec.key) ? (connected(sec.key) ? 'Auto from Google' : 'Manual entry') : 'From your data';
          return (
            <label key={sec.key} className={`rb-toggle ${on ? 'on' : ''} ${has ? '' : 'disabled'}`}>
              <input type="checkbox" checked={on} disabled={!has || !editable} onChange={() => toggleSection(sec.key)} />
              <span className="rb-toggle-text">
                <span className="rb-toggle-title">{SECTION_ICON[sec.key]} {sec.label}</span>
                <span className="rb-toggle-sub">
                  {has
                    ? `${shown} of ${list.length} shown · ${src}`
                    : isProvider(sec.key) ? 'No figures yet — enter them on its step' : 'Nothing recorded this period'}
                </span>
              </span>
              <button type="button" className="rb-jump" onClick={e => { e.preventDefault(); goTo(sec.key); }}>Edit</button>
            </label>
          );
        })}
      </div>

      <div className="rb-group-label" style={{ marginTop: 28 }}>Executive summary — KPI cards</div>
      <p className="rb-panel-sub" style={{ margin: '0 0 12px' }}>
        Tick the headline figures the client should see. A card still needs a value to appear —
        this only hides the ones you don't want.
      </p>
      {(['gsc', 'ga4', 'gbp'] as const).map(key => {
        const list = (bySection[key] || []).filter(i => i.kind === 'headline');
        if (list.length === 0) return null;
        return (
          <div key={key} style={{ marginBottom: 14 }}>
            <div className="composer-metric-label">{SECTION_ICON[key]} {PROVIDER_NAME[key]}</div>
            <div className="rb-toggle-grid">
              {list.map(i => (
                <label key={i.id} className={`rb-toggle ${itemOn[i.id] !== false ? 'on' : ''} ${sectionOn[key] ? '' : 'muted'}`}>
                  <input type="checkbox" checked={itemOn[i.id] !== false} disabled={!editable} onChange={() => toggleItem(i.id)} />
                  <span className="rb-toggle-text">
                    <span className="rb-toggle-title">{i.label}</span>
                    <span className="rb-toggle-sub">{display(values[i.id] ?? '', i.format)}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
        );
      })}
    </>
  );

  const renderSection = (key: string) => {
    const sec = sections.find(s => s.key === key);
    if (!sec) return null;
    const list = bySection[key] || [];
    const on = !!sectionOn[key];
    const provider = isProvider(key);
    const live = provider && connected(key);
    const typedIn = provider && !live;
    const dataPage = DATA_PAGE[key] && clientId ? DATA_PAGE[key](clientId) : null;
    const rows = list.filter(i => i.kind === 'row');

    return (
      <>
        <div className="rb-panel-head">
          <div>
            <h2 className="rb-panel-title">{SECTION_ICON[key]} {sec.label}</h2>
            <p className="rb-panel-sub">{SECTION_SUB[key]}</p>
          </div>
          {includeToggle(key)}
        </div>

        {live ? (
          <div className="rb-source auto">
            <Plug size={15} />
            <span>
              <strong>Auto-filled from {PROVIDER_NAME[key]}.</strong> Pulled from the connected account
              for this period. Every figure stays editable with the pencil
              {FETCHABLE[key] ? ' — fetch again to replace them with the latest.' : '.'}
            </span>
            {fetchButton(key)}
          </div>
        ) : typedIn ? (
          <div className="rb-source manual">
            <Pencil size={15} />
            <span>
              <strong>{PROVIDER_NAME[key]} isn't connected</strong>, so enter this period's figures by hand.{' '}
              {key === 'gbp'
                ? <>Figures kept under <Link to={dataPage || '#'}>GBP Data</Link> are filled in already.</>
                : <><Link to={`/admin/clients/${clientId}/connections`}>Connect it</Link> to fetch them automatically.</>}
            </span>
            {fetchButton(key)}
          </div>
        ) : (
          <div className="rb-source">
            <Info size={15} />
            <span>
              Taken from what's recorded{dataPage ? <> under <Link to={dataPage}>{sec.label}</Link></> : null} for this period.
              Untick anything the client shouldn't see — every figure can be corrected with the pencil.
            </span>
          </div>
        )}

        {uploadBox(key)}

        {!provider && list.length === 0 ? (
          <div className="rb-empty">
            Nothing recorded for {sec.label} in this period yet{editable ? ' — upload a sheet above to add it.' : '.'}
          </div>
        ) : (
          <div className={`rb-body ${on ? '' : 'off'}`}>
            {(['headline', 'summary'] as const).map(kind => {
              const group = list.filter(i => i.kind === kind);
              if (group.length === 0) return null;
              return (
                <div key={kind} className="rb-group">
                  {list.some(i => i.kind !== kind) && <div className="rb-group-label">{KIND_LABEL[kind]}</div>}
                  {typedIn && kind === 'headline'
                    ? <div className="rb-fields">{group.map(field)}</div>
                    : <div className="metric-grid">{group.map(i => card(i))}</div>}
                </div>
              );
            })}

            {typedIn && !hasData(key) && (
              <p className="rb-hint">Enter {NEEDS[key]}, or upload a sheet, to be able to include this section.</p>
            )}

            {monthTable(key)}

            {rows.length > 0 && (
              <div className="rb-group">
                <div className="rb-group-label">
                  <span>{KIND_LABEL.row} · {rows.filter(i => itemOn[i.id] !== false).length} of {rows.length} shown</span>
                  {editable && (
                    <span className="composer-bulk" style={{ margin: 0 }}>
                      <button className="btn ghost btn-sm" onClick={() => setAllIn(key, true)}>Select all</button>
                      <button className="btn ghost btn-sm" onClick={() => setAllIn(key, false)}>Clear all</button>
                    </span>
                  )}
                </div>
                <div className="metric-rows">{rows.map(i => card(i, true))}</div>
              </div>
            )}
          </div>
        )}

        {headingEditor(key)}
      </>
    );
  };

  const renderReview = () => (
    <>
      <div className="rb-panel-head">
        <div>
          <h2 className="rb-panel-title"><FileText size={18} /> Review &amp; generate</h2>
          <p className="rb-panel-sub">
            This is what the report will contain. Go back to any step to change it — nothing is
            final until the report is published.
          </p>
        </div>
      </div>
      <div className="rb-review">
        <div className="rb-review-row">
          <span className="rb-review-name"><SlidersHorizontal size={15} /> Report basics</span>
          <span className="rb-review-meta">
            {copy.brand_line.trim() || brandDefault} · {hasCover ? 'Cover screenshot added' : 'No cover screenshot'}
            {customHeadings > 0 ? ` · ${customHeadings} custom heading${customHeadings === 1 ? '' : 's'}` : ''}
          </span>
          <button type="button" className="rb-jump" onClick={() => goTo('basics')}>Edit</button>
        </div>
        {sections.map(sec => {
          const on = !!sectionOn[sec.key];
          const list = bySection[sec.key] || [];
          const shown = list.filter(i => itemOn[i.id] !== false).length;
          const src = isProvider(sec.key) ? (connected(sec.key) ? 'Auto from Google' : 'Entered by hand') : 'From your data';
          return (
            <div key={sec.key} className={`rb-review-row ${on ? '' : 'off'}`}>
              <span className="rb-review-name">{SECTION_ICON[sec.key]} {sec.label}</span>
              <span className="rb-review-meta">
                {on ? `${shown} of ${list.length} items · ${src}` : hasData(sec.key) ? 'Left out' : 'No data'}
              </span>
              <span className={`rb-pill ${on ? 'on' : ''}`}>{on ? 'Included' : 'Off'}</span>
              <button type="button" className="rb-jump" onClick={() => goTo(sec.key)}>Edit</button>
            </div>
          );
        })}
      </div>
      {sectionsOnCount === 0 && (
        <div className="notice notice-warning" style={{ marginTop: 14 }}>
          <p className="notice-body">Nothing is switched on — the report would only carry its cover and summary.</p>
        </div>
      )}
    </>
  );

  return (
    <div className="rb">
      <PageHeader
        title="Build the report"
        subtitle={`${client?.name}${periodLabel ? ` · ${periodLabel}` : ''} — choose what goes in and check the figures, then generate.`}
        breadcrumbs={[
          { label: 'Home', href: '/admin/clients' },
          { label: client?.name || 'Client', href: `/admin/clients/${clientId}` },
          { label: 'Report builder' },
        ]}
      />

      {!editable && (
        <div className="notice notice-warning" style={{ marginBottom: 16 }}>
          <p className="notice-body">This report is published, so it can be looked through here but not changed.</p>
        </div>
      )}

      <div className="rb-shell">
        <aside className="rb-nav" aria-label="Report builder steps">
          <div className="rb-tablist" role="tablist">
            {steps.map((s, i) => {
              const done = visited.has(i) && i !== step;
              return (
                <button
                  key={s.key}
                  type="button"
                  role="tab"
                  aria-selected={i === step}
                  className={`rb-tab ${i === step ? 'active' : ''} ${done ? 'done' : ''}`}
                  onClick={() => go(i)}
                >
                  <span className="rb-tab-num">{done ? <Check size={13} /> : i + 1}</span>
                  <span className="rb-tab-label">{s.label}</span>
                  {s.kind === 'section' && !sectionOn[s.key] && <span className="rb-tab-state">Off</span>}
                </button>
              );
            })}
          </div>
          <div className="rb-progress">
            <div className="rb-progress-track">
              <div className="rb-progress-fill" style={{ width: `${Math.round((visited.size / steps.length) * 100)}%` }} />
            </div>
            <div className="rb-progress-text">{visited.size} / {steps.length} steps reviewed</div>
            <div className={`rb-save-status ${saveState.err ? 'err' : ''}`}>{saveState.text}</div>
          </div>
        </aside>

        <div className="rb-main">
          <div className="rb-panel" key={cur.key}>
            {sectionBusy && sectionBusy.key === cur.key && (
              <div className="rb-busy" role="status"><Loader2 size={22} className="spin" /><span>{sectionBusy.text}</span></div>
            )}
            {cur.kind === 'basics' ? renderBasics()
              : cur.kind === 'overview' ? renderOverview()
              : cur.kind === 'review' ? renderReview()
              : renderSection(cur.key)}
          </div>

          <div className="rb-actionbar">
            <button className="btn ghost" onClick={leave}>{editable ? 'Save & exit' : 'Back to client'}</button>
            <span className="rb-save-hint">Changes save automatically as you move between steps</span>
            <div className="rb-actionbar-nav">
              <button className="btn btn-secondary" onClick={() => go(step - 1)} disabled={step === 0}>
                <ArrowLeft size={14} /> Back
              </button>
              {step < steps.length - 1 && (
                <button className="btn btn-secondary" onClick={() => go(step + 1)}>
                  Continue <ArrowRight size={14} />
                </button>
              )}
              <button className="btn btn-primary" onClick={finish} disabled={finishing}>
                {finishing
                  ? <><Loader2 size={14} className="spin" /> Generating…</>
                  : editable ? 'Generate Report' : 'View report'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {showPeriod && clientId && snapshotId && (
        <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget && !periodBusy) setShowPeriod(false); }}>
          <div className="modal modal-lg" role="dialog" aria-modal="true" aria-labelledby="rb-period-title">
            <h2 className="modal-title" id="rb-period-title">Report period</h2>
            <PeriodPicker
              clientId={clientId}
              snapshotId={snapshotId}
              initialMonths={period?.months || 1}
              busy={periodBusy}
              confirmText={(m, label) => (m === (period?.months || 1) ? 'Keep this period' : `Recalculate for ${label}`)}
              onConfirm={m => (m === (period?.months || 1) ? setShowPeriod(false) : changePeriod(m))}
              onCancel={() => setShowPeriod(false)}
            />
          </div>
        </div>
      )}

      {leaveTo && (
        <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setLeaveTo(null); }}>
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="rb-leave-title">
            <h2 className="modal-title" id="rb-leave-title">Save your changes?</h2>
            <p className="modal-desc">
              You've changed this report since it was last saved. Save before you go, or the
              changes will be lost.
            </p>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setLeaveTo(null)}>Stay</button>
              <button className="btn ghost" onClick={leaveWithoutSaving}>Leave without saving</button>
              <button className="btn btn-primary" onClick={saveAndLeave}>Save &amp; leave</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportBuilder;
