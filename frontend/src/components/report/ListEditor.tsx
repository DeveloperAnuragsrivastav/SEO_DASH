import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Plus, Trash2, ChevronDown, ChevronRight, Eye, EyeOff } from 'lucide-react';
import api from '../../api/client';

export type ListColumn = { key: string; label: string; type: 'text' | 'int' | 'decimal' };
export type ListSpec = { path: string; section: string; label: string; note?: string; columns: ListColumn[] };
type Row = Record<string, any>;
export type DisplayOff = { changes: string[]; cols: Record<string, string[]> };

/**
 * One of the report's breakdown tables (top pages, countries, channels…) as
 * an editable grid: change a cell, add a row, remove one, then save.
 * Collapsed by default so a step with several tables stays short.
 */
export default function ListEditor({
  base, spec, rows, editable, onSaved, defaultOpen = false, colsOff, onColsOff,
}: {
  base: string; spec: ListSpec; rows: Row[]; editable: boolean; onSaved: (rows: Row[]) => void; defaultOpen?: boolean;
  /** Columns the slide leaves out; given only for tables whose columns can be hidden. */
  colsOff?: string[]; onColsOff?: (off: DisplayOff) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [draft, setDraft] = useState<Row[]>(rows);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);

  // A fresh copy from the server (a fetch, a reload) replaces unsaved edits.
  useEffect(() => { setDraft(rows); setDirty(false); }, [rows]);

  const nameKey = spec.columns[0].key;

  const set = (i: number, key: string, value: string) => {
    setDraft(d => d.map((r, n) => (n === i ? { ...r, [key]: value } : r)));
    setDirty(true);
  };
  const add = () => {
    setDraft(d => [...d, Object.fromEntries(spec.columns.map(c => [c.key, c.type === 'text' ? '' : 0]))]);
    setDirty(true);
    setOpen(true);
  };
  const remove = (i: number) => {
    setDraft(d => d.filter((_, n) => n !== i));
    setDirty(true);
  };

  const save = async () => {
    const blank = draft.findIndex(r => !String(r[nameKey] ?? '').trim());
    if (blank !== -1) { toast.error(`Row ${blank + 1} needs a ${spec.columns[0].label.toLowerCase()}.`); return; }
    setBusy(true);
    try {
      const res = await api.put(`${base}/lists`, { path: spec.path, rows: draft });
      onSaved(res.data.rows || []);
      setDirty(false);
      toast.success(`${spec.label} saved.`);
    } catch {
      // Handled by global interceptor
    }
    setBusy(false);
  };

  const discard = () => { setDraft(rows); setDirty(false); };

  const [colBusy, setColBusy] = useState(false);
  const colOff = (key: string) => !!colsOff?.includes(key);
  /** Show or hide one column on the slide — saved at once, the rows are untouched. */
  const toggleCol = async (key: string) => {
    if (!colsOff) return;
    const next = colOff(key) ? colsOff.filter(k => k !== key) : [...colsOff, key];
    if (next.length >= spec.columns.length) { toast.error('Keep at least one column in the table.'); return; }
    setColBusy(true);
    try {
      const res = await api.put(`${base}/lists/columns`, { path: spec.path, off: next });
      if (res.data?.displayOff) onColsOff?.(res.data.displayOff);
    } catch {
      // Handled by global interceptor
    }
    setColBusy(false);
  };

  return (
    <div className={`rb-list ${open ? 'open' : ''}`}>
      <button type="button" className="rb-list-head" onClick={() => setOpen(o => !o)}>
        {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        <span className="rb-list-title">{spec.label}</span>
        <span className="rb-list-count">{draft.length} {draft.length === 1 ? 'row' : 'rows'}</span>
        {dirty && <span className="rb-list-dirty">Unsaved</span>}
        {!!colsOff?.length && <span className="rb-list-hidden">{colsOff.length} {colsOff.length === 1 ? 'column' : 'columns'} hidden</span>}
      </button>

      {open && (
        <div className="rb-list-body">
          {spec.note && <p className="rb-note">{spec.note}</p>}
          {colsOff && (
            <div className="tbl-cols">
              <span className="tbl-cols-label">On the slide</span>
              {spec.columns.map(c => (
                <span key={c.key} className={`tbl-col ${colOff(c.key) ? 'off' : ''}`}>
                  <button type="button" disabled={!editable || colBusy} onClick={() => toggleCol(c.key)}
                          title={colOff(c.key) ? 'Show this column on the slide' : 'Hide this column on the slide'}>
                    {colOff(c.key) ? <EyeOff size={12} /> : <Eye size={12} />} {c.label}
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="rb-list-scroll">
            <table className="rb-list-table">
              <thead>
                <tr>
                  {spec.columns.map(c => (
                    <th key={c.key} className={`${c.type === 'text' ? '' : 'num'} ${colOff(c.key) ? 'col-off' : ''}`}
                        title={colOff(c.key) ? 'Hidden on the slide — still saved here' : undefined}>{c.label}</th>
                  ))}
                  {editable && <th aria-label="Remove" />}
                </tr>
              </thead>
              <tbody>
                {draft.length === 0 && (
                  <tr><td colSpan={spec.columns.length + 1} className="rb-list-empty">No rows yet{editable ? ' — add one below.' : '.'}</td></tr>
                )}
                {draft.map((r, i) => (
                  <tr key={i}>
                    {spec.columns.map(c => (
                      <td key={c.key} className={`${c.type === 'text' ? 'text' : 'num'} ${colOff(c.key) ? 'col-off' : ''}`}>
                        <input
                          type={c.type === 'text' ? 'text' : 'number'}
                          min={c.type === 'text' ? undefined : 0}
                          step={c.type === 'decimal' ? '0.01' : '1'}
                          value={r[c.key] ?? ''}
                          disabled={!editable || busy}
                          onChange={e => set(i, c.key, e.target.value)}
                        />
                      </td>
                    ))}
                    {editable && (
                      <td className="act">
                        <button className="btn ghost btn-sm" onClick={() => remove(i)} disabled={busy} aria-label="Remove row">
                          <Trash2 size={13} />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {editable && (
            <div className="rb-list-actions">
              <button className="btn ghost btn-sm" onClick={add} disabled={busy}><Plus size={13} /> Add row</button>
              <span style={{ flex: 1 }} />
              {dirty && <button className="btn ghost btn-sm" onClick={discard} disabled={busy}>Discard</button>}
              <button className="btn btn-primary btn-sm" onClick={save} disabled={!dirty || busy}>
                {busy ? <Loader2 size={13} className="spin" /> : null} Save table
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
