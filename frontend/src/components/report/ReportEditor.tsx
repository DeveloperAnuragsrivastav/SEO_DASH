import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import api from '../../api/client';
import { toast } from 'sonner';
import { EyeOff, Pencil, Sparkles, Loader2, Check, X, Undo2 } from 'lucide-react';

interface Item {
  id: string;
  section: string;
  label: string;
  value: number | boolean | null;
  format: 'int' | 'percent' | 'decimal' | 'bool' | 'none';
  editable: boolean;
  kind: string;
}

interface Props {
  clientId: string;
  snapshotId: string;
  onExit: () => void;
  /** Re-fetch the report once changes are saved. */
  onSaved: () => void;
}

/** The element currently under the cursor, and where to float its controls. */
interface Target {
  kind: 'item' | 'section';
  id: string;
  rect: DOMRect;
}

function parseValue(raw: string, format: Item['format']): number | boolean {
  if (format === 'bool') return raw === 'true';
  if (format === 'percent') return Number(raw) / 100;
  return Number(raw);
}

function displayValue(v: Item['value'], format: Item['format']): string {
  if (format === 'bool') return v ? 'true' : 'false';
  if (format === 'percent') return String(((Number(v) || 0) * 100).toFixed(2));
  return String(v ?? '');
}

const ReportEditor: React.FC<Props> = ({ clientId, snapshotId, onExit, onSaved }) => {
  const [items, setItems] = useState<Record<string, Item>>({});
  const [itemOn, setItemOn] = useState<Record<string, boolean>>({});
  const [sectionOn, setSectionOn] = useState<Record<string, boolean>>({});
  const [available, setAvailable] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, string>>({});

  const [target, setTarget] = useState<Target | null>(null);
  const [editing, setEditing] = useState<{ id: string; rect: DOMRect } | null>(null);
  const [draft, setDraft] = useState('');

  const [instruction, setInstruction] = useState('');
  const [asking, setAsking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState<{ text: string; ignored: boolean } | null>(null);
  const [dirty, setDirty] = useState(false);

  const rootRef = useRef<HTMLElement | null>(null);

  // ── Load current state ────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    api.get(`/clients/${clientId}/reports/${snapshotId}/composer`)
      .then(res => {
        if (cancelled) return;
        const d = res.data;
        const byId: Record<string, Item> = {};
        for (const i of d.items || []) byId[i.id] = i;
        setItems(byId);
        setItemOn(d.selectedItems || {});
        setSectionOn(d.selectedSections || {});
        setAvailable(d.available || {});
        setValues(Object.fromEntries((d.items || []).map((i: Item) => [i.id, displayValue(i.value, i.format)])));
      })
      .catch(() => { /* Handled by global interceptor */ });
    return () => { cancelled = true; };
  }, [clientId, snapshotId]);

  // ── Reflect hidden state onto the real report nodes ───────────────
  useEffect(() => {
    const root = document.querySelector('.report-view');
    rootRef.current = root as HTMLElement;
    if (!root) return;

    root.querySelectorAll<HTMLElement>('[data-item-id]').forEach(el => {
      const id = el.dataset.itemId!;
      el.classList.toggle('re-hidden', itemOn[id] === false);
    });
    root.querySelectorAll<HTMLElement>('[data-section-id]').forEach(el => {
      const id = el.dataset.sectionId!;
      el.classList.toggle('re-hidden', sectionOn[id] === false && available[id] !== false);
    });
  }, [itemOn, sectionOn, available]);

  // Strip the editing classes when leaving edit mode.
  useEffect(() => () => {
    document.querySelectorAll('.re-hidden').forEach(el => el.classList.remove('re-hidden'));
  }, []);

  // ── Track what the cursor is over ─────────────────────────────────
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (editing) return;
      const el = (e.target as HTMLElement)?.closest?.('[data-item-id],[data-section-id]') as HTMLElement | null;
      if (!el) { setTarget(null); return; }
      const itemId = el.dataset.itemId;
      const sectionId = el.dataset.sectionId;
      setTarget({
        kind: itemId ? 'item' : 'section',
        id: (itemId || sectionId)!,
        rect: el.getBoundingClientRect(),
      });
    };
    document.addEventListener('mousemove', onMove);
    return () => document.removeEventListener('mousemove', onMove);
  }, [editing]);

  const toggle = useCallback((kind: 'item' | 'section', id: string) => {
    setDirty(true);
    setNote(null);
    if (kind === 'item') setItemOn(prev => ({ ...prev, [id]: prev[id] === false }));
    else setSectionOn(prev => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const startEdit = (id: string, rect: DOMRect) => {
    setDraft(values[id] ?? '');
    setEditing({ id, rect });
    setTarget(null);
  };

  const commitEdit = () => {
    if (!editing) return;
    setValues(prev => ({ ...prev, [editing.id]: draft }));
    setDirty(true);
    setEditing(null);
  };

  const askAi = async () => {
    if (!instruction.trim()) return;
    setAsking(true);
    setNote(null);
    try {
      const res = await api.post(`/clients/${clientId}/reports/${snapshotId}/composer/suggest`, { instruction });
      setSectionOn(res.data.sections || {});
      setItemOn(res.data.items || {});
      setNote({ text: res.data.note || '', ignored: !!res.data.ignored });
      if (!res.data.ignored) setDirty(true);
    } catch (err: any) {
      // Handled by global interceptor
    }
    setAsking(false);
  };

  const save = async () => {
    setSaving(true);
    try {
      const edits: Record<string, any> = {};
      for (const [id, raw] of Object.entries(values)) {
        const item = items[id];
        if (!item?.editable) continue;
        const next = parseValue(raw, item.format);
        const before = item.format === 'bool' ? !!item.value : Number(item.value);
        if (next !== before) edits[id] = next;
      }
      if (Object.keys(edits).length) {
        await api.put(`/clients/${clientId}/reports/${snapshotId}/values`, { edits });
      }
      await api.put(`/clients/${clientId}/reports/${snapshotId}/composer`, {
        sections: sectionOn,
        items: itemOn,
      });
      toast.success('Report updated.');
      onSaved();
      onExit();
    } catch (err: any) {
      // Handled by global interceptor
    }
    setSaving(false);
  };

  const hiddenCount =
    Object.values(itemOn).filter(v => v === false).length +
    Object.entries(sectionOn).filter(([k, v]) => !v && available[k]).length;

  // ── Floating control cluster ──────────────────────────────────────
  const controls = target && (() => {
    const isSection = target.kind === 'section';
    const on = isSection ? !!sectionOn[target.id] : itemOn[target.id] !== false;
    const item = items[target.id];
    const canEdit = !isSection && item?.editable;

    const top = Math.max(8, target.rect.top - 34);
    const left = Math.min(window.innerWidth - 120, target.rect.right - 8);

    return createPortal(
      <div
        className="re-controls"
        style={{ top, left }}
        onMouseEnter={() => setTarget(target)}
      >
        <button
          className="re-control"
          onClick={() => toggle(target.kind, target.id)}
          title={on ? 'Hide from report' : 'Show in report'}
        >
          {on ? <EyeOff size={13} /> : <Undo2 size={13} />}
          {isSection && <span>{on ? 'Hide section' : 'Restore'}</span>}
        </button>
        {canEdit && on && (
          <button className="re-control" onClick={() => startEdit(target.id, target.rect)} title="Edit value">
            <Pencil size={13} />
          </button>
        )}
      </div>,
      document.body,
    );
  })();

  // ── Inline value editor, floated over the figure ──────────────────
  const inlineEditor = editing && (() => {
    const item = items[editing.id];
    return createPortal(
      <div
        className="re-inline"
        style={{ top: editing.rect.top - 4, left: editing.rect.left - 4, minWidth: editing.rect.width + 8 }}
      >
        <span className="re-inline-label">{item?.label}</span>
        <div className="re-inline-row">
          {item?.format === 'bool' ? (
            <select className="form-select" value={draft} autoFocus onChange={e => setDraft(e.target.value)}>
              <option value="true">Mentioned</option>
              <option value="false">Not found</option>
            </select>
          ) : (
            <input
              className="form-input"
              type="number"
              step={item?.format === 'int' ? '1' : '0.01'}
              value={draft}
              autoFocus
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') commitEdit();
                if (e.key === 'Escape') setEditing(null);
              }}
            />
          )}
          {item?.format === 'percent' && <span className="re-inline-unit">%</span>}
          <button className="btn btn-primary btn-sm" onClick={commitEdit}><Check size={13} /></button>
          <button className="btn ghost btn-sm" onClick={() => setEditing(null)}><X size={13} /></button>
        </div>
      </div>,
      document.body,
    );
  })();

  return (
    <>
      {controls}
      {inlineEditor}

      {createPortal(
        <div className="re-bar" role="toolbar" aria-label="Report editing">
          <div className="re-bar-status">
            <span className="re-dot" />
            <strong>Editing</strong>
            <span className="re-bar-count">
              {hiddenCount === 0 ? 'nothing hidden' : `${hiddenCount} hidden`}
            </span>
          </div>

          <div className="re-bar-ai">
            <Sparkles size={14} />
            <input
              className="re-bar-input"
              placeholder="Tell me what to include…"
              value={instruction}
              onChange={e => setInstruction(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); askAi(); } }}
            />
            {asking
              ? <Loader2 size={14} className="spin" />
              : instruction.trim() && <button className="btn btn-secondary btn-sm" onClick={askAi}>Apply</button>}
          </div>

          {note && (
            <div className={`re-bar-note ${note.ignored ? 'ignored' : ''}`}>{note.text}</div>
          )}

          <div className="re-bar-actions">
            <button className="btn ghost btn-sm" onClick={onExit} disabled={saving}>Cancel</button>
            <button className="btn btn-primary btn-sm" onClick={save} disabled={saving || !dirty}>
              {saving ? <><Loader2 size={13} className="spin" /> Saving…</> : 'Save changes'}
            </button>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
};

export default ReportEditor;
