import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import * as XLSX from 'xlsx';
import { toast } from 'sonner';
import { Download, ExternalLink, Search, Table2, X, EyeOff, Lock, Pencil, Info } from 'lucide-react';
import api from '../../api/client';
import Page, { Empty } from '../ui/Page';
import PageSkeleton from '../ui/PageSkeleton';
import '../../sheets.css';

type Cell = { value: number | null; text: string | null; edited: boolean };
type Row = {
  key: string; label: string; group: string; format: string;
  cells: Record<string, Cell>; extra?: Record<string, number | null>;
};
type Month = { key: string; label: string; report: string | null };
type SheetData = {
  sheet: string; name: string; months: Month[];
  extraColumns: { key: string; label: string }[];
  groups: { name: string; rows: Row[] }[];
  editable: boolean;
};

const ASSISTANT: Record<string, string> = {
  chatgpt: 'ChatGPT', google_ai_overview: 'AI Overview', ai_mode: 'AI Mode', gemini: 'Gemini',
  perplexity: 'Perplexity', claude: 'Claude', grok: 'Grok',
};

/** Rows whose figure is better when it is lower. */
const lowerIsBetter = (r: Row) => r.format === 'position' || r.format === 'int_low';

const fmt = (v: number | null | undefined, format: string): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return '';
  switch (format) {
    case 'percent': return `${v < 10 ? v.toFixed(2) : v.toFixed(0)}%`;
    case 'position': return Number.isInteger(v) ? String(v) : v.toFixed(1);
    case 'money': return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    case 'seconds': { const s = Math.round(v); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; }
    default: return Math.round(v).toLocaleString();
  }
};

const checksOf = (text: string | null) =>
  (text || '').split(',').filter(Boolean).map(p => { const [k, f] = p.split(':'); return { k, yes: f === '1' }; });

const monthRange = [
  { key: '6', label: 'Last 6 months' },
  { key: '12', label: 'Last 12 months' },
  { key: 'all', label: 'All months' },
];

/**
 * One of the client's month-on-month sheets. A column per published month,
 * the figures exactly as that month's report printed them. Read-only for
 * everyone but a super admin, who can correct a cell in place.
 */
