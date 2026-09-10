import React, { useEffect, useMemo, useState } from 'react';
import api from '../api/client';
import { toast } from 'sonner';
import {
  Sparkles, Loader2, X, Info, Pencil, Check, ChevronDown,
  Search, BarChart2, MapPin, Crosshair, Bot, Link as LinkIcon, CheckSquare,
} from 'lucide-react';

interface Item {
  id: string;
  section: string;
  label: string;
  value: number | boolean | null;
  format: 'int' | 'percent' | 'decimal' | 'bool' | 'none';
  editable: boolean;
  kind: 'headline' | 'summary' | 'row';
  unit?: string;
}

interface Props {
  clientId: string;
  snapshotId: string;
  onClose: () => void;
  onSaved: () => void;
}

const SECTION_ICON: Record<string, React.ReactNode> = {
  gsc: <Search size={15} />,
  ga4: <BarChart2 size={15} />,
  gbp: <MapPin size={15} />,
  rankings: <Crosshair size={15} />,
  ai_visibility: <Bot size={15} />,
  links: <LinkIcon size={15} />,
  work: <CheckSquare size={15} />,
};

const KIND_LABEL: Record<string, string> = {
  headline: 'Figures',
  summary: 'Summary',
  row: 'Rows',
};

function formatValue(raw: Item['value'], format: Item['format']): string {
  if (format === 'bool') return raw ? 'Mentioned' : 'Not found';
  if (format === 'none' || raw === null) return '—';
  const n = Number(raw) || 0;
  if (format === 'percent') return `${(n * 100).toFixed(1)}%`;
  if (format === 'decimal') return n.toFixed(1);
  if (Math.abs(n) >= 10000) {
    return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(n);
  }
  return Math.round(n).toLocaleString();
}

