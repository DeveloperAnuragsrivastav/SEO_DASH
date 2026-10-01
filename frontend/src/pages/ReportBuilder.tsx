import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import api from '../api/client';
import { toast } from 'sonner';
import {
  Sparkles, Loader2, Info, Pencil, Check, ArrowLeft, ArrowRight,
  FileText, Plug, RefreshCw, ImagePlus, Type,
  Upload, Download, CalendarRange, X,
} from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import PageSkeleton from '../components/ui/PageSkeleton';
import PeriodPicker from '../components/PeriodPicker';
import ReportShots from '../components/report/ReportShots';
import ListEditor, { type ListSpec } from '../components/report/ListEditor';
import '../builder.css';
import { confirmDialog } from '../components/ui/ConfirmDialog';

type Format = 'int' | 'percent' | 'decimal' | 'bool' | 'none';

interface Item {
  id: string;
  section: string;
  label: string;
  value: number | boolean | null;
  format: Format;
  editable: boolean;
  kind: 'headline' | 'summary' | 'row' | 'previous' | 'initial';
  /** For a previous-period figure: the id of this period's figure it pairs with. */
  pair?: string;
  unit?: string;
  /** An AI answer opened from last month's sheet, not yet confirmed for this one. */
  pending?: boolean;
  /** Heading for summary figures that belong to one slide (leads, AI referrals). */
  group?: string;
}

interface Period {
  months: number;
  start: string;
  end: string;
  labels: string[];
  label: string;
  range?: string;
  compare?: { range?: string; hasData?: boolean; published?: boolean };
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
  columns: string;
  sample: string;
  accept?: string;
}

interface Section { key: string; label: string }
/** A titled block of the report — the unit a commentary paragraph belongs to. */
interface Block { key: string; label: string; section: string }
/** Whether a connected source's figures can be trusted for this period. */
interface Health {
  connected: boolean;
  status: string;
  lastError: string;
  lastSync: string | null;
  newest: string | null;
  stale: boolean;
  source: string | null;
}
interface Heading { key: string; section: string; title: string; eyebrow?: string; label?: string }
interface Copy {
  brand_line: string;
  eyebrows: Record<string, string>;
  titles: Record<string, string>;
  subtitles: Record<string, string>;
  /** Every other fixed string the report prints, by its registry id. */
  texts: Record<string, string>;
}
/** One editable string: what it is, where it prints, and its unedited wording. */
interface TextField { key: string; block: string; label: string; default: string }
interface Step { key: string; kind: 'slides' | 'review'; label: string; about?: string }
/** One part of a slide's numbers, as the server describes it. */
interface SlidePart {
  type: 'figures' | 'rows' | 'table' | 'shots' | 'months' | 'editor';
  ids?: string[]; prefix?: string; path?: string; section?: string; name?: string;
  label?: string; hint?: string;
  /** Printed words rather than numbers (e.g. the brand line): shown under Words. */
  words?: boolean;
  /** Shown below the slide's title fields rather than above them. */
  after_heading?: boolean;
}
/** One slide of the report, and everything that feeds it. */
interface SlideDef {
  key: string; name: string; step: string; section: string | null; about: string;
  parts: SlidePart[]; heading: string | null; narration: string | null; texts: string[];
  note?: string; state: 'in' | 'empty' | 'hidden'; why: string;
  /** Which heading fields the slide prints; all three when absent. */
  heading_fields?: ('eyebrow' | 'title' | 'subtitle')[];
}
interface StepDef { key: string; label: string; about: string }

interface PlanItem { title: string; detail: string }
interface Plan { now: PlanItem[]; next: PlanItem[]; lede: string }

const EMPTY_PLAN: Plan = { now: [], next: [], lede: '' };

const EMPTY_COPY: Copy = { brand_line: '', eyebrows: {}, titles: {}, subtitles: {}, texts: {} };



/** Sections whose figures come from a Google connection when there is one. */
const PROVIDER_NAME: Record<string, string> = {
  gsc: 'Google Search Console',
  ga4: 'Google Analytics 4',
  gbp: 'Google Business Profile',
};

/** Sources the builder can pull fresh figures from on demand. */
const FETCHABLE: Record<string, string> = { gsc: 'GSC', ga4: 'GA4', gbp: 'Business Profile' };

/** What a provider section needs before the server will include it. */
const NEEDS: Record<string, string> = {
  gsc: 'clicks or impressions',
  ga4: 'sessions or users',
  gbp: 'at least one of calls, direction requests, website clicks or bookings',
};

/** Where each hand-kept section's data lives, for the "add more" links. */
const DATA_PAGE: Record<string, (clientId: string) => string> = {
  gsc: id => `/clients/${id}/search-console`,
  ga4: id => `/clients/${id}/google-analytics`,
  gbp: id => `/clients/${id}/gbp`,
  rankings: id => `/clients/${id}/keywords`,
  ai_visibility: id => `/clients/${id}/ai-mentions-data`,
  links: id => `/clients/${id}/links`,
  work: id => `/clients/${id}/work`,
};

const SHEET_NAME: Record<string, string> = {
  gsc: 'Search Console', ga4: 'Google Analytics', gbp: 'Business Profile', rankings: 'Keywords',
  ai_visibility: 'AI Visibility', links: 'Backlinks', work: 'On-Site SEO',
};

// What a section's summary figures are, where "Summary" alone would not say.
// What a section's tickable rows are, where "Rows" alone would not say.



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
/** The ranking slide's bands, in its order, with the positions each covers. */
const RANK_BANDS: { key: string; name: string; lo: number; hi: number }[] = [
  { key: 'top10', name: 'Top 10', lo: 1, hi: 10 },
  { key: '11_20', name: '11–20', lo: 11, hi: 20 },
  { key: '21_30', name: '21–30', lo: 21, hi: 30 },
  { key: '31_40', name: '31–40', lo: 31, hi: 40 },
  { key: '41_50', name: '41–50', lo: 41, hi: 50 },
  { key: '51_100', name: '51–100', lo: 51, hi: 100 },
  { key: 'none', name: 'Not in top 100', lo: 101, hi: 10_000 },
];

