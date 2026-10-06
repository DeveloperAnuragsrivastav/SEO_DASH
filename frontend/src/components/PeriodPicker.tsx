import React, { useEffect, useState } from 'react';
import api, { errorText } from '../api/client';
import { Info, Loader2 } from 'lucide-react';
import '../builder.css';

export interface Cycle {
  label: string;
  range: string;
  start: string;
  end: string;
  current: boolean;
  sources: Record<string, boolean>;
}

export interface PeriodsInfo {
  mode: 'first' | 'new' | 'draft' | 'locked';
  anchor_end: string;
  /** First report only: the period offered before anyone picks. */
  suggested_start?: string;
  /** Locked: the day the next period is over and its report can be made. */
  opens_on?: string;
  report_id: string | null;
  months: number | null;
  days_remaining: number;
  cycles: Cycle[];
  maxMonths: number;
  connected: { gsc: boolean; ga4: boolean };
}

interface Props {
  clientId: string;
  /** Describe this report's own cycles instead of the next report's. */
  snapshotId?: string;
  /** Months selected to begin with; defaults to the draft's own, or 1. */
  initialMonths?: number;
  busy?: boolean;
  confirmText: (months: number, label: string, info: PeriodsInfo) => string;
  /** `period` is set only for a client's first report: the dates picked. */
  onConfirm: (months: number, info: PeriodsInfo, period?: { start: string; end: string }) => void;
  onCancel?: () => void;
  onLoaded?: (info: PeriodsInfo) => void;
}

const SOURCES: [string, string][] = [
  ['gsc', 'GSC'], ['ga4', 'GA4'], ['gbp', 'GBP'], ['rankings', 'Rankings'],
  ['ai_visibility', 'AI'], ['links', 'Links'], ['work', 'Work'],
];