const ReportComposer: React.FC<Props> = ({ clientId, snapshotId, onClose, onSaved }) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [asking, setAsking] = useState(false);

  const [sections, setSections] = useState<{ key: string; label: string }[]>([]);
  const [available, setAvailable] = useState<Record<string, boolean>>({});
  const [sectionOn, setSectionOn] = useState<Record<string, boolean>>({});
  const [items, setItems] = useState<Item[]>([]);
  const [itemOn, setItemOn] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const [instruction, setInstruction] = useState('');
  const [aiNote, setAiNote] = useState<{ text: string; ignored: boolean } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.get(`/clients/${clientId}/reports/${snapshotId}/composer`)
      .then(res => {
        if (cancelled) return;
        const d = res.data;
        setSections(d.sections || []);
        setAvailable(d.available || {});
        setSectionOn(d.selectedSections || {});
        setItems(d.items || []);
        setItemOn(d.selectedItems || {});
        setValues(Object.fromEntries((d.items || []).map((i: Item) => [i.id, String(i.value ?? '')])));
        // Open the provider sections by default; long row lists start collapsed.
        setOpen(Object.fromEntries((d.sections || []).map((s: any) => [s.key, ['gsc', 'ga4', 'gbp'].includes(s.key)])));
      })
      .catch(() => { /* Handled by global interceptor */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [clientId, snapshotId]);

  const bySection = useMemo(() => {
    const map: Record<string, Item[]> = {};
    for (const i of items) (map[i.section] ||= []).push(i);
    return map;
  }, [items]);

  const toggleSection = (key: string) => {
    if (!available[key]) return;
    setSectionOn({ ...sectionOn, [key]: !sectionOn[key] });
    setAiNote(null);
  };

  const toggleItem = (id: string) => {
    setItemOn({ ...itemOn, [id]: itemOn[id] === false });
    setAiNote(null);
  };

  /** Tick or untick every row in one section at once. */
  const setAllIn = (key: string, on: boolean) => {
    const next = { ...itemOn };
    for (const i of bySection[key] || []) next[i.id] = on;
    setItemOn(next);
    setAiNote(null);
  };

  const askAi = async () => {
    if (!instruction.trim()) return;
    setAsking(true);
    setAiNote(null);
    try {
      const res = await api.post(`/clients/${clientId}/reports/${snapshotId}/composer/suggest`, { instruction });
      setSectionOn(res.data.sections || {});
      setItemOn(res.data.items || {});
      setAiNote({ text: res.data.note || '', ignored: !!res.data.ignored });
    } catch (err: any) {
      // Handled by global interceptor
    }
    setAsking(false);
  };

  const save = async () => {
    setSaving(true);
    try {
      const edits: Record<string, any> = {};
      for (const i of items) {
        if (!i.editable) continue;
        const raw = values[i.id];
        if (raw === undefined) continue;
        const next = i.format === 'bool' ? raw === 'true' : Number(raw);
        if (i.format === 'bool' ? next !== i.value : next !== Number(i.value)) edits[i.id] = next;
      }
      if (Object.keys(edits).length > 0) {
        await api.put(`/clients/${clientId}/reports/${snapshotId}/values`, { edits });
      }
      await api.put(`/clients/${clientId}/reports/${snapshotId}/composer`, {
        sections: sectionOn,
        items: itemOn,
      });
      toast.success('Report updated.');
      onSaved();
    } catch (err: any) {
      // Handled by global interceptor
    }
    setSaving(false);
  };

  const shownIn = (key: string) => (bySection[key] || []).filter(i => itemOn[i.id] !== false).length;
  const sectionsOn = sections.filter(s => sectionOn[s.key]).length;

  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal composer" role="dialog" aria-modal="true" aria-label="Build the report">
        <div className="composer-head">
          <div>
            <h2 className="modal-title">Build the report</h2>
            <p className="modal-desc" style={{ marginBottom: 0 }}>
              Untick anything the client shouldn't see. Every figure can be corrected with the pencil.
            </p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={17} /></button>
        </div>

        {loading ? (
          <div className="loader-container"><div className="spinner" /></div>
        ) : (
          <>
            <div className="composer-ai">
              <label className="composer-ai-label" htmlFor="composer-instruction">
                <Sparkles size={14} /> Describe what to include
              </label>
              <div className="composer-ai-row">
                <input
                  id="composer-instruction"
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

            <div className="overline" style={{ margin: '20px 0 10px' }}>
              Sections · {sectionsOn} of {sections.length} included
            </div>

            <div className="stack">
              {sections.map(sec => {
                const has = available[sec.key];
                const on = !!sectionOn[sec.key];
                const list = bySection[sec.key] || [];
                const isOpen = !!open[sec.key];

                return (
                  <div key={sec.key} className={`composer-section ${on ? 'on' : ''} ${has ? '' : 'empty'}`}>
                    <div className="composer-section-head">
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={!has}
                        onChange={() => toggleSection(sec.key)}
                        aria-label={`Include ${sec.label}`}
                      />
                      <span className="composer-section-text">
                        <span className="composer-section-title">{SECTION_ICON[sec.key]} {sec.label}</span>
                        <span className="composer-section-sub">
                          {has ? `${shownIn(sec.key)} of ${list.length} shown` : 'No data — nothing to show'}
                        </span>
                      </span>

                      {has && list.length > 0 && (
                        <button
                          className={`composer-expand ${isOpen ? 'open' : ''}`}
                          onClick={() => setOpen({ ...open, [sec.key]: !isOpen })}
                          aria-expanded={isOpen}
                          aria-label={`${isOpen ? 'Collapse' : 'Expand'} ${sec.label}`}
                        >
                          <ChevronDown size={16} />
                        </button>
                      )}
                    </div>

                    {has && on && isOpen && (
                      <div className="composer-metrics">
                        <div className="composer-bulk">
                          <button className="btn ghost btn-sm" onClick={() => setAllIn(sec.key, true)}>Select all</button>
                          <button className="btn ghost btn-sm" onClick={() => setAllIn(sec.key, false)}>Clear all</button>
                        </div>

                        {(['headline', 'summary', 'row'] as const).map(kind => {
                          const group = list.filter(i => i.kind === kind);
                          if (group.length === 0) return null;
                          return (
                            <div key={kind}>
                              {list.some(i => i.kind !== kind) && (
                                <div className="composer-metric-label">{KIND_LABEL[kind]}</div>
                              )}
                              <div className={kind === 'row' ? 'metric-rows' : 'metric-grid'}>
                                {group.map(i => {
                                  const isEditing = editing === i.id;
                                  const shown = itemOn[i.id] !== false;
                                  return (
                                    <div key={i.id} className={`metric-card ${shown ? '' : 'off'} ${kind === 'row' ? 'is-row' : ''}`}>
                                      <label className="metric-card-head">
                                        <input type="checkbox" checked={shown} onChange={() => toggleItem(i.id)} />
                                        <span title={i.label}>{i.label}</span>
                                      </label>

                                      <div className="metric-card-value">
                                        {isEditing && i.editable ? (
                                          <>
                                            {i.format === 'bool' ? (
                                              <select
                                                className="form-select metric-input"
                                                value={values[i.id] === 'true' ? 'true' : 'false'}
                                                autoFocus
                                                onChange={e => setValues({ ...values, [i.id]: e.target.value })}
                                              >
                                                <option value="true">Mentioned</option>
                                                <option value="false">Not found</option>
                                              </select>
                                            ) : (
                                              <input
                                                className="form-input metric-input"
                                                type="number"
                                                min="0"
                                                step={i.format === 'int' ? '1' : i.format === 'percent' ? '0.0001' : '0.1'}
                                                value={values[i.id] ?? '0'}
                                                autoFocus
                                                onChange={e => setValues({ ...values, [i.id]: e.target.value })}
                                                onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Escape') setEditing(null); }}
                                              />
                                            )}
                                            <button className="metric-pencil done" onClick={() => setEditing(null)} aria-label="Done">
                                              <Check size={13} />
                                            </button>
                                          </>
                                        ) : (
                                          <>
                                            <span className="metric-number">
                                              {formatValue(
                                                i.format === 'bool' ? values[i.id] === 'true' : (values[i.id] as any),
                                                i.format,
                                              )}
                                              {i.unit === 'position' && <small> pos</small>}
                                            </span>
                                            {i.editable && (
                                              <button className="metric-pencil" onClick={() => setEditing(i.id)} aria-label={`Edit ${i.label}`}>
                                                <Pencil size={12} />
                                              </button>
                                            )}
                                          </>
                                        )}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
              <button className="btn btn-primary" onClick={save} disabled={saving}>
                {saving ? <><Loader2 size={15} className="spin" /> Saving…</> : 'Save & View Report'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ReportComposer;
