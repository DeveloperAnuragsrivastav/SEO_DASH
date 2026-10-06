import { useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Eye, EyeOff, RotateCcw, X } from 'lucide-react';
import api from '../../api/client';

/** One GA4 comparison table as the report prints it (from the server), plus
 *  everything the builder may switch: see slide_deck.comparison_table. */
export interface GTable {
  columns: string[];
  rows: { name: string; cells: Cell[] }[];
  total?: { name: string; cells: Cell[] };
  has_previous: boolean;
  meta: {
    columns: { label: string; field: string | null; off: boolean; change_off: boolean; prev_off: boolean }[];
    rows: { name: string; shown: boolean; edited: boolean; now: Record<string, number>; prev: Record<string, number> }[];
    cells_off: string[];
    edits: Record<string, { now?: Record<string, number>; prev?: Record<string, number> }>;
    has_data_before: boolean;
    max_rows: number;
  };
}
type Cell = { value: string; prev: string | null; change: number | null };
type Settings = {
  cols_off?: string[]; change_off?: string[]; prev_off?: string[]; cells_off?: string[];
  rows?: string[]; edits?: GTable['meta']['edits'];
};

const DEFAULT_ROWS = 4;

/** The settings the table currently has, rebuilt from what the server sent. */
function settingsOf(t: GTable): Settings {
  const cols = t.meta.columns;
  const shown = t.meta.rows.filter(r => r.shown).map(r => r.name);
  const def = t.meta.rows.slice(0, DEFAULT_ROWS).map(r => r.name);
  return {
    cols_off: cols.filter(c => c.off).map(c => c.label),
    change_off: cols.filter(c => c.change_off).map(c => c.label),
    prev_off: cols.filter(c => c.prev_off).map(c => c.label),
    cells_off: t.meta.cells_off,
    rows: shown.join('|') === def.join('|') ? undefined : shown,
    edits: t.meta.edits,
  };
}

const toggle = (list: string[] = [], v: string) => (list.includes(v) ? list.filter(x => x !== v) : [...list, v]);