export default function SheetView({ sheet, screen, detailsLabel }: { sheet: string; screen: string; detailsLabel?: string }) {
  const { clientId } = useParams();
  const [data, setData] = useState<SheetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [range, setRange] = useState<string>(() => {
    try { return localStorage.getItem('sheet.range') || '12'; } catch { return '12'; }
  });
  const [editing, setEditing] = useState<{ row: string; month: string } | null>(null);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [details, setDetails] = useState<{ month: Month; rows: any[] } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/clients/${clientId}/sheets/${sheet}`);
      setData(res.data);
    } catch {
      // Handled by global interceptor
    } finally {
      setLoading(false);
    }
  }, [clientId, sheet]);

  useEffect(() => { setLoading(true); setData(null); setDetails(null); load(); }, [load]);
  useEffect(() => { try { localStorage.setItem('sheet.range', range); } catch { /* per-viewer only */ } }, [range]);
  useEffect(() => { if (editing) inputRef.current?.select(); }, [editing]);
  // Open on the newest months: with many, they sit past the right edge.
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [data, range]);

  const months = useMemo(() => {
    const all = data?.months || [];
    return range === 'all' ? all : all.slice(-Number(range));
  }, [data, range]);
  const last = months[months.length - 1];
  // The month the latest one is compared with: the one before it unless
  // another is chosen.
  const [compareKey, setCompareKey] = useState<string>('');
  const earlier = (data?.months || []).filter(m => last && m.key < last.key);
  const before = earlier.find(m => m.key === compareKey) || earlier[earlier.length - 1];

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.groups || [])
      .map(g => ({ ...g, rows: q ? g.rows.filter(r => r.label.toLowerCase().includes(q)) : g.rows }))
      .filter(g => g.rows.length);
  }, [data, query]);
  const rowCount = groups.reduce((n, g) => n + g.rows.length, 0);

  const startEdit = (row: Row, month: Month) => {
    if (!data?.editable || row.format === 'checks') return;
    const cell = row.cells[month.key];
    setEditing({ row: row.key, month: month.key });
    setDraft(cell?.value !== null && cell?.value !== undefined ? String(cell.value) : '');
  };

  const commit = async () => {
    if (!editing || !data) return;
    const row = data.groups.flatMap(g => g.rows).find(r => r.key === editing.row);
    const before_ = row?.cells[editing.month]?.value ?? null;
    const raw = draft.trim().replace(/,/g, '').replace(/%$/, '');
    const value = raw === '' ? null : Number(raw);
    if (value !== null && (Number.isNaN(value) || value < 0)) { toast.error('Type a number, 0 or more.'); return; }
    if (value === before_) { setEditing(null); return; }
    setSaving(true);
    try {
      const res = await api.put(`/clients/${clientId}/sheets/${sheet}/cell`, { row: editing.row, month: editing.month, value });
      setData(d => d && ({
        ...d,
        groups: d.groups.map(g => ({
          ...g,
          rows: g.rows.map(r => r.key !== editing.row ? r : { ...r, cells: { ...r.cells, [editing.month]: res.data } }),
        })),
      }));
      setEditing(null);
    } catch {
      // Handled by global interceptor
    }
    setSaving(false);
  };

  const stopTracking = async (row: Row) => {
    const what = sheet === 'keywords' ? 'keyword' : 'prompt';
    if (!window.confirm(`Stop tracking “${row.label}”? Its published months stay here; later reports leave it out.`)) return;
    try {
      await api.delete(`/clients/${clientId}/sheets/${sheet}/rows/${encodeURIComponent(row.key)}`);
      toast.success(`The ${what} is no longer tracked.`);
    } catch {
      // Handled by global interceptor
    }
  };

  const openDetails = async (month: Month) => {
    if (!detailsLabel) return;
    if (details?.month.key === month.key) { setDetails(null); return; }
    try {
      const res = await api.get(`/clients/${clientId}/sheets/${sheet}/details/${month.key.slice(0, 7)}`);
      setDetails({ month, rows: res.data || [] });
    } catch {
      // Handled by global interceptor
    }
  };

  const exportExcel = () => {
    if (!data) return;
    const all = data.months;
    const header = ['Group', 'Row', ...data.extraColumns.map(c => c.label), ...all.map(m => m.label)];
    const lines: (string | number | null)[][] = [header];
    for (const g of data.groups) {
      for (const r of g.rows) {
        lines.push([
          g.name, r.label,
          ...data.extraColumns.map(c => r.extra?.[c.key] ?? null),
          ...all.map(m => {
            const cell = r.cells[m.key];
            if (!cell) return null;
            if (r.format === 'checks') return checksOf(cell.text).map(c => `${ASSISTANT[c.k] || c.k}: ${c.yes ? 'Yes' : 'No'}`).join(', ');
            return cell.value;
          }),
        ]);
      }
    }
    const ws = XLSX.utils.aoa_to_sheet(lines);
    ws['!cols'] = header.map((_, i) => ({ wch: i === 1 ? 42 : i === 0 ? 22 : 12 }));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, data.name.slice(0, 31));
    XLSX.writeFile(wb, `${data.name.replace(/\s+/g, '-')}.xlsx`);
  };

  if (loading && !data) return <PageSkeleton />;

  const empty = !data || data.months.length === 0;
  const trackedOnly = !empty ? false : (data?.groups || []).some(g => g.rows.length);

  const change = (row: Row) => {
    if (!last || !before) return null;
    const a = row.cells[before.key]?.value, b = row.cells[last.key]?.value;
    if (a === null || a === undefined || b === null || b === undefined) return null;
    const d = b - a;
    if (Math.abs(d) < 1e-9) return <span className="sh-chg flat">–</span>;
    const good = lowerIsBetter(row) ? d < 0 : d > 0;
    if (row.format === 'count') return <span className="sh-chg flat">{d > 0 ? '+' : '−'}{Math.abs(Math.round(d))}</span>;
    const shown = row.format === 'percent' ? `${Math.abs(d) < 1 ? Math.abs(d).toFixed(2) : Math.abs(d).toFixed(1).replace(/\.0$/, '')} pts`
      : row.format === 'position' ? String(Math.abs(Math.round(d * 10) / 10))
      : Math.abs(d) >= 1 ? Math.round(Math.abs(d)).toLocaleString() : Math.abs(d).toFixed(2);
    return <span className={`sh-chg ${good ? 'up' : 'down'}`}>{d > 0 ? '▲' : '▼'} {shown}</span>;
  };

  const cellView = (row: Row, month: Month) => {
    const cell = row.cells[month.key];
    const isEditing = editing?.row === row.key && editing.month === month.key;
    if (isEditing) {
      return (
        <td key={month.key} className="sh-num sh-editing">
          <input
            ref={inputRef}
            className="sh-input"
            value={draft}
            inputMode="decimal"
            disabled={saving}
            onChange={e => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={e => {
              if (e.key === 'Enter') { e.preventDefault(); commit(); }
              if (e.key === 'Escape') setEditing(null);
            }}
            aria-label={`${row.label}, ${month.label}`}
          />
        </td>
      );
    }
    if (row.format === 'checks') {
      const checks = checksOf(cell?.text || null);
      return (
        <td key={month.key} className="sh-checks-cell">
          {checks.length ? (
            <span className="sh-checks" title={checks.map(c => `${ASSISTANT[c.k] || c.k}: ${c.yes ? 'named' : 'not named'}`).join('\n')}>
              {checks.map(c => <i key={c.k} className={c.yes ? 'yes' : ''} />)}
              <b>{checks.filter(c => c.yes).length}/{checks.length}</b>
            </span>
          ) : <span className="sh-blank" />}
        </td>
      );
    }
    const text = fmt(cell?.value, row.format);
    return (
      <td
        key={month.key}
        className={`sh-num ${data?.editable ? 'can-edit' : ''} ${cell?.edited ? 'edited' : ''}`}
        onDoubleClick={() => startEdit(row, month)}
        onKeyDown={e => { if (e.key === 'Enter') startEdit(row, month); }}
        tabIndex={data?.editable ? 0 : undefined}
        title={cell?.edited ? 'Corrected after publishing' : row.format === 'text' ? undefined : cell?.text || undefined}
      >
        {text || <span className="sh-blank" />}
        {cell?.text && sheet === 'work' && <span className="sh-note">{cell.text}</span>}
      </td>
    );
  };

  return (
    <Page
      screen={screen}
      badge={data && !empty ? <span className="sh-badge"><Lock size={11} /> Final figures</span> : undefined}
      actions={
        <>
          {data && !empty && earlier.length > 1 && (
              <select className="sh-range" value={before?.key || ''} onChange={e => setCompareKey(e.target.value)} aria-label="Compare the latest month with" title="Compare the latest month with">
                {earlier.slice().reverse().map(m => <option key={m.key} value={m.key}>Compare with {m.label}</option>)}
              </select>
          )}
          {data && !empty && (
            <select className="sh-range" value={range} onChange={e => setRange(e.target.value)} aria-label="Months shown">
              {monthRange.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
            </select>
          )}
          <button className="btn btn-secondary" onClick={exportExcel} disabled={empty}>
            <Download size={15} /> Download Excel
          </button>
        </>
      }
    >
      {empty && !trackedOnly ? (
        <section className="surface">
          <Empty
            icon={<Table2 size={22} />}
            title="No published months yet"
            hint="This sheet fills in one column each month, the moment that month's report is published. Drafts never change it."
            action={<Link className="btn btn-secondary" to={`/admin/clients/${clientId}`}>Go to reports</Link>}
          />
        </section>
      ) : (
        <section className="surface sh-surface">
          <div className="sh-bar">
            <div className="sh-search">
              <Search size={14} />
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Find a row…" aria-label="Find a row" />
              {query && <button onClick={() => setQuery('')} aria-label="Clear"><X size={13} /></button>}
            </div>
            <span className="sh-meta">
              {rowCount} row{rowCount === 1 ? '' : 's'} · {data?.months.length ? `${data.months.length} month${data.months.length === 1 ? '' : 's'} published` : 'no month published yet'}
            </span>
            {empty ? null : data?.editable
              ? <span className="sh-hint"><Pencil size={12} /> Double-click a figure to correct it</span>
              : null}
          </div>
          {empty && (
            <div className="sh-waiting">
              <Info size={15} />
              <span>These are the tracked {sheet === 'keywords' ? 'keywords' : 'prompts'}. Their positions fill in a column per month as each report is published.</span>
            </div>
          )}

          <div className="sh-scroll" ref={scrollRef}>
            <table className="sh-table">
              <thead>
                <tr>
                  <th className="sh-name">{sheet === 'keywords' ? 'Keyword' : sheet === 'ai' ? 'Prompt / figure' : 'Row'}</th>
                  {data?.extraColumns.map(c => <th key={c.key} className="sh-num sh-extra">{c.label}</th>)}
                  {months.map(m => (
                    <th key={m.key} className={`sh-num sh-month ${m === last ? 'latest' : ''} ${details?.month.key === m.key ? 'open' : ''}`}>
                      {detailsLabel ? (
                        <button className="sh-month-btn" onClick={() => openDetails(m)} title={`Show ${detailsLabel.toLowerCase()} for ${m.label}`}>{m.label}</button>
                      ) : m.label}
                      {m.report && (
                        <Link className="sh-report" to={`/admin/clients/${clientId}/reports/${m.report}`} title={`Open the ${m.label} report`}>
                          <ExternalLink size={11} />
                        </Link>
                      )}
                    </th>
                  ))}
                  <th className="sh-num sh-chg-col" title={before ? `${last?.label} compared with ${before.label}` : undefined}>
                    {before ? <>Change<br /><span className="sh-chg-sub">{last?.label.split(' ')[0]} vs {before.label}</span></> : 'Change'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {groups.map(g => (
                  <React.Fragment key={g.name || '_'}>
                    {g.name && (
                      <tr className="sh-group">
                        <th colSpan={2 + (data?.extraColumns.length || 0) + months.length} scope="colgroup">{g.name}</th>
                      </tr>
                    )}
                    {g.rows.map(r => (
                      <tr key={r.key}>
                        <th scope="row" className="sh-name" title={r.label}>
                          <div className="sh-name-in">
                          <span className="sh-label">{r.label}</span>
                          {data?.editable && (sheet === 'keywords' && r.key.startsWith('kw:') || sheet === 'ai' && r.key.startsWith('prompt:')) && (
                            <button className="sh-untrack" onClick={() => stopTracking(r)} title="Stop tracking">
                              <EyeOff size={12} />
                            </button>
                          )}
                          </div>
                        </th>
                        {data?.extraColumns.map(c => (
                          <td key={c.key} className="sh-num sh-extra">{fmt(r.extra?.[c.key] ?? null, c.key === 'initial' ? 'position' : 'int') || <span className="sh-blank" />}</td>
                        ))}
                        {months.map(m => cellView(r, m))}
                        <td className="sh-num sh-chg-col">{change(r)}</td>
                      </tr>
                    ))}
                  </React.Fragment>
                ))}
                {rowCount === 0 && (
                  <tr><td className="sh-none" colSpan={2 + months.length + (data?.extraColumns.length || 0)}>No rows match “{query}”.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {details && (
            <div className="sh-details">
              <div className="sh-details-head">
                <strong>{detailsLabel} · {details.month.label}</strong>
                <button className="btn ghost btn-sm" onClick={() => setDetails(null)} aria-label="Close"><X size={14} /></button>
              </div>
              {details.rows.length === 0 ? <p className="sh-meta">Nothing listed for this month.</p> : (
                <table className="sh-table sh-mini">
                  <thead>
                    <tr>
                      <th>{sheet === 'links' ? 'Activity' : 'Task'}</th>
                      {sheet === 'links' && <th>URL</th>}
                      {sheet === 'work' && <th>Notes</th>}
                      <th className="sh-num">Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {details.rows.map((d, i) => (
                      <tr key={i}>
                        <td>{d.name}</td>
                        {sheet === 'links' && <td className="sh-url">{d.url ? <a href={d.url} target="_blank" rel="noreferrer">{d.url}</a> : '—'}</td>}
                        {sheet === 'work' && <td>{d.notes || '—'}</td>}
                        <td className="sh-num">{d.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </section>
      )}
    </Page>
  );
}