/** Typed-over ranking figures as the text in each box ("" = worked out). */
function rankDraftFrom(ov: any): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, cell] of Object.entries<any>(ov?.bands || {})) {
    if (cell?.initial !== undefined && cell?.initial !== null) out[`${key}.initial`] = String(cell.initial);
    if (cell?.prev !== undefined && cell?.prev !== null) out[`${key}.prev`] = String(cell.prev);
    if (cell?.now !== undefined && cell?.now !== null) out[`${key}.now`] = String(cell.now);
  }
  for (const k of ['improved', 'declined']) {
    const v = ov?.moves?.[k];
    if (v !== undefined && v !== null) out[`moves.${k}`] = String(v);
  }
  return out;
}

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
  const [listSpecs, setListSpecs] = useState<ListSpec[]>([]);
  // The report's slides and steps, as the server lists them; the builder is drawn from these.
  const [slides, setSlides] = useState<SlideDef[]>([]);
  const [stepDefs, setStepDefs] = useState<StepDef[]>([]);
  const [slideBusy, setSlideBusy] = useState<string | null>(null);
  const [kpiList, setKpiList] = useState<{ id: string; name: string; value: string; shown: boolean }[]>([]);
  // AI results figures: typed values ("" = worked out) and the worked-out ones.
  const [aiDraft, setAiDraft] = useState<Record<string, string>>({});
  const [aiSaved, setAiSaved] = useState<Record<string, string>>({});
  const [aiAuto, setAiAuto] = useState<any>(null);
  const [aiReading, setAiReading] = useState(false);
  const [aiRewriting, setAiRewriting] = useState(false);
  const [aiShot, setAiShot] = useState<string | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  // The builder's Add keyword / Add prompt forms.
  const [newKw, setNewKw] = useState({ term: '', search_volume: '', initial: '', previous: '', position: '' });
  const [newPrompt, setNewPrompt] = useState<{ prompt: string; results: Record<string, string> }>({ prompt: '', results: {} });
  const [adding, setAdding] = useState(false);
  // Figures typed over the ranking summary; blank means "worked out".
  type RankOv = { bands: Record<string, { initial?: number; prev?: number; now?: number }>; moves: { improved?: number; declined?: number } };
  const [rankOv, setRankOv] = useState<RankOv>({ bands: {}, moves: {} });
  const [rankDraft, setRankDraft] = useState<Record<string, string>>({});
  const [rankBusy, setRankBusy] = useState(false);
  // The ranking summary shows its worked-out counts; boxes open only to correct one.
  const [rankEditing, setRankEditing] = useState(false);
  const [lists, setLists] = useState<Record<string, any[]>>({});
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

  const [fetching, setFetching] = useState<string | null>(null);

  // Per-section commentary: the paragraph the report prints under the figures.
  const [narration, setNarration] = useState<Record<string, string>>({});
  const [narrationSource, setNarrationSource] = useState<Record<string, string>>({});
  const [narrationBlocks, setNarrationBlocks] = useState<Block[]>([]);
  const [plan, setPlan] = useState<Plan>(EMPTY_PLAN);
  // Who wrote the plan: "ai", "edited" (a person), or unknown for older reports.
  const [planSource, setPlanSource] = useState<string | null>(null);
  const [planWriting, setPlanWriting] = useState(false);
  // Slide subtitles the AI wrote (for the tag).
  const [subtitleAi, setSubtitleAi] = useState<string[]>([]);
  const [textFields, setTextFields] = useState<TextField[]>([]);
  const [narrationAvailable, setNarrationAvailable] = useState<Record<string, boolean>>({});

  // Sources whose connection is not working, and the acknowledgement that
  // lets a report go out on stored figures anyway.
  const [health, setHealth] = useState<Record<string, Health>>({});
  const [ackStale, setAckStale] = useState(false);
  const [writingFor, setWritingFor] = useState<string | null>(null);
  const savedNarration = useRef('{}');

  // The months this report covers
  const [period, setPeriod] = useState<Period | null>(null);
  const [periods, setPeriods] = useState<PeriodRow[]>([]);
  const [showPeriod, setShowPeriod] = useState(false);
  const [periodBusy, setPeriodBusy] = useState(false);

  // Figures whose edit should also correct the saved data they came from

  // A section busy reading an uploaded sheet
  const [sectionBusy, setSectionBusy] = useState<{ key: string; text: string } | null>(null);


  const [step, setStep] = useState(0);
  // A slide to scroll to once its step has drawn (from Review's Edit).
  const jumpTo = useRef<string | null>(null);
  useEffect(() => {
    if (!jumpTo.current) return;
    const key = jumpTo.current;
    jumpTo.current = null;
    // After the step has drawn its cards.
    setTimeout(() => document.getElementById(`slide-${key}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
  }, [step]);
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
    if (d.listSpecs) setListSpecs(d.listSpecs);
    if (d.slides) setSlides(d.slides);
    if (d.steps) setStepDefs(d.steps);
    if (d.kpiCards) setKpiList(d.kpiCards);
    const typedAi = d.aiSummary || {};
    const flat: Record<string, string> = {};
    for (const k of ['score', 'mentions', 'cited']) if (typedAi[k] !== undefined && typedAi[k] !== null) flat[k] = String(typedAi[k]);
    for (const [eng, cell] of Object.entries<any>(typedAi.engines || {}))
      for (const f of ['mentions', 'cited']) if (cell?.[f] !== undefined && cell?.[f] !== null) flat[`${eng}.${f}`] = String(cell[f]);
    setAiDraft(flat);
    setAiSaved(flat);
    setAiAuto(d.aiSummaryAuto || null);
    const ov = d.rankOverrides || { bands: {}, moves: {} };
    setRankOv(ov);
    setRankDraft(rankDraftFrom(ov));
    setLists(d.lists || {});
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
    const nar: Record<string, string> = d.narration || {};
    setNarration(nar);
    savedNarration.current = JSON.stringify(nar);
    setNarrationSource(d.narrationSource || {});
    if (d.narrationBlocks) setNarrationBlocks(d.narrationBlocks);
    if (d.textFields) setTextFields(d.textFields);
    if (d.plan) {
      const p: Plan = { now: d.plan.now || [], next: d.plan.next || [], lede: d.plan.lede || '' };
      setPlan(p);
      savedPlan.current = JSON.stringify(p);
      setPlanSource(d.planSource || null);
      setSubtitleAi(d.subtitleAi || []);
    }
    setNarrationAvailable(d.narrationAvailable || {});
    setHealth(d.dataHealth || {});
    setPeriod(d.period || null);
    setPeriods(d.periods || []);
  };


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
  const savedPlan = useRef('');
  const latest = useRef({ items, values, saved, sectionOn, itemOn, copy, narration, plan, available });
  latest.current = { items, values, saved, sectionOn, itemOn, copy, narration, plan, available };
  const chain = useRef<Promise<unknown>>(Promise.resolve());

  const persist = useCallback(async () => {
    if (!dirty.current) return;
    dirty.current = false;
    const { items, values, saved, itemOn, copy, narration, plan } = latest.current;
    let { sectionOn, available: known } = latest.current;
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
        const res = await api.put(`${base}/values`, { edits });
        setSaved(prev => ({ ...prev, ...sent }));
        // What the slides now print follows the new figures.
        if (res.data?.kpiCards) setKpiList(res.data.kpiCards);
        // A section that just got its first figures is on now, as the server says.
        if (res.data?.available) {
          known = res.data.available;
          setAvailable(res.data.available);
          if (res.data.selectedSections) { sectionOn = res.data.selectedSections; setSectionOn(res.data.selectedSections); }
        }
        // One answer in the AI grid confirms the whole grid for this month.
        if (Object.keys(edits).some(k => k.startsWith('ai_visibility.'))) {
          setItems(list => list.map(x => (x.section === 'ai_visibility' && x.pending ? { ...x, pending: false } : x)));
        }
        if (res.data?.slides) setSlides(res.data.slides);
        // The total leads is worked out from the lead figures: take the new sum,
        // unless the total itself was just typed.
        const total: Item | undefined = (res.data?.items || []).find((x: Item) => x.id === 'ga4.lead.total');
        if (total && !('ga4.lead.total' in edits)) {
          const text = toText(total);
          setItems(list => list.map(x => (x.id === total.id ? total : x)));
          setValues(v => ({ ...v, [total.id]: text }));
          setSaved(v => ({ ...v, [total.id]: text }));
        }
      }
      // Only sections with data carry a choice; an empty one switches on by itself.
      const chosen = Object.fromEntries(Object.entries(sectionOn).filter(([k]) => known[k]));
      const res = await api.put(`${base}/composer`, { sections: chosen, items: itemOn });
      if (res.data?.selectedSections) setSectionOn(res.data.selectedSections);

      const copyJson = JSON.stringify(copy);
      if (copyJson !== savedCopy.current) {
        const saved = await api.put(`${base}/copy`, copy);
        savedCopy.current = copyJson;
        if (saved.data?.subtitleAi) setSubtitleAi(saved.data.subtitleAi);
      }

      const narrationJson = JSON.stringify(narration);
      if (narrationJson !== savedNarration.current) {
        const res = await api.put(`${base}/narration`, { narration });
        savedNarration.current = narrationJson;
        if (res.data?.narrationSource) setNarrationSource(res.data.narrationSource);
      }

      const planJson = JSON.stringify(plan);
      if (planJson !== savedPlan.current) {
        await api.put(`${base}/plan`, plan);
        savedPlan.current = planJson;
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

  const toggleItem = (id: string) => {
    if (!editable) return;
    setItemOn(s => ({ ...s, [id]: s[id] === false }));
    dirty.current = true;
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


  /** Read a sheet into this draft only — nothing is saved for the client
   *  until the report is published. */
  const uploadSheet = async (key: string, file: File) => {
    if (file.size > 2 * 1024 * 1024) { toast.error('The sheet must be 2 MB or smaller.'); return; }
    setSectionBusy({ key, text: 'Reading the sheet into this report…' });
    // Save first — the section read from the sheet replaces what is on screen.
    try { await queueSave(); } catch (e) { setSectionBusy(null); return; }
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post(`${base}/upload/${key}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      applyComposer(res.data || {});
      toast.success(`Sheet read — ${res.data?.uploaded || 'this section is updated'}.`);
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
  const setEyebrow = (key: string, text: string) => {
    setCopy(c => ({ ...c, eyebrows: { ...c.eyebrows, [key]: text } }));
    dirty.current = true;
  };
  const setText = (key: string, text: string) => {
    setCopy(c => ({ ...c, texts: { ...c.texts, [key]: text } }));
    dirty.current = true;
  };

  const setStory = (key: string, text: string) => {
    setNarration(n => ({ ...n, [key]: text }));
    setNarrationSource(src => ({ ...src, [key]: text.trim() ? 'edited' : '' }));
    dirty.current = true;
  };

  /** Have the AI write one section's commentary from its current figures. */
  const writeStory = async (key: string) => {
    setWritingFor(key);
    // Save first: the AI reads the figures and ticks as they now stand.
    try { await queueSave(); } catch (e) { setWritingFor(null); return; }
    try {
      const res = await api.post(`${base}/narration/${key}/regenerate`);
      const text = res.data?.text || '';
      setNarration(n => ({ ...n, [key]: text }));
      setNarrationSource(src => ({ ...src, [key]: 'ai' }));
      savedNarration.current = JSON.stringify({ ...latest.current.narration, [key]: text });
      toast.success('Summary written.');
    } catch (err: any) {
      // Handled by global interceptor
    }
    setWritingFor(null);
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



  // ── Steps ──
  const steps = useMemo<Step[]>(() => [
    ...stepDefs.map(s => ({ key: s.key, kind: 'slides' as const, label: s.label, about: s.about })),
    { key: 'review', kind: 'review', label: 'Review & generate' },
  ], [stepDefs]);

  /** Write the plan with AI. `force` replaces what is there (the Rewrite button). */
  const writePlan = useCallback(async (force: boolean) => {
    setPlanWriting(true);
    try {
      const res = await api.post(`${base}/plan/draft`, null, { params: { force } });
      const p = res.data.plan || EMPTY_PLAN;
      const next: Plan = { now: p.now || [], next: p.next || [], lede: p.lede || '' };
      setPlan(next);
      savedPlan.current = JSON.stringify(next);
      setPlanSource(res.data.source || null);
      if (force) toast.success('Plan written — edit anything you like.');
    } catch {
      // Handled by global interceptor
    }
    setPlanWriting(false);
  }, [base]);

  const go = (i: number) => {
    if (i < 0 || i >= steps.length || i === step) return;
    setEditing(null);
    if (editable) queueSave().catch(() => {});
    setStep(i);
    setVisited(v => new Set(v).add(i));
    if (!jumpTo.current) document.querySelector('.app-content')?.scrollTo({ top: 0, behavior: 'smooth' });
  };
  /** Open the step a slide is on and bring its card into view. */
  const goToSlide = (sl: { key: string; step: string }) => {
    jumpTo.current = sl.key;
    const i = steps.findIndex(s => s.key === sl.step);
    if (i === step) { document.getElementById(`slide-${sl.key}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }); jumpTo.current = null; }
    else go(i);
  };

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

  /** Save, then publish: this month's figures become final on every sheet. */
  const publish = async () => {
    const month = period?.labels?.[period.labels.length - 1] || period?.label || 'this month';
    if (!(await confirmDialog({
      title: `Publish the ${month} report?`,
      message: `Its figures become ${month}'s final column in every sheet (Search Console, Analytics, Keywords…) and the report is locked. To change it later, use Make draft and publish again.`,
      confirmText: 'Publish',
    }))) return;
    setFinishing(true);
    dirty.current = true;
    try {
      await queueSave();
      await api.post(`/clients/${clientId}/reports/${snapshotId}/publish`);
      toast.success(`Published — ${month} is now on every sheet.`);
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
      </div>
    );
  };

  /** Last period's twin of a figure, when the report compares it. */
  // A several-month report shows only the numbers it prints — the combined
  // ones; its comparison is worked out from the months themselves.
  const span = (period?.months || 1) > 1;
  const prevOf = (i: Item) => (span && i.section !== 'rankings')
    ? undefined
    : items.find(p => p.kind === 'previous' && p.pair === i.id);
  /** Where a keyword started, when tracking began. */
  const initialOf = (i: Item) => items.find(p => p.kind === 'initial' && p.pair === i.id);

  /** The change between the two boxes, worded the way the report prints it. */
  const changeText = (i: Item, prevText: string, nowText: string) => {
    if (prevText.trim() === '' || nowText.trim() === '') return { text: 'Add last month to show the change', tone: 'none' };
    const was = Number(prevText), now = Number(nowText);
    if (!Number.isFinite(was) || !Number.isFinite(now)) return { text: '', tone: 'none' };
    if (i.id.endsWith('.position') || i.unit === 'position') {
      const moved = Math.round((now - was) * 10) / 10;
      if (!moved) return { text: 'No change', tone: 'flat' };
      return { text: `${Math.abs(moved)} ${Math.abs(moved) === 1 ? 'place' : 'places'} ${moved > 0 ? 'lower' : 'better'}`, tone: moved > 0 ? 'down' : 'up' };
    }
    if (was === 0) return { text: now > 0 ? 'New this month' : 'No change', tone: now > 0 ? 'up' : 'flat' };
    const pct = Math.round(((now - was) / was) * 1000) / 10;
    return { text: `${pct > 0 ? '+' : ''}${pct}% vs last month`, tone: pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat' };
  };

  /** A figure with last period beside it: two boxes, and the change between. */
  const pairCard = (i: Item, prev: Item) => {
    const shown = itemOn[i.id] !== false;
    const change = changeText(i, values[prev.id] ?? '', values[i.id] ?? '');
    return (
      <div key={i.id} className={`metric-card rb-pair ${shown ? '' : 'off'}`}>
        <label className="metric-card-head">
          <input type="checkbox" checked={shown} disabled={!editable} onChange={() => toggleItem(i.id)} />
          <span title={i.label}>{i.label}</span>
        </label>
        <div className={`rb-pair-boxes ${initialOf(i) ? 'three' : ''}`}>
          {initialOf(i) && (
            <label className="rb-pair-box initial">
              <span>Initial</span>
              {valueInput(initialOf(i)!, false, true)}
            </label>
          )}
          <label className="rb-pair-box">
            <span>Previous month</span>
            {valueInput(prev, false, true)}
          </label>
          <label className="rb-pair-box now">
            <span>This month</span>
            {valueInput(i, false, true)}
          </label>
        </div>
        <div className={`rb-pair-change ${change.tone}`}>{change.text}</div>
      </div>
    );
  };

  /** The ranking summary: worked out live from each keyword's two positions,
   *  and every count can be typed over. Blank boxes show the worked-out figure. */
  const rankingSummary = () => {
    const kws = items.filter(i => i.section === 'rankings' && i.kind === 'row' && itemOn[i.id] !== false);
    if (kws.length === 0) return null;
    const pos = (id: string) => Math.round(Number(values[id] || 0)) || 0;
    const bandOf = (p: number) => RANK_BANDS.findIndex(b => (p || 10_000) >= b.lo && (p || 10_000) <= b.hi);
    const auto = RANK_BANDS.map(b => ({ ...b, initial: 0, prev: 0, now: 0 }));
    let improved = 0, declined = 0, held = 0, noPrev = 0;
    for (const k of kws) {
      const now = pos(k.id), was = pos(`prev:${k.id}`), start = pos(`init:${k.id}`);
      auto[bandOf(now)].now += 1;
      if (start) auto[bandOf(start)].initial += 1;
      if (was) auto[bandOf(was)].prev += 1;
      if (!was) noPrev += 1;
      else if (now && now < was) improved += 1;
      else if (now && now > was) declined += 1;
      else if (now) held += 1;
    }
    const saved = rankDraftFrom(rankOv);
    const dirty = JSON.stringify(saved) !== JSON.stringify(Object.fromEntries(Object.entries(rankDraft).filter(([, v]) => v.trim() !== '')));
    const shown = (id: string, fallback: number) => (rankDraft[id] ?? '').trim() !== '' ? Number(rankDraft[id]) : fallback;
    const typedHere = (id: string) => (rankDraft[id] ?? '').trim() !== '';
    const box = (id: string, fallback: number) => !rankEditing ? (
      <span className={`rb-rank-val ${typedHere(id) ? 'typed' : ''}`} title={typedHere(id) ? `Typed in — worked out it would be ${fallback}` : 'Worked out from the keywords below'}>
        {typedHere(id) ? Number(rankDraft[id]) : fallback}
      </span>
    ) : (
      <input
        type="number" min="0" step="1"
        className={`rb-rank-input ${(rankDraft[id] ?? '').trim() !== '' ? 'typed' : ''}`}
        placeholder={String(fallback)}
        value={rankDraft[id] ?? ''}
        disabled={!editable || rankBusy}
        aria-label={id}
        onChange={e => setRankDraft(d => ({ ...d, [id]: e.target.value }))}
      />
    );
    const save = async (draft: Record<string, string>) => {
      const bands: Record<string, Record<string, number | null>> = {};
      for (const b of RANK_BANDS) {
        const cell: Record<string, number | null> = {};
        for (const side of ['initial', 'prev', 'now']) {
          const v = (draft[`${b.key}.${side}`] ?? '').trim();
          if (v !== '') cell[side] = Number(v);
        }
        if (Object.keys(cell).length) bands[b.key] = cell;
      }
      const moves: Record<string, number> = {};
      for (const k of ['improved', 'declined']) {
        const v = (draft[`moves.${k}`] ?? '').trim();
        if (v !== '') moves[k] = Number(v);
      }
      setRankBusy(true);
      try {
        const res = await api.put(`${base}/rank-summary`, { bands, moves });
        setRankOv(res.data.overrides);
        setRankDraft(rankDraftFrom(res.data.overrides));
        setRankEditing(false);
        toast.success('Ranking summary saved.');
      } catch {
        // Handled by global interceptor
      }
      setRankBusy(false);
    };
    const anyTyped = Object.keys(saved).length > 0;

    return (
      <div className="rb-group">
        <div className="rb-group-label">Ranking summary — counted automatically from the keyword positions below</div>
        <div className="rb-rank-summary">
          <div className="rb-rank-moves">
            <label className="up"><span>Improved</span>{box('moves.improved', improved)}</label>
            <label className="down"><span>Declined</span>{box('moves.declined', declined)}</label>
            <div><b>{held}</b><span>Unchanged</span></div>
          </div>
          <div className="rb-month-table">
            <table>
              <thead><tr><th>Position</th><th>Initial</th><th>Previous month</th><th>This month</th><th>Change</th></tr></thead>
              <tbody>
                {auto.map(b => {
                  const was = shown(`${b.key}.prev`, b.prev), now = shown(`${b.key}.now`, b.now);
                  const diff = now - was;
                  return (
                    <tr key={b.key}>
                      <td>{b.name}</td>
                      <td>{box(`${b.key}.initial`, b.initial)}</td>
                      <td>{box(`${b.key}.prev`, b.prev)}</td>
                      <td>{box(`${b.key}.now`, b.now)}</td>
                      <td className={diff > 0 ? 'up' : diff < 0 ? 'down' : 'flat'}>{diff > 0 ? `+${diff}` : diff === 0 ? '—' : diff}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {editable && (
            <div className="rb-list-actions">
              {anyTyped && (
                <button className="btn ghost btn-sm" disabled={rankBusy} onClick={() => save({})}>Go back to automatic</button>
              )}
              <span style={{ flex: 1 }} />
              {!rankEditing ? (
                <button className="btn btn-secondary btn-sm" onClick={() => setRankEditing(true)}>
                  <Pencil size={13} /> Correct a count
                </button>
              ) : (
                <>
                  <button className="btn ghost btn-sm" disabled={rankBusy} onClick={() => { setRankDraft(saved); setRankEditing(false); }}>Cancel</button>
                  <button className="btn btn-primary btn-sm" disabled={!dirty || rankBusy} onClick={() => save(rankDraft)}>
                    {rankBusy ? <Loader2 size={13} className="spin" /> : null} Save counts
                  </button>
                </>
              )}
            </div>
          )}
        </div>
        <p className="rb-note">
          {rankEditing
            ? 'Type a number only where the count should differ from the keywords; leave a box empty to keep counting it automatically.'
            : anyTyped
              ? 'Gold numbers were typed in and replace the automatic count; every other number updates as you change the positions below.'
              : 'Every number here updates as you change the positions below — nothing to fill in.'}
          {noPrev > 0 && <> {noPrev} {noPrev === 1 ? 'keyword has' : 'keywords have'} no previous position yet — add it below to count its movement.</>}
        </p>
      </div>
    );
  };

  // ── Adding a keyword or a prompt from the builder ──

  const addKeyword = async () => {
    const n = (v: string) => (v.trim() === '' ? null : Math.max(0, Math.round(Number(v))));
    if (!newKw.term.trim()) { toast.error('Type the keyword.'); return; }
    setAdding(true);
    try {
      const res = await api.post(`${base}/keywords`, {
        term: newKw.term, search_volume: n(newKw.search_volume), initial: n(newKw.initial),
        previous: n(newKw.previous), position: n(newKw.position),
      });
      applyComposer(res.data);
      setNewKw({ term: '', search_volume: '', initial: '', previous: '', position: '' });
      toast.success('Keyword added — it is now tracked for this client.');
    } catch {
      // Handled by global interceptor
    }
    setAdding(false);
  };

  const ASSISTANTS: [string, string][] = [
    ['chatgpt', 'ChatGPT'], ['google_ai_overview', 'AI Overview'], ['gemini', 'Gemini'],
    ['perplexity', 'Perplexity'], ['claude', 'Claude'], ['grok', 'Grok'],
  ];

  const addPrompt = async () => {
    if (!newPrompt.prompt.trim()) { toast.error('Type the prompt.'); return; }
    const results = Object.fromEntries(
      Object.entries(newPrompt.results).filter(([, v]) => v === 'yes' || v === 'no').map(([k, v]) => [k, v === 'yes']),
    );
    if (Object.keys(results).length === 0) { toast.error('Mark Yes or No for at least one assistant.'); return; }
    setAdding(true);
    try {
      const res = await api.post(`${base}/ai-prompts`, { prompt: newPrompt.prompt, results });
      applyComposer(res.data);
      setNewPrompt({ prompt: '', results: {} });
      toast.success('Prompt added — it is now tracked for this client.');
    } catch {
      // Handled by global interceptor
    }
    setAdding(false);
  };

  const addKeywordForm = () => editable && (
    <div className="rb-group rb-add">
      <div className="rb-group-label">Add a keyword</div>
      <div className="rb-add-row">
        <label className="rb-add-field wide"><span>Keyword</span>
          <input className="form-input" value={newKw.term} placeholder="e.g. best seo agency in delhi"
            onChange={e => setNewKw(k => ({ ...k, term: e.target.value }))}
            onKeyDown={e => { if (e.key === 'Enter') addKeyword(); }} />
        </label>
        {([['search_volume', 'Search volume'], ['initial', 'Initial'], ['previous', 'Previous month'], ['position', 'This month']] as const).map(([k, label]) => (
          <label key={k} className="rb-add-field"><span>{label}</span>
            <input className="form-input" type="number" min="0" value={(newKw as any)[k]}
              onChange={e => setNewKw(v => ({ ...v, [k]: e.target.value }))}
              onKeyDown={e => { if (e.key === 'Enter') addKeyword(); }} />
          </label>
        ))}
        <button className="btn btn-primary btn-sm" disabled={adding || !newKw.term.trim()} onClick={addKeyword}>
          {adding ? <Loader2 size={13} className="spin" /> : null} Add keyword
        </button>
      </div>
      <p className="rb-note">Added to this report and to the client's tracked keywords, so next month's report includes it too. Leave a position blank if it isn't known.</p>
    </div>
  );

  /** AI Visibility, total mentions, total cited pages, and each assistant's. */
  const aiSummaryEditor = () => {
    if (!aiAuto) return null;
    const auto = (id: string): number => {
      if (id === 'score') return aiAuto.auto?.score ?? 0;
      const [eng, f] = id.split('.');
      if (!f) {
        // Totals follow the assistants' figures, typed or worked out.
        return (aiAuto.engines || []).reduce((sum: number, e: any) => {
          const typed = (aiDraft[`${e.key}.${eng}`] ?? '').trim();
          return sum + (typed !== '' ? Number(typed) : (e[eng] ?? 0));
        }, 0);
      }
      return aiAuto.auto?.engines?.[eng]?.[f] ?? 0;
    };
    const box = (id: string, max?: number) => (
      <input
        type="number" min="0" max={max} step="1"
        className={`rb-rank-input ${(aiDraft[id] ?? '').trim() !== '' ? 'typed' : ''}`}
        placeholder={String(auto(id))}
        value={aiDraft[id] ?? ''}
        disabled={!editable || aiBusy}
        aria-label={id}
        onChange={e => setAiDraft(d => ({ ...d, [id]: e.target.value }))}
      />
    );
    const clean = (d: Record<string, string>) => Object.fromEntries(Object.entries(d).filter(([, v]) => v.trim() !== ''));
    const dirty = JSON.stringify(clean(aiDraft)) !== JSON.stringify(clean(aiSaved));
    const save = async (draft: Record<string, string>) => {
      const n = (id: string) => ((draft[id] ?? '').trim() === '' ? null : Number(draft[id]));
      const engines: Record<string, Record<string, number | null>> = {};
      for (const e of aiAuto.engines || []) engines[e.key] = { mentions: n(`${e.key}.mentions`), cited: n(`${e.key}.cited`) };
      setAiBusy(true);
      try {
        await api.put(`${base}/ai-summary`, { score: n('score'), mentions: n('mentions'), cited: n('cited'), engines });
        setAiSaved(clean(draft));
        setAiDraft(clean(draft));
        toast.success('AI results saved.');
      } catch {
        // Handled by global interceptor
      }
      setAiBusy(false);
    };
    /** Read the figures off an AI-visibility tool's screenshot into the boxes. */
    const readShot = async (file: File) => {
      if (!/^image\/(png|jpeg|webp)$/.test(file.type)) { toast.error('Use a PNG, JPEG or WebP screenshot.'); return; }
      if (file.size > 5 * 1024 * 1024) { toast.error('The screenshot must be 5 MB or smaller.'); return; }
      setAiReading(true);
      try { await queueSave(); } catch (e) { setAiReading(false); return; }
      try {
        const fd = new FormData();
        fd.append('file', file);
        const res = await api.post(`${base}/ai-summary/read`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        const r = await api.get(`${base}/composer`);
        applyComposer(r.data || {});
        setAiShot(URL.createObjectURL(file));
        const n = Object.keys(res.data?.read || {}).length + Object.keys(res.data?.read?.engines || {}).length - (res.data?.read?.engines ? 1 : 0);
        toast.success(`Read ${n} figure${n === 1 ? '' : 's'} from the screenshot — check them below and change any that are off.`);
      } catch {
        // Handled by global interceptor
      }
      setAiReading(false);
    };
    return (
      <div className="rb-group">
        <div className="rb-group-label">AI results slide — read the figures from a screenshot, or type them</div>
        {editable && (
          <div className="rb-upload" style={{ marginBottom: 10 }}>
            <div className="rb-upload-text">
              <ImagePlus size={16} />
              <span>
                <strong>Fill from a screenshot</strong>
                Upload a screenshot of your AI visibility tool (score, mentions, cited pages, each assistant). The figures are read and filled in below — every one stays editable.
              </span>
            </div>
            <div className="rb-upload-actions">
              {aiShot && <a href={aiShot} target="_blank" rel="noreferrer" className="btn ghost btn-sm">View screenshot</a>}
              <label className={`btn btn-primary btn-sm ${aiReading ? 'is-disabled' : ''}`}>
                {aiReading ? <><Loader2 size={13} className="spin" /> Reading…</> : <><Upload size={13} /> Upload screenshot</>}
                <input type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={aiReading}
                  onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) readShot(f); }} />
              </label>
            </div>
          </div>
        )}
        <div className="rb-ai-sum">
          <label className="rb-add-field"><span>AI Visibility (0–100)</span>{box('score', 100)}</label>
          <label className="rb-add-field"><span>Total mentions</span>{box('mentions')}</label>
          <label className="rb-add-field"><span>Total cited pages</span>{box('cited')}</label>
        </div>
        <div className="rb-month-table" style={{ marginTop: 10 }}>
          <table>
            <thead><tr><th>Assistant</th><th>Mentions</th><th>Cited pages</th></tr></thead>
            <tbody>
              {(aiAuto.engines || []).map((e: any) => (
                <tr key={e.key}>
                  <td>{e.name}</td>
                  <td>{box(`${e.key}.mentions`)}</td>
                  <td>{box(`${e.key}.cited`)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {editable && (
          <div className="rb-list-actions">
            {Object.keys(aiSaved).length > 0 && (
              <button className="btn ghost btn-sm" disabled={aiBusy} onClick={() => save({})}>Reset to worked-out</button>
            )}
            <span style={{ flex: 1 }} />
            {dirty && <button className="btn ghost btn-sm" disabled={aiBusy} onClick={() => setAiDraft(aiSaved)}>Discard</button>}
            <button className="btn btn-primary btn-sm" disabled={!dirty || aiBusy} onClick={() => save(aiDraft)}>
              {aiBusy ? <Loader2 size={13} className="spin" /> : null} Save AI results
            </button>
          </div>
        )}
        <p className="rb-note">Grey numbers come from the prompt checks; the totals add up the assistants unless you type them. AI Mode isn't checked automatically, so type its figures.</p>
      </div>
    );
  };

  const addPromptForm = () => editable && (
    <div className="rb-group rb-add">
      <div className="rb-group-label">Add a prompt</div>
      <label className="rb-add-field wide" style={{ marginBottom: 10 }}><span>Prompt — the question a customer asks an AI assistant</span>
        <input className="form-input" value={newPrompt.prompt} placeholder="e.g. best seo company in india"
          onChange={e => setNewPrompt(p => ({ ...p, prompt: e.target.value }))} />
      </label>
      <div className="rb-add-assistants">
        {ASSISTANTS.map(([key, name]) => {
          const v = newPrompt.results[key] || '';
          const set = (val: string) => setNewPrompt(p => ({ ...p, results: { ...p.results, [key]: p.results[key] === val ? '' : val } }));
          return (
            <div key={key} className="rb-add-assistant">
              <span>{name}</span>
              <div className="rb-wb" role="radiogroup" aria-label={`${name} named the brand?`}>
                <button type="button" className={`rb-wb-opt ${v === 'yes' ? 'on' : ''}`} onClick={() => set('yes')}>Yes</button>
                <button type="button" className={`rb-wb-opt ${v === 'no' ? 'on' : ''}`} onClick={() => set('no')}>No</button>
              </div>
            </div>
          );
        })}
      </div>
      <div className="rb-list-actions">
        <span className="rb-note" style={{ margin: 0, flex: 1 }}>Yes = the assistant named the brand. Leave an assistant unmarked if it wasn't checked.</span>
        <button className="btn btn-primary btn-sm" disabled={adding || !newPrompt.prompt.trim()} onClick={addPrompt}>
          {adding ? <Loader2 size={13} className="spin" /> : null} Add prompt
        </button>
      </div>
    </div>
  );

  /** Any figure: as a pair when last period applies, else as before. */
  const figure = (i: Item, typed: boolean) => {
    const prev = prevOf(i);
    if (prev) return pairCard(i, prev);
    return typed ? field(i) : card(i);
  };

  /** A figure typed straight in — for sources with no connection to fill it. */
  const field = (i: Item) => (
    <div key={i.id} className={`rb-field ${itemOn[i.id] !== false ? '' : 'off'}`}>
      <label className="metric-card-head">
        <input type="checkbox" checked={itemOn[i.id] !== false} disabled={!editable} onChange={() => toggleItem(i.id)} />
        <span title={i.label}>{i.label}</span>
      </label>
      {valueInput(i, false, true)}
      {i.format === 'percent' && <div className="rb-field-unit">Percent — e.g. 2.4</div>}
      {i.id.endsWith('.position') && <div className="rb-field-unit">Average position — e.g. 18.5</div>}
    </div>
  );


  /** Which sheet a section takes, when its data is entered by hand. */
  const uploadSpecFor = (key: string): UploadSpec | null => {
    const m = lastCol;
    switch (key) {
      case 'gsc':
        return connected('gsc') ? null : {
          title: 'Upload a Search Console sheet', hint: 'One row per day.',
          columns: 'date,clicks,impressions,ctr,position', sample: `${sampleDay},120,4500,0.027,12.4`,
        };
      case 'ga4':
        return connected('ga4') ? null : {
          title: 'Upload an Analytics sheet', hint: 'One row per day.',
          columns: 'date,sessions,users,engaged_sessions,conversions,revenue', sample: `${sampleDay},761,589,147,3,0`,
        };
      case 'gbp':
        return connected('gbp') ? null : {
          title: 'Upload a Business Profile sheet', hint: 'One row per month.',
          columns: 'Date,Impressions Desktop Maps,Impressions Desktop Search,Impressions Mobile Maps,Impressions Mobile Search,Calls,Direction Requests,Website Clicks,Bookings',
          sample: `${m},100,50,300,150,5,2,10,1`,
        };
      case 'rankings': {
        // Last month's column too: it fills "Previous" when that month isn't published yet.
        const first = new Date(`1 ${(period?.labels || [])[0] || ''}`);
        const prevCol = Number.isNaN(first.getTime()) ? null
          : monthCol(new Date(first.getFullYear(), first.getMonth() - 1, 1).toLocaleString('en', { month: 'long', year: 'numeric' }));
        const cols = [...(prevCol ? [prevCol] : []), ...(monthCols.length ? monthCols : [m])];
        return {
          title: 'Upload keyword rankings', hint: 'One row per keyword, one column per month.',
          columns: `Keyword,SV,Initial Ranking,${cols.join(',')}`,
          sample: `best seo agency,1900,24,${cols.map((_, n) => Math.max(1, 18 - n * 3)).join(',')}`,
          accept: '.csv,.xlsx',
        };
      }
      case 'ai_visibility':
        return {
          title: 'Upload AI prompt checks', hint: 'One row per prompt — Yes or No for each AI tool.',
          columns: 'Month,Prompts,ChatGPT,AI Overview,Google Gemini,Perplexity,Claude', sample: `${m},Best pizza in NY,Yes,No,Yes,Yes,No`,
        };
      case 'links':
        return {
          title: 'Upload links built', hint: 'One row per link.',
          columns: 'Month,Activity Name,URL,Count', sample: `${m},Guest Post,https://example.com/article,1`,
        };
      case 'work':
        return {
          title: 'Upload work delivered', hint: 'One row per task.',
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
          <label className={`btn btn-primary btn-sm ${sectionBusy ? 'is-disabled' : ''}`}>
            <Upload size={13} /> Upload sheet
            <input
              type="file"
              accept=".csv,.xlsx"
              hidden
              disabled={!!sectionBusy}
              onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) uploadSheet(key, f); }}
            />
          </label>
        </div>
      </div>
    );
  };

  /** Each month of a combined report, beside the combined figure. */
  const monthTable = (key: string) => {
    const cols = PERIOD_COLS[key];
    // No per-month sections: the builder works on the combined figures only.
    if (!cols || periods.length < 2 || span) return null;
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


  /** The paragraph printed under one block's figures in the report. */
  const summaryEditor = (blockKey: string) => {
    const block = narrationBlocks.find(b => b.key === blockKey);
    if (!block) return null;
    const text = narration[blockKey] ?? '';
    const busy = writingFor === blockKey;
    const written = narrationSource[blockKey] === 'ai' && !!text.trim();
    const hasFigures = narrationAvailable[blockKey] !== false;

    return (
      <div className="rb-story">
        {/* A peer of Title and Subtitle, labelled the same quiet way — the
            paragraph repeats under every block, so its label must not shout. */}
        <label className="rb-copy-field">
          <span>
            Summary <em>the paragraph in the black box at the bottom of the slide</em>
            {text.trim() && (
              <span className={`rb-story-tag ${written ? 'ai' : 'own'}`}>
                {written ? 'Written by AI' : 'Your words'}
              </span>
            )}
          </span>
          <textarea
            className="form-input rb-story-text"
            rows={4}
            maxLength={2000}
            value={text}
            disabled={!editable || busy}
            placeholder={`What changed in ${block.label.toLowerCase()}, why, and what happens next.`}
            onChange={e => setStory(blockKey, e.target.value)}
          />
        </label>

        <div className="rb-story-foot">
          {editable && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => writeStory(blockKey)}
              disabled={busy || !!fetching || !hasFigures}
              title={hasFigures
                ? `Read the figures in ${block.label} and write this paragraph`
                : 'There are no figures in this block to write about yet'}
            >
              {busy
                ? <><Loader2 size={13} className="spin" /> Writing…</>
                : <><Sparkles size={13} /> {text.trim() ? 'Rewrite with AI' : 'Write with AI'}</>}
            </button>
          )}
          <span className="rb-story-note">
            {!hasFigures
              ? 'Nothing recorded in this block yet, so there is nothing to write about.'
              : text.trim()
                ? 'Prints under this block in the report, exactly as written here.'
                : 'Leave it empty and the block prints its figures on their own.'}
          </span>
        </div>
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

  /** Sources this report leans on whose connection is not actually working.
   *  The figures are real — they are just the last ones ever stored, and the
   *  report will present them as automatically collected. */
  const staleSources = Object.entries(health)
    // Only figures that claim to come from Google ("api", or "mixed" with
    // hand entries) can be stale. Figures typed in — saved by hand ("manual")
    // or straight into this report (no saved source at all) — never claimed
    // to be collected automatically, so a missing connection is no warning.
    .filter(([key, h]) => sectionOn[key] && hasData(key) && !h.connected && (h.source === 'api' || h.source === 'mixed'))
    .map(([key, h]) => ({ key, name: PROVIDER_NAME[key] || key, ...h }));

  const mustAcknowledge = editable && staleSources.length > 0 && !ackStale;

  // ── Next plan of action ──
  const setLane = (lane: 'now' | 'next', i: number, field: 'title' | 'detail', value: string) => {
    if (!editable) return;
    setPlanSource('edited');
    setPlan(p => {
      const rows = [...p[lane]];
      while (rows.length <= i) rows.push({ title: '', detail: '' });
      rows[i] = { ...rows[i], [field]: value };
      return { ...p, [lane]: rows };
    });
    dirty.current = true;
  };

  const dropLane = (lane: 'now' | 'next', i: number) => {
    setPlanSource('edited');
    if (!editable) return;
    setPlan(p => ({ ...p, [lane]: p[lane].filter((_, n) => n !== i) }));
    dirty.current = true;
  };

  const LANES: { key: 'now' | 'next'; label: string; hint: string }[] = [
    { key: 'now', label: 'Next 30 days', hint: 'What the team starts on as soon as this report goes out.' },
    { key: 'next', label: 'The month after', hint: 'What follows once the work above is in place.' },
  ];

  /** The Next Plan of Action: an opening line and two lanes of three. */
  const planEditor = () => (
    <>
      {editable && (
        <div className="rb-plan-ai">
          {(plan.now.length > 0 || plan.next.length > 0) && (
            <span className={`rb-story-tag ${planSource === 'ai' ? 'ai' : 'own'}`}>
              {planSource === 'ai' ? 'Written by AI' : 'Your words'}
            </span>
          )}
          <span className="rb-plan-ai-note">
            {planWriting ? 'Writing the plan from this report\'s figures…'
              : plan.now.length || plan.next.length ? 'Edit any line below, or have it rewritten.' : 'No plan yet.'}
          </span>
          <button
            className="btn btn-secondary btn-sm"
            disabled={planWriting}
            onClick={async () => {
              if (planSource === 'edited' && (plan.now.length || plan.next.length)
                && !(await confirmDialog({ title: 'Replace your edited plan?', message: 'A new AI draft will replace the plan you edited.', confirmText: 'Replace', tone: 'danger' }))) return;
              writePlan(true);
            }}
          >
            {planWriting ? <><Loader2 size={13} className="spin" /> Writing…</>
              : <><Sparkles size={13} /> {plan.now.length || plan.next.length ? 'Rewrite with AI' : 'Write with AI'}</>}
          </button>
        </div>
      )}

      <div className="rb-copy-field">
        <label className="form-label">Opening line <span className="rb-opt">optional</span></label>
        <input
          className="form-input"
          value={plan.lede}
          disabled={!editable}
          placeholder="Where we go from here"
          onChange={e => { setPlan(p => ({ ...p, lede: e.target.value })); setPlanSource('edited'); dirty.current = true; }}
        />
      </div>

      {LANES.map(lane => (
        <div className="rb-plan-lane" key={lane.key}>
          <div className="rb-plan-lane-head">
            <h3 className="rb-group-title">{lane.label}</h3>
            <p className="rb-group-sub">{lane.hint}</p>
          </div>

          {[0, 1, 2].map(i => {
            const row = plan[lane.key][i] || { title: '', detail: '' };
            const filled = !!row.title.trim();
            return (
              <div className={`rb-plan-row ${filled ? 'filled' : ''}`} key={i}>
                <span className="rb-plan-num">{i + 1}</span>
                <div className="rb-plan-fields">
                  <input
                    className="form-input"
                    value={row.title}
                    disabled={!editable}
                    placeholder={i === 0 ? 'What we will do' : 'Add another (optional)'}
                    onChange={e => setLane(lane.key, i, 'title', e.target.value)}
                  />
                  {filled && (
                    <input
                      className="form-input rb-plan-detail"
                      value={row.detail}
                      disabled={!editable}
                      placeholder="Why it matters — one line"
                      onChange={e => setLane(lane.key, i, 'detail', e.target.value)}
                    />
                  )}
                </div>
                {filled && editable && (
                  <button
                    type="button"
                    className="btn ghost btn-sm"
                    aria-label={`Remove item ${i + 1}`}
                    onClick={() => dropLane(lane.key, i)}
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </>
  );

  // ── The builder, slide by slide ───────────────────────────────────────

  /** Show or hide one slide in the report. */
  const toggleSlide = async (key: string, shown: boolean) => {
    setSlideBusy(key);
    try {
      await queueSave();
      const res = await api.put(`${base}/slides`, { key, shown });
      if (res.data?.slides) setSlides(res.data.slides);
      if (res.data?.selectedSections) setSectionOn(res.data.selectedSections);
    } catch {
      // Handled by global interceptor
    }
    setSlideBusy(null);
  };

  /** A slide's printed title: what was typed, else its default. */

  /** Items a figures or rows part draws, by exact id or by prefix. */
  const partItems = (part: SlidePart, kinds: Item['kind'][]) => items.filter(i =>
    kinds.includes(i.kind)
    && (part.ids ? part.ids.includes(i.id) : part.prefix ? i.id.startsWith(part.prefix) : false),
  ).sort((a, b) => (part.ids ? part.ids.indexOf(a.id) - part.ids.indexOf(b.id) : 0));

  /** Where a step's numbers come from: the connection, a fetch, a sheet. */
  const sourcePanel = (section: string) => {
    const provider = isProvider(section);
    const live = provider && connected(section);
    const typedIn = provider && !live;
    const dataPage = DATA_PAGE[section] && clientId ? DATA_PAGE[section](clientId) : null;
    const name = PROVIDER_NAME[section] || sections.find(x => x.key === section)?.label || section;
    // Last month is final once published: it comes from that sheet, not from this draft.
    const published = !!period?.compare?.published;
    const compareNote = published && dataPage
      ? <>; last month comes from the published <Link to={dataPage}>{SHEET_NAME[section] || name} sheet</Link></>
      : null;
    return (
      <div key={section} className="rb-source-block">
        {live ? (
          <div className="rb-source auto">
            <Plug size={15} />
            <span>
              <strong>{name} is connected.</strong> This month's figures are fetched from it into this report
              {compareNote}. Every number below can still be corrected by hand.
            </span>
            {fetchButton(section)}
          </div>
        ) : typedIn ? (
          <div className="rb-source manual">
            <Pencil size={15} />
            <span>
              <strong>{name} isn't connected</strong> — type this month's figures below, or upload a sheet{compareNote}.{' '}
              <Link to={`/admin/clients/${clientId}/connections`}>Connect it</Link> to fetch them automatically.
            </span>
          </div>
        ) : (
          <div className="rb-source">
            <Info size={15} />
            <span>
              <strong>{name}</strong> — type this month's below, or upload a sheet{compareNote}.
            </span>
          </div>
        )}
        {uploadBox(section)}
        {typedIn && !hasData(section) && (
          <p className="rb-hint">Enter {NEEDS[section]} below, or upload a sheet, for these slides to print.</p>
        )}
      </div>
    );
  };

  /** Many rows as one compact table: show, name, and each figure's boxes
   *  (initial, last month, this month when they exist), with the change. */
  const rowsTable = (list: Item[]) => {
    const withInit = list.some(i => initialOf(i));
    const withPrev = list.some(i => prevOf(i));
    const numeric = list.some(i => i.editable && i.format !== 'bool');
    // Name the value column for what it is: "Count", "Sessions", …
    const unit = list.find(i => i.unit)?.unit;
    const valueCol = withPrev ? 'This month' : unit ? unit.charAt(0).toUpperCase() + unit.slice(1) : 'Value';
    return (
      <div className="rb-rows-wrap">
        <table className="rb-rows">
          <thead>
            <tr>
              <th className="show">Show</th>
              <th>Name</th>
              {withInit && <th className="num">Initial</th>}
              {withPrev && <th className="num">Last month</th>}
              <th className="num">{valueCol}</th>
              {withPrev && <th className="num">Change</th>}
            </tr>
          </thead>
          <tbody>
            {list.map(i => {
              const prev = prevOf(i), init = initialOf(i);
              const change = prev ? changeText(i, values[prev.id] ?? '', values[i.id] ?? '') : null;
              const on = itemOn[i.id] !== false;
              return (
                <tr key={i.id} className={on ? '' : 'off'}>
                  <td className="show"><input type="checkbox" checked={on} disabled={!editable} onChange={() => toggleItem(i.id)} aria-label={`Show ${i.label}`} /></td>
                  <td className="name" title={i.label}>{i.label}</td>
                  {withInit && <td className="num">{init ? valueInput(init, false, true) : '—'}</td>}
                  {withPrev && <td className="num">{prev ? valueInput(prev, false, true) : '—'}</td>}
                  <td className="num">{i.editable && numeric ? valueInput(i, false, true) : display(values[i.id] ?? '', i.format)}</td>
                  {withPrev && <td className={`num change ${change?.tone || ''}`}>{change?.tone === 'none' ? '—' : change?.text.replace(' vs last month', '')}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  /** Prompt checks as the slide shows them: prompts down the side, the
   *  assistants across; click a cell to switch it between yes and no. */
  const aiMatrix = (list: Item[]) => {
    const parse = (i: Item) => {
      const rest = i.id.slice('ai_visibility.'.length);
      const cut = rest.lastIndexOf('.');
      const label = i.label.includes(' · ') ? i.label.split(' · ').slice(1).join(' · ') : i.label;
      return { prompt: rest.slice(0, cut), platform: rest.slice(cut + 1), label };
    };
    const rows: { prompt: string; label: string; cells: Record<string, Item> }[] = [];
    const engines: string[] = [];
    for (const i of list) {
      const { prompt, platform, label } = parse(i);
      if (!engines.includes(platform)) engines.push(platform);
      let row = rows.find(r => r.prompt === prompt);
      if (!row) { row = { prompt, label, cells: {} }; rows.push(row); }
      row.cells[platform] = i;
    }
    const name = (p: string) => ({ chatgpt: 'ChatGPT', google_ai_overview: 'AI Overview', gemini: 'Gemini', perplexity: 'Perplexity', claude: 'Claude', grok: 'Grok' } as Record<string, string>)[p] || p.replace(/_/g, ' ');
    const pending = list.some(i => i.pending);
    const carried = pending && list.some(i => values[i.id] === 'true');
    return (
      <>
      {pending && (
        <div className="rb-ai-pending">
          <Info size={15} />
          <span>
            {carried
              ? <><strong>These are last month's answers</strong>, from the published sheet. Switch what's different this month, or confirm them as they are.</>
              : <><strong>Mark which assistants named the brand this month.</strong> Nothing from this grid prints until it's answered.</>}
          </span>
          {editable && (
            <button className="btn btn-secondary btn-sm" onClick={() => confirmAi(list)}>
              <Check size={13} /> {carried ? "Confirm last month's answers" : 'All answers are correct'}
            </button>
          )}
        </div>
      )}
      <div className="rb-rows-wrap">
        <table className="rb-rows rb-matrix">
          <thead>
            <tr>
              <th className="show">Show</th>
              <th>Prompt</th>
              {engines.map(e => <th key={e} className="num">{name(e)}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const items_ = Object.values(r.cells);
              const on = items_.some(i => itemOn[i.id] !== false);
              return (
                <tr key={r.prompt} className={on ? '' : 'off'}>
                  <td className="show">
                    <input type="checkbox" checked={on} disabled={!editable} aria-label={`Show ${r.label}`}
                      onChange={() => items_.forEach(i => (itemOn[i.id] !== false) === on && toggleItem(i.id))} />
                  </td>
                  <td className="name" title={r.label}>{r.label}</td>
                  {engines.map(e => {
                    const i = r.cells[e];
                    if (!i) return <td key={e} className="num">—</td>;
                    const yes = values[i.id] === 'true';
                    return (
                      <td key={e} className="num">
                        <button type="button" className={`rb-seen ${yes ? 'yes' : 'no'}`} disabled={!editable}
                          title="Click to switch" onClick={() => setValue(i.id, yes ? 'false' : 'true')}>
                          {yes ? 'Yes' : 'No'}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      </>
    );
  };

  /** Take the AI grid as this month's answers, unchanged. One answer sent
   *  confirms them all on the server. */
  const confirmAi = async (list: Item[]) => {
    const first = list[0];
    if (!first) return;
    try { await queueSave(); } catch (e) { return; }
    try {
      const res = await api.put(`${base}/values`, { edits: { [first.id]: values[first.id] === 'true' } });
      setItems(l => l.map(x => (x.section === 'ai_visibility' ? { ...x, pending: false } : x)));
      if (res.data?.slides) setSlides(res.data.slides);
      if (res.data?.kpiCards) setKpiList(res.data.kpiCards);
      toast.success("This month's AI answers are set.");
    } catch {
      // Handled by global interceptor
    }
  };

  /** One slide's numbers part. */
  const partView = (_sl: SlideDef, part: SlidePart, n: number) => {
    const head = (label?: string, hint?: string) => (label || hint) ? (
      <div className="rb-part-head">
        {label && <span className="rb-part-label">{label}</span>}
        {hint && <span className="rb-part-hint">{hint}</span>}
      </div>
    ) : null;

    if (part.type === 'figures') {
      const list = partItems(part, ['headline', 'summary']);
      if (!list.length) return null;
      return (
        <div key={n} className="rb-part">
          {head(part.label, part.hint)}
          <div className={list.some(i => prevOf(i)) ? 'rb-pair-grid' : 'metric-grid'}>{list.map(i => figure(i, false))}</div>
        </div>
      );
    }
    if (part.type === 'rows') {
      const list = partItems(part, ['row']);
      if (!list.length) return <div key={n} className="rb-part">{head(part.label, part.hint)}<div className="rb-empty">Nothing here yet.</div></div>;
      const shown = list.filter(i => itemOn[i.id] !== false).length;
      return (
        <div key={n} className="rb-part">
          <div className="rb-part-head">
            <span className="rb-part-label">{part.label} · {shown} of {list.length} shown</span>
            {part.hint && <span className="rb-part-hint">{part.hint}</span>}
            {editable && (
              <span className="rb-part-actions">
                <button className="btn ghost btn-sm" onClick={() => list.forEach(i => itemOn[i.id] === false && toggleItem(i.id))}>Select all</button>
                <button className="btn ghost btn-sm" onClick={() => list.forEach(i => itemOn[i.id] !== false && toggleItem(i.id))}>Clear all</button>
              </span>
            )}
          </div>
          {part.prefix === 'ai_visibility.' ? aiMatrix(list) : rowsTable(list)}
        </div>
      );
    }
    if (part.type === 'table') {
      const spec = listSpecs.find(x => x.path === part.path);
      if (!spec) return null;
      return (
        <div key={n} className="rb-part">
          <ListEditor base={base} spec={spec} rows={lists[spec.path] || []} editable={editable}
            defaultOpen={spec.path === 'links' || spec.path === 'activities'}
            onSaved={rows => {
              setLists(l => ({ ...l, [spec.path]: rows }));
              // A list that is the slide itself: its status and figures follow.
              if (spec.path === 'links' || spec.path === 'activities') {
                api.get(`${base}/composer`).then(r => applyComposer(r.data || {})).catch(() => {});
              }
            }} />
        </div>
      );
    }
    if (part.type === 'shots') {
      return (
        <div key={n} className="rb-part">
          <ReportShots base={base} section={part.section || ''} editable={editable} title={part.label || 'Screenshots'} hint={part.hint || ''} />
        </div>
      );
    }
    if (part.type === 'months') {
      const table = monthTable(part.section || '');
      return table ? <div key={n} className="rb-part">{table}</div> : null;
    }
    // Purpose-built editors, known by name.
    const body = part.name === 'brand_line' ? (
      <input className="form-input rb-brand" maxLength={80} placeholder={brandDefault} value={copy.brand_line}
        disabled={!editable} onChange={e => setBrand(e.target.value)} />
    ) : part.name === 'kpi_cards' ? kpiCards()
      : part.name === 'rank_summary' ? rankingSummary()
      : part.name === 'add_keyword' ? addKeywordForm()
      : part.name === 'ai_summary' ? aiSummaryEditor()
      : part.name === 'add_prompt' ? addPromptForm()
      : part.name === 'plan' ? planEditor()
      : null;
    if (!body) return null;
    const own = part.name === 'brand_line' || part.name === 'kpi_cards';
    return (
      <div key={n} className="rb-part">
        {own && head(part.label, part.hint)}
        {body}
      </div>
    );
  };

  /** The headline cards on Performance Highlight — the slide's own list,
   *  with the values it will print — and a switch for each. */
  const kpiCards = () => (
    kpiList.length === 0
      ? <div className="rb-empty">No cards yet — they appear once the report has figures.</div>
      : (
        <div className="rb-toggle-grid">
          {kpiList.map(c => (
            <label key={c.id} className={`rb-toggle ${c.shown ? 'on' : ''}`}>
              <input type="checkbox" checked={c.shown} disabled={!editable} onChange={async () => {
                setKpiList(list => list.map(x => (x.id === c.id ? { ...x, shown: !c.shown } : x)));
                try {
                  const res = await api.put(`${base}/cards`, { id: c.id, shown: !c.shown });
                  if (res.data?.kpiCards) setKpiList(res.data.kpiCards);
                } catch {
                  // Handled by global interceptor
                }
              }} />
              <span className="rb-toggle-text">
                <span className="rb-toggle-title">{c.name}</span>
                <span className="rb-toggle-sub">{c.value}</span>
              </span>
            </label>
          ))}
        </div>
      )
  );

  /** The heading of one slide: the label above, the title, the line under. */
  const headingEditor = (sl: SlideDef) => {
    const h = headings.find(x => x.key === sl.heading);
    if (!h) return null;
    const isCover = h.key === 'exec_summary';
    const fields = sl.heading_fields || ['eyebrow', 'title', 'subtitle'];
    const fill = (t: string) => t.replace('{period}', periodLabel).replace('{client}', client?.name || 'Client');
    const aiSub = subtitleAi.includes(h.key) && (copy.subtitles[h.key] || '').trim();
    return (
      <div className="rb-words-grid">
        {fields.includes('eyebrow') && (
          <label className="rb-copy-field">
            <span>Label above the title <em>the small gold word</em></span>
            <input className="form-input" maxLength={60} placeholder={h.eyebrow || ''} value={copy.eyebrows[h.key] ?? ''}
              disabled={!editable} onChange={e => setEyebrow(h.key, e.target.value)} />
          </label>
        )}
        <label className="rb-copy-field">
          <span>{isCover ? 'Client name' : 'Title'} <em>{isCover ? 'the big text' : 'blank keeps the grey default'}</em></span>
          <input className="form-input" maxLength={120} placeholder={fill(h.title)} value={copy.titles[h.key] ?? ''}
            disabled={!editable} onChange={e => setTitle(h.key, e.target.value)} />
        </label>
        {fields.includes('subtitle') && <label className="rb-copy-field wide">
          <span>
            {isCover ? 'Tagline' : 'Subtitle'} <em>{isCover ? 'the line under the client name' : 'one line under the title'}</em>
            {aiSub && <span className="rb-story-tag ai">Written by AI</span>}
          </span>
          <input className="form-input" maxLength={280}
            placeholder={isCover ? 'What the client does, e.g. “AI SEO company in India”' : 'e.g. “Clicks rose 19% to 138”'}
            value={copy.subtitles[h.key] ?? ''} disabled={!editable} onChange={e => setSubtitle(h.key, e.target.value)} />
        </label>}
      </div>
    );
  };

  /** Any other wording a slide prints, folded away. */
  const moreWording = (keys: string[]) => {
    const fields = keys.map(k => textFields.find(f => f.key === k)).filter(Boolean) as TextField[];
    if (!fields.length) return null;
    const edited = fields.filter(f => (copy.texts[f.key] ?? '').trim()).length;
    return (
      <details className="rb-wording">
        <summary>
          <span className="rb-inline"><Type size={12} /> Other wording on this slide</span>
          <span className="rb-wording-count">{edited > 0 ? `${edited} changed · ${fields.length} in all` : `${fields.length} labels`}</span>
        </summary>
        <p className="rb-note" style={{ margin: '8px 0 10px' }}>Card names, column headings and small print. Blank keeps the grey default.</p>
        <div className="rb-wording-grid">
          {fields.map(f => (
            <label className="rb-copy-field" key={f.key}>
              <span>{f.label}</span>
              <input className="form-input" maxLength={160} placeholder={f.default} value={copy.texts[f.key] ?? ''}
                disabled={!editable} onChange={e => setText(f.key, e.target.value)} />
            </label>
          ))}
        </div>
      </details>
    );
  };

  /** One slide: what it is, whether it prints, its numbers and its words. */
  const slideCard = (sl: SlideDef, number: number) => {
    const shown = sl.state !== 'hidden';
    const numbers = sl.parts.map((part, n) => (part.words ? null : partView(sl, part, n))).filter(Boolean);
    // Words follow the slide top to bottom: anything printed above the title
    // (the cover's brand line) first, the title, then what sits below it.
    const wordParts = sl.parts.map((part, n) => (part.words && !part.after_heading ? partView(sl, part, n) : null)).filter(Boolean);
    const wordPartsAfter = sl.parts.map((part, n) => (part.words && part.after_heading ? partView(sl, part, n) : null)).filter(Boolean);
    const summary = sl.narration ? summaryEditor(sl.narration) : null;
    const heading = headingEditor(sl);
    const wording = moreWording(sl.texts || []);
    const words = wordParts.length > 0 || wordPartsAfter.length > 0 || heading || summary || wording;
    return (
      <section key={sl.key} id={`slide-${sl.key}`} className={`rb-slide ${sl.state}`}>
        <header className="rb-slide-head">
          <span className="rb-slide-num">{number}</span>
          <div className="rb-slide-title">
            <h3>{sl.name}</h3>
            <p>{sl.about}</p>
          </div>
          <div className="rb-slide-side">
            <span className={`rb-slide-state ${sl.state}`}>
              {sl.state === 'in' ? 'In the report' : sl.state === 'hidden' ? 'Switched off' : 'Not in the report yet'}
            </span>
            {editable && sl.key !== 'cover' && (
              <label className={`rb-switch ${shown ? 'on' : ''}`} title={shown ? 'Leave this slide out' : 'Put this slide back in'}>
                <input type="checkbox" checked={shown} disabled={slideBusy === sl.key} onChange={() => toggleSlide(sl.key, !shown)} />
                <span className="rb-switch-track"><span className="rb-switch-dot" /></span>
                <span className="rb-switch-text">Show</span>
              </label>
            )}
          </div>
        </header>
        {sl.state !== 'hidden' && sl.why && (
          <div className="rb-slide-why"><Info size={13} /> {sl.state === 'in' ? <>Prints as it is now — {sl.why.charAt(0).toLowerCase() + sl.why.slice(1)}</> : sl.why}</div>
        )}

        {shown && (
          <div className="rb-slide-body">
            {numbers.length > 0 && (
              <div className="rb-slide-part">
                <div className="rb-slide-part-title"><span>1</span> Numbers</div>
                {sl.note && <p className="rb-note" style={{ marginTop: 0 }}>{sl.note}</p>}
                {numbers}
              </div>
            )}
            {words && (
              <div className="rb-slide-part">
                <div className="rb-slide-part-title"><span>{numbers.length > 0 ? 2 : 1}</span> Words</div>
                {wordParts}
                {heading}
                {wordPartsAfter.length > 0 && <div className="rb-words-after">{wordPartsAfter}</div>}
                {summary && <div className="rb-words-summary">{summary}</div>}
                {wording}
              </div>
            )}
          </div>
        )}
      </section>
    );
  };

  /** One step: where its numbers come from, then each of its slides. */
  const renderSlidesStep = (stepKey: string) => {
    const def = stepDefs.find(x => x.key === stepKey);
    const mine = slides.filter(x => x.step === stepKey);
    const sources = Array.from(new Set(mine.map(x => x.section).filter(Boolean))) as string[];
    const printing = mine.filter(x => x.state === 'in').length;
    return (
      <>
        <div className="rb-panel-head">
          <div>
            <h2 className="rb-panel-title">{def?.label}</h2>
            <p className="rb-panel-sub">
              {def?.about} {mine.length > 1 && <>· {printing} of {mine.length} slides in the report</>}
            </p>
          </div>
        </div>

        {stepKey === 'start' && period && (
          <div className="rb-period">
            <div className="rb-period-main">
              <CalendarRange size={18} />
              <div>
                <div className="rb-period-title">{period.label}{period.months > 1 ? ` · ${period.months} months combined` : ''}</div>
                <div className="rb-period-sub">
                  {period.range || ''}{period.range ? ' · ' : ''}
                  {period.months > 1
                    ? `every figure below is the total of all ${period.months} months; the report's % is ${period.compare?.range || 'the current month against the earlier months’ average'}`
                    : period.compare?.hasData
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

        {sources.length > 0 && (
          <div className="rb-sources">
            <div className="rb-sources-title">Where these numbers come from</div>
            {sources.map(sourcePanel)}
          </div>
        )}

        {mine.map(sl => slideCard(sl, slides.indexOf(sl) + 1))}
      </>
    );
  };

  /** Rewrite what the AI wrote from the figures as they are now. */
  const rewriteAi = async () => {
    setAiRewriting(true);
    try { await queueSave(); } catch (e) { setAiRewriting(false); return; }
    try {
      const res = await api.post(`${base}/ai-text/refresh`);
      applyComposer(res.data || {});
      toast.success('Written with AI — edit anything you like.');
    } catch {
      // Handled by global interceptor
    }
    setAiRewriting(false);
  };

  const renderReview = () => (
    <>
      <div className="rb-panel-head">
        <div>
          <h2 className="rb-panel-title"><FileText size={18} /> Review &amp; generate</h2>
          <p className="rb-panel-sub">
            Every slide, in the order it prints. Click Edit to jump straight to one — nothing is
            final until the report is published.
          </p>
        </div>
      </div>
      {editable && (
        <div className="rb-upload" style={{ marginBottom: 14 }}>
          <div className="rb-upload-text">
            <Sparkles size={16} />
            <span>
              <strong>Summaries, subtitles and plan</strong>
              Nothing is written by AI until you ask. Write them all from the figures as they are now — anything you typed yourself stays as it is.
            </span>
          </div>
          <div className="rb-upload-actions">
            <button className="btn btn-primary btn-sm" disabled={aiRewriting} onClick={rewriteAi}>
              {aiRewriting ? <><Loader2 size={13} className="spin" /> Rewriting…</> : <><Sparkles size={13} /> Write with AI</>}
            </button>
          </div>
        </div>
      )}
      <div className="rb-review">
        {slides.map((sl, n) => (
          <div key={sl.key} className={`rb-review-row ${sl.state === 'in' ? '' : 'off'}`}>
            <span className="rb-review-name"><span className="rb-review-num">{n + 1}</span> {sl.name}</span>
            <span className="rb-review-meta">
              {sl.state === 'in'
                ? (sl.why || (sl.narration ? (narration[sl.narration]?.trim() ? 'Summary written' : 'No summary') : ''))
                : sl.why}
            </span>
            <span className={`rb-pill ${sl.state === 'in' ? 'on' : ''}`}>
              {sl.state === 'in' ? 'In' : sl.state === 'hidden' ? 'Off' : 'Empty'}
            </span>
            <button type="button" className="rb-jump" onClick={() => goToSlide(sl)}>Edit</button>
          </div>
        ))}
      </div>
      <p className="rb-note" style={{ marginTop: 10 }}>
        {slides.filter(x => x.state === 'in').length} of {slides.length} slides will print. Slides marked Empty print once they have figures; Off slides are switched off on their card.
      </p>

      {staleSources.length > 0 && (
        <div className="notice notice-danger rb-blocker">
          <p className="notice-title">
            {staleSources.length === 1 ? 'One source is not connected' : `${staleSources.length} sources are not connected`}
          </p>
          <p className="notice-body">
            The report prints these figures as collected automatically, but nothing is collecting them.
            They are the last figures that were stored, and they will not update until the connection works.
          </p>
          <ul className="rb-blocker-list">
            {staleSources.map(s => (
              <li key={s.key}>
                <strong>{s.name}</strong>
                <span>
                  {s.stale
                    ? ` — the newest stored figures are from ${s.newest}, before this reporting period even began.`
                    : s.lastSync
                      ? ` — last collected ${s.lastSync}; the connection has been failing since.`
                      : ' — has never successfully collected anything.'}
                </span>
                {s.lastError && <span className="rb-blocker-why">{s.lastError}</span>}
              </li>
            ))}
          </ul>
          <div className="rb-blocker-actions">
            <Link to={`/admin/clients/${clientId}/connections`} className="btn btn-secondary btn-sm">
              <Plug size={14} /> Fix the connection
            </Link>
            {editable && (
              <label className="rb-blocker-ack">
                <input type="checkbox" checked={ackStale} onChange={e => setAckStale(e.target.checked)} />
                <span>I have checked these figures and want to send the report anyway</span>
              </label>
            )}
          </div>
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
                  {s.kind === 'slides' && (() => {
                    const mine = slides.filter(x => x.step === s.key);
                    const printing = mine.filter(x => x.state === 'in').length;
                    return mine.length > 0 ? <span className="rb-tab-state">{printing}/{mine.length}</span> : null;
                  })()}
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
            {cur.kind === 'review' ? renderReview() : renderSlidesStep(cur.key)}
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
              <button
                className={`btn ${editable && step === steps.length - 1 ? 'btn-secondary' : 'btn-primary'}`}
                onClick={finish}
                disabled={finishing || mustAcknowledge}
                title={mustAcknowledge
                  ? 'A source this report uses is not connected — review it on the last step first'
                  : undefined}
              >
                {finishing
                  ? <><Loader2 size={14} className="spin" /> Saving…</>
                  : editable ? (step === steps.length - 1 ? 'Preview report' : 'Generate Report') : 'View report'}
              </button>
              {editable && step === steps.length - 1 && (
                <button className="btn btn-primary rb-publish" onClick={publish} disabled={finishing || mustAcknowledge}
                  title="Make this month final on every sheet">
                  <Check size={14} /> Publish
                </button>
              )}
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