export default function TableEditor({ base, table, data, editable, onChange }: {
  base: string; table: 'channels' | 'countries'; data: GTable | undefined; editable: boolean;
  onChange: (tables: Record<string, GTable>) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<{ row: string; col: string; top: number; left: number } | null>(null);
  const [draft, setDraft] = useState<{ now: string; prev: string }>({ now: '', prev: '' });
  const popRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (popRef.current && !popRef.current.contains(e.target as Node)) setOpen(null); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(null); };
    const scrolled = (e: Event) => { if (!(popRef.current && e.target instanceof Node && popRef.current.contains(e.target))) setOpen(null); };
    document.addEventListener('mousedown', close); document.addEventListener('keydown', esc);
    window.addEventListener('scroll', scrolled, true);
    return () => {
      document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc);
      window.removeEventListener('scroll', scrolled, true);
    };
  }, [open]);

  const current = useMemo(() => (data ? settingsOf(data) : {}), [data]);
  if (!data || !data.meta || data.meta.columns.length === 0) {
    return <p className="rb-note">No {table === 'channels' ? 'channel' : 'country'} figures yet — fetch Google Analytics, and this table appears here exactly as the report prints it.</p>;
  }
  const meta = data.meta;
  const before = meta.has_data_before;

  const save = async (next: Settings, done?: string) => {
    setBusy(true);
    try {
      const res = await api.put(`${base}/tables`, { table, settings: next });
      onChange(res.data?.tables || {});
      if (done) toast.success(done);
    } catch {
      // The reason is shown by the API client.
    }
    setBusy(false);
  };

  const col = (label: string) => meta.columns.find(c => c.label === label)!;
  const rowMeta = (name: string) => meta.rows.find(r => r.name === name);
  const shownRows = meta.rows.filter(r => r.shown).map(r => r.name);

  const openCell = (row: string, label: string, el: HTMLElement) => {
    if (!editable) return;
    // Placed against the window, not the scrolling table, so it is never cut off.
    const r = el.getBoundingClientRect();
    const width = 260, height = 230;
    const left = Math.max(8, Math.min(window.innerWidth - width - 8, r.left + r.width / 2 - width / 2));
    const top = r.bottom + height + 8 > window.innerHeight ? Math.max(8, r.top - height - 4) : r.bottom + 4;
    const f = col(label).field;
    const rm = rowMeta(row);
    setDraft({
      now: f && rm?.now[f] !== undefined ? String(rm.now[f]) : '',
      prev: f && rm?.prev[f] !== undefined ? String(rm.prev[f]) : '',
    });
    setOpen({ row, col: label, top, left });
  };

  const saveFigures = () => {
    if (!open) return;
    const f = col(open.col).field!;
    const parse = (v: string) => {
      const t = v.trim().replace(/,/g, '');
      if (t === '') return null;
      const n = Number(t);
      return Number.isFinite(n) && n >= 0 ? n : NaN;
    };
    const now = parse(draft.now), prev = parse(draft.prev);
    if (Number.isNaN(now) || Number.isNaN(prev)) { toast.error('Type a number, 0 or more — or leave it blank to keep Google’s.'); return; }
    const edits = JSON.parse(JSON.stringify(current.edits || {}));
    const e = edits[open.row] || (edits[open.row] = {});
    for (const [which, v] of [['now', now], ['prev', prev]] as const) {
      e[which] = { ...(e[which] || {}) };
      if (v === null) delete e[which][f]; else e[which][f] = v;
      if (!Object.keys(e[which]).length) delete e[which];
    }
    if (!Object.keys(e).length) delete edits[open.row];
    setOpen(null);
    save({ ...current, edits }, `${open.row} · ${open.col} updated — totals and rates follow.`);
  };

  const resetCell = () => {
    if (!open) return;
    const f = col(open.col).field!;
    const edits = JSON.parse(JSON.stringify(current.edits || {}));
    for (const which of ['now', 'prev']) {
      if (edits[open.row]?.[which]) { delete edits[open.row][which][f]; if (!Object.keys(edits[open.row][which]).length) delete edits[open.row][which]; }
    }
    if (edits[open.row] && !Object.keys(edits[open.row]).length) delete edits[open.row];
    setOpen(null);
    save({ ...current, edits }, 'Back to Google’s figure.');
  };

  const cellKey = (row: string, label: string) => `${row}|${label}`;
  const cellOff = (row: string, label: string) => (current.cells_off || []).includes(cellKey(row, label));
  const edited = (row: string, label: string) => {
    const f = col(label).field;
    const e = current.edits?.[row];
    return !!f && !!(e?.now?.[f] !== undefined || e?.prev?.[f] !== undefined);
  };

  const renderCell = (row: string, label: string, c: Cell, total = false) => (
    <td key={label} className={`num tbl-cell ${editable ? 'can-edit' : ''} ${edited(row, label) ? 'edited' : ''} ${cellOff(row, label) ? 'cmp-off' : ''}`}
        onClick={e => openCell(row, label, e.currentTarget)} title={editable ? 'Click to change this cell' : undefined}>
      <span className="tbl-v">{c.value}</span>
      {c.change !== null && c.change !== undefined && (
        <small className={`tbl-chg ${c.change > 0 ? 'up' : c.change < 0 ? 'down' : ''}`}>{c.change > 0 ? '+' : ''}{c.change}%</small>
      )}
      {c.prev !== null && c.prev !== undefined && <span className="tbl-prev">vs {c.prev}</span>}
      {open && open.row === row && open.col === label && (
        <div className="tbl-pop" ref={popRef} style={{ top: open.top, left: open.left }} onClick={e => e.stopPropagation()}>
          <div className="tbl-pop-head"><strong>{row} · {label}</strong><button type="button" className="icon-btn" onClick={() => setOpen(null)} aria-label="Close"><X size={14} /></button></div>
          {before && (
            <label className="tbl-check">
              <input type="checkbox" checked={!cellOff(row, label)} disabled={busy}
                     onChange={() => { setOpen(null); save({ ...current, cells_off: toggle(current.cells_off, cellKey(row, label)) }); }} />
              Show the change and last period’s figure for this cell
            </label>
          )}
          {!total && col(label).field ? (
            <>
              <div className="tbl-pop-fields">
                <label><span>This period</span><input inputMode="decimal" value={draft.now} onChange={e => setDraft(d => ({ ...d, now: e.target.value }))} /></label>
                {before && <label><span>Last period</span><input inputMode="decimal" value={draft.prev} onChange={e => setDraft(d => ({ ...d, prev: e.target.value }))} /></label>}
              </div>
              <div className="tbl-pop-actions">
                {edited(row, label) && <button type="button" className="btn ghost btn-sm" disabled={busy} onClick={resetCell}><RotateCcw size={12} /> Google’s figure</button>}
                <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={saveFigures}>Save</button>
              </div>
            </>
          ) : (
            <p className="tbl-pop-note">{total ? 'The total is the whole site’s, worked out from every row.' : `${label} is worked out from the other figures — change those and it follows.`}</p>
          )}
        </div>
      )}
    </td>
  );

  return (
    <div className="tbl-ed">
      {editable && (
        <div className="tbl-cols">
          <span className="tbl-cols-label">Columns</span>
          {meta.columns.map(c => (
            <span key={c.label} className={`tbl-col ${c.off ? 'off' : ''}`}>
              <button type="button" disabled={busy} onClick={() => save({ ...current, cols_off: toggle(current.cols_off, c.label) })}
                      title={c.off ? 'Show this column' : 'Hide this column'}>
                {c.off ? <EyeOff size={12} /> : <Eye size={12} />} {c.label}
              </button>
              {!c.off && before && (
                <>
                  <button type="button" disabled={busy} className={`tbl-mini ${c.change_off ? 'off' : ''}`}
                          title={c.change_off ? 'Show the % change' : 'Hide the % change'}
                          onClick={() => save({ ...current, change_off: toggle(current.change_off, c.label) })}>%</button>
                  <button type="button" disabled={busy} className={`tbl-mini ${c.prev_off ? 'off' : ''}`}
                          title={c.prev_off ? 'Show last period’s figure' : 'Hide last period’s figure'}
                          onClick={() => save({ ...current, prev_off: toggle(current.prev_off, c.label) })}>vs</button>
                </>
              )}
            </span>
          ))}
          <button type="button" className="btn ghost btn-sm tbl-reset" disabled={busy}
                  onClick={() => save({}, 'Table back as Google Analytics has it.')}><RotateCcw size={12} /> Reset table</button>
        </div>
      )}

      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>{table === 'channels' ? 'Channel' : 'Country'}</th>
              {data.columns.map(l => <th key={l} className="num">{l}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.rows.map(r => (
              <tr key={r.name}>
                <td className="tbl-name">{r.name}{rowMeta(r.name)?.edited && <span className="tbl-tag">edited</span>}</td>
                {r.cells.map((c, i) => renderCell(r.name, data.columns[i], c))}
              </tr>
            ))}
            {data.total && (
              <tr className="tbl-total">
                <td className="tbl-name">Total</td>
                {data.total.cells.map((c, i) => renderCell('Total', data.columns[i], c, true))}
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {editable && table === 'channels' && meta.rows.length > 1 && (
        <div className="tbl-rows">
          <span className="tbl-cols-label">Rows shown</span>
          {meta.rows.map(r => (
            <label key={r.name} className={`tbl-row ${r.shown ? 'on' : ''}`}>
              <input type="checkbox" checked={r.shown} disabled={busy || (!r.shown && shownRows.length >= meta.max_rows) || (r.shown && shownRows.length === 1)}
                     onChange={() => {
                       const next = r.shown ? shownRows.filter(n => n !== r.name) : meta.rows.map(x => x.name).filter(n => n === r.name || shownRows.includes(n));
                       save({ ...current, rows: next });
                     }} />
              {r.name}
            </label>
          ))}
          <span className="rb-note">Up to {meta.max_rows}. The total counts every channel, shown or not.</span>
        </div>
      )}
    </div>
  );
}