// ── First report: the person picks its period ───────────────────────────
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const day = (s: string) => new Date(`${s}T00:00:00`);
const addDays = (s: string, n: number) => { const d = day(s); d.setDate(d.getDate() + n); return iso(d); };
const addMonths = (s: string, n: number) => { const d = day(s); return iso(new Date(d.getFullYear(), d.getMonth() + n, d.getDate())); };
const fmt = (s: string, year = true) => day(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', ...(year ? { year: 'numeric' } : {}) });
const range = (a: string, b: string) => `${fmt(a, day(a).getFullYear() !== day(b).getFullYear())} – ${fmt(b)}`;
const lengthOf = (a: string, b: string) => Math.round((day(b).getTime() - day(a).getTime()) / 86400000) + 1;

/** Why a picked first period cannot be used (the server checks the same), or null. */
export function firstPeriodProblem(start: string, end: string): string | null {
  const today = iso(new Date());
  if (!start || !end) return 'Pick a start and an end date.';
  if (end >= today) return 'The period has to be over — pick an end date before today.';
  if (start > end) return 'The start date is after the end date.';
  const n = lengthOf(start, end);
  if (n < 7) return 'Pick a period of at least 7 days.';
  if (n > 92) return 'Pick a period of at most 3 months.';
  if (start < addDays(today, -480)) return 'Google keeps 16 months of data — pick a start date in the last 16 months.';
  const next = day(addDays(end, 1)).getDate();
  if (next > 28) return 'End the period on the 1st–27th or on a month’s last day, so every later report can start on the same date each month.';
  return null;
}

const FirstPeriod: React.FC<{
  info: PeriodsInfo; busy?: boolean; onCancel?: () => void;
  onConfirm: (months: number, info: PeriodsInfo, period?: { start: string; end: string }) => void;
}> = ({ info, busy, onCancel, onConfirm }) => {
  const suggestedEnd = info.anchor_end;
  const suggestedStart = info.suggested_start || addDays(addMonths(addDays(suggestedEnd, 1), -1), 0);
  const today = new Date();
  const lastMonthEnd = iso(new Date(today.getFullYear(), today.getMonth(), 0));
  const lastMonthStart = iso(new Date(today.getFullYear(), today.getMonth() - 1, 1));
  const presets = [
    { key: 'cycle', label: suggestedEnd === addDays(iso(today), -1) ? 'Up to yesterday' : `Up to ${fmt(suggestedEnd, false)}`,
      start: suggestedStart, end: suggestedEnd },
    { key: 'month', label: 'Last full month', start: lastMonthStart, end: lastMonthEnd },
  ].filter((p, i, all) => all.findIndex(q => q.start === p.start && q.end === p.end) === i);
  const [start, setStart] = useState(suggestedStart);
  const [end, setEnd] = useState(suggestedEnd);
  const active = presets.find(p => p.start === start && p.end === end)?.key || 'custom';
  const problem = firstPeriodProblem(start, end);
  const n = !problem ? lengthOf(start, end) : 0;
  // One whole period (5 Sep – 4 Oct) is compared with the period before it
  // (5 Aug – 4 Sep); any other length with as many days straight before.
  const wholeCycle = !!end && start === addMonths(addDays(end, 1), -1);
  const prevEnd = start ? addDays(start, -1) : '';
  const prevStart = start && n ? (wholeCycle ? addMonths(start, -1) : addDays(start, -n)) : '';
  const nextStart = end ? addDays(end, 1) : '';
  const startDay = nextStart ? day(nextStart).getDate() : 1;
  const upcoming = !problem ? [0, 1, 2].map(k => {
    const a = addMonths(nextStart, k);
    const b = addDays(addMonths(nextStart, k + 1), -1);
    return { a, b, opens: addDays(b, 1) };
  }) : [];
  const ord = (d: number) => `${d}${d % 10 === 1 && d !== 11 ? 'st' : d % 10 === 2 && d !== 12 ? 'nd' : d % 10 === 3 && d !== 13 ? 'rd' : 'th'}`;

  return (
    <div className="pp">
      <p className="pp-lead">
        This is the client’s <strong>first report</strong>. Choose the period it covers — after this one, a report is due
        every month on the same date, counted from the day after this period ends.
      </p>

      <div className="pp-presets" role="radiogroup" aria-label="Report period">
        {presets.map(p => (
          <button key={p.key} type="button" role="radio" aria-checked={active === p.key}
                  className={`pp-preset ${active === p.key ? 'on' : ''}`} disabled={busy}
                  onClick={() => { setStart(p.start); setEnd(p.end); }}>
            <span className="pp-preset-name">{p.label}</span>
            <span className="pp-preset-range">{range(p.start, p.end)}</span>
          </button>
        ))}
        <span className={`pp-preset custom ${active === 'custom' ? 'on' : ''}`}>
          <span className="pp-preset-name">Custom</span>
          <span className="pp-dates">
            <label><span>From</span><input type="date" value={start} max={addDays(iso(today), -1)} disabled={busy}
                   onChange={e => setStart(e.target.value)} /></label>
            <label><span>To</span><input type="date" value={end} max={addDays(iso(today), -1)} disabled={busy}
                   onChange={e => setEnd(e.target.value)} /></label>
          </span>
        </span>
      </div>

      {problem ? (
        <div className="pp-note warn"><Info size={14} /><span>{problem}</span></div>
      ) : (
        <div className="pp-plan">
          <div><span>This report</span><strong>{range(start, end)}</strong><small>{n} days · fetched from Google when you generate</small></div>
          <div><span>Compared with</span><strong>{range(prevStart, prevEnd)}</strong><small>{wholeCycle ? 'the month before' : `the ${n} days before`}</small></div>
          <div><span>Then, every month on the {ord(startDay)}</span>
            <strong>{upcoming.map(u => range(u.a, u.b)).join(' · ')}</strong>
            <small>each opens the day after it ends — {fmt(upcoming[0].opens, false)}, {fmt(upcoming[1].opens, false)}…</small></div>
        </div>
      )}

      <div className="pp-actions">
        {onCancel && <button className="btn btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button>}
        <button className="btn btn-primary" disabled={busy || !!problem} onClick={() => onConfirm(1, info, { start, end })}>
          {busy ? <><Loader2 size={14} className="spin" /> Working…</> : `Generate ${start && end && !problem ? range(start, end) : 'report'}`}
        </button>
      </div>
    </div>
  );
};

export const periodLabel = (cycles: Cycle[], months: number) => {
  const chosen = cycles.slice(cycles.length - months);
  if (chosen.length === 0) return '';
  return chosen.length === 1 ? chosen[0].label : `${chosen[0].label} – ${chosen[chosen.length - 1].label}`;
};

/**
 * The periods a report can cover, as a timeline (or, for a client's first
 * report, a choice of dates). The current cycle is
 * always there; earlier ones appear only when data for them is already saved.
 * Clicking a cycle starts the report from it.
 */
const PeriodPicker: React.FC<Props> = ({ clientId, snapshotId, initialMonths, busy, confirmText, onConfirm, onCancel, onLoaded }) => {
  const [info, setInfo] = useState<PeriodsInfo | null>(null);
  const [months, setMonths] = useState(1);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.get(`/clients/${clientId}/reports/periods`, { params: snapshotId ? { snapshot_id: snapshotId } : undefined })
      .then(res => {
        if (!alive) return;
        const d: PeriodsInfo = res.data;
        setInfo(d);
        const max = Math.max(1, d.maxMonths || 1);
        setMonths(Math.min(Math.max(initialMonths || d.months || 1, 1), max));
        onLoaded?.(d);
      })
      .catch((e) => { if (alive) setFailed(errorText(e, 'the report periods')); });
    return () => { alive = false; };
  }, [clientId, snapshotId]);

  if (failed) return <p className="text-subtle">{failed}</p>;
  if (!info) return <div className="loader-container"><div className="spinner" /></div>;
  if (info.mode === 'first') return <FirstPeriod info={info} busy={busy} onCancel={onCancel} onConfirm={onConfirm} />;

  const cycles = info.cycles;
  const n = cycles.length;
  const locked = info.mode === 'locked';
  const label = periodLabel(cycles, months);
  const first = cycles[n - months];
  const last = cycles[n - 1];
  const span = first && last
    ? `${first.range.split(' – ')[0]} – ${last.range.split(' – ')[1] ?? last.range}`
    : '';

  return (
    <div className="pp">
      <p className="pp-lead">
        Reports run month to month on this client’s own date.{' '}
        {info.mode === 'new'
          ? 'The current period is fetched from Google when you generate'
          : 'The current period was fetched when this report was generated'}
        ; earlier ones come from data already saved — nothing old is pulled again.
      </p>

      {locked && (
        <div className="pp-note">
          <Info size={14} />
          <span>
            {(() => {
              const n = info.days_remaining;
              const opens = info.opens_on ? fmt(info.opens_on, false) : 'the day the next period ends';
              return `This period’s report is published. The next one opens on ${opens}${n > 0 ? ` — in ${n} day${n === 1 ? '' : 's'}` : ''}.`;
            })()}
          </span>
        </div>
      )}
      {!locked && n === 1 && (
        <div className="pp-note">
          <Info size={14} />
          <span>No earlier data is saved for this client yet, so the report covers {cycles[0].label} only.</span>
        </div>
      )}

      <div className="pp-track" role="listbox" aria-label="Months to include">
        {cycles.map((c, idx) => {
          const inRange = idx >= n - months;
          const fetchable = c.current && info.mode === 'new';
          const shown = SOURCES.filter(([k]) => c.sources[k] || (fetchable && (info.connected as any)[k]));
          return (
            <button
              key={c.end}
              type="button"
              role="option"
              aria-selected={inRange}
              className={`pp-cycle ${inRange ? 'in' : ''} ${idx === n - months ? 'start' : ''}`}
              disabled={locked || busy}
              onClick={() => setMonths(n - idx)}
              title={c.current ? 'This month only' : `Start the report from ${c.label}`}
            >
              {c.current && <span className="pp-now">This month</span>}
              <span className="pp-month">{c.label}</span>
              <span className="pp-range">{c.range}</span>
              <span className="pp-dots">
                {shown.map(([k, name]) => (
                  <span key={k} className={`pp-dot ${c.sources[k] ? 'on' : 'fetch'}`}>{name}</span>
                ))}
                {shown.length === 0 && <span className="pp-dot">Added in the builder</span>}
              </span>
            </button>
          );
        })}
      </div>

      <div className="pp-summary">
        <span><strong>{months} month{months === 1 ? '' : 's'}</strong> · {label} · {span}</span>
        <span className="pp-legend">
          <span className="pp-dot on">Saved</span>
          {info.mode === 'new' && <span className="pp-dot fetch">Fetched on generate</span>}
        </span>
      </div>

      {!locked && n > 1 && (
        <div className="pp-quick">
          <button className="btn ghost btn-sm" onClick={() => setMonths(1)} disabled={busy}>Only {last.label}</button>
          <button className="btn ghost btn-sm" onClick={() => setMonths(n)} disabled={busy}>All {n} months</button>
        </div>
      )}

      <div className="pp-actions">
        {onCancel && <button className="btn btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button>}
        <button className="btn btn-primary" onClick={() => onConfirm(months, info)} disabled={busy || locked}>
          {busy ? <><Loader2 size={14} className="spin" /> Working…</> : confirmText(months, label, info)}
        </button>
      </div>
    </div>
  );
};

export default PeriodPicker;
