import React, { useEffect, useState } from 'react';
import api from '../api/client';
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
  mode: 'new' | 'draft' | 'locked';
  anchor_end: string;
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
  onConfirm: (months: number, info: PeriodsInfo) => void;
  onCancel?: () => void;
  onLoaded?: (info: PeriodsInfo) => void;
}

const SOURCES: [string, string][] = [
  ['gsc', 'GSC'], ['ga4', 'GA4'], ['gbp', 'GBP'], ['rankings', 'Rankings'],
  ['ai_visibility', 'AI'], ['links', 'Links'], ['work', 'Work'],
];

export const periodLabel = (cycles: Cycle[], months: number) => {
  const chosen = cycles.slice(cycles.length - months);
  if (chosen.length === 0) return '';
  return chosen.length === 1 ? chosen[0].label : `${chosen[0].label} – ${chosen[chosen.length - 1].label}`;
};

/**
 * The 30-day cycles a report can cover, as a timeline. The current cycle is
 * always there; earlier ones appear only when data for them is already saved.
 * Clicking a cycle starts the report from it.
 */
const PeriodPicker: React.FC<Props> = ({ clientId, snapshotId, initialMonths, busy, confirmText, onConfirm, onCancel, onLoaded }) => {
  const [info, setInfo] = useState<PeriodsInfo | null>(null);
  const [months, setMonths] = useState(1);
  const [failed, setFailed] = useState(false);

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
      .catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
  }, [clientId, snapshotId]);

  if (failed) return <p className="text-subtle">The report periods could not be loaded.</p>;
  if (!info) return <div className="loader-container"><div className="spinner" /></div>;

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
        Each month is a 30-day cycle.{' '}
        {info.mode === 'new'
          ? 'The current one is fetched from Google when you generate'
          : 'The current one was fetched when this report was generated'}
        ; earlier months come from data already saved — nothing old is pulled again.
      </p>

      {locked && (
        <div className="pp-note">
          <Info size={14} />
          <span>
            This cycle's report is published. The next report can be generated in {info.days_remaining} day
            {info.days_remaining === 1 ? '' : 's'}.
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
