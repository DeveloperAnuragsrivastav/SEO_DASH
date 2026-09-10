import React, { useEffect, useState } from 'react';
import api from '../api/client';
import { toast } from 'sonner';
import {
  Sparkles, Loader2, X, Search, BarChart2, MapPin,
  Crosshair, Bot, Link as LinkIcon, CheckSquare, Info, Pencil, Check,
} from 'lucide-react';

type SectionKey = 'traffic' | 'rankings' | 'ai_visibility' | 'links' | 'work';

interface MetricDef { key: string; label: string; format: 'int' | 'percent' | 'decimal' }

interface Props {
  clientId: string;
  snapshotId: string;
  snapshot: any;
  onClose: () => void;
  onSaved: () => void;
}

const SECTION_META: { key: SectionKey; label: string; icon: React.ReactNode }[] = [
  { key: 'traffic',       label: 'Traffic & Conversions', icon: <BarChart2 size={15} /> },
  { key: 'rankings',      label: 'Rankings',              icon: <Crosshair size={15} /> },
  { key: 'ai_visibility', label: 'AI Visibility',         icon: <Bot size={15} /> },
  { key: 'links',         label: 'Links Built',           icon: <LinkIcon size={15} /> },
  { key: 'work',          label: 'Work Done',             icon: <CheckSquare size={15} /> },
];

const PROVIDER_META: Record<string, { label: string; icon: React.ReactNode }> = {
  gsc: { label: 'Search Console',   icon: <Search size={13} /> },
  ga4: { label: 'Google Analytics', icon: <BarChart2 size={13} /> },
  gbp: { label: 'Business Profile', icon: <MapPin size={13} /> },
};

/** Display form — compact for big counts, so "298,431" reads as "298K". */
function formatValue(raw: number, format: string): string {
  const n = Number(raw) || 0;
  if (format === 'percent') return `${(n * 100).toFixed(1)}%`;
  if (format === 'decimal') return n.toFixed(1);
  if (Math.abs(n) >= 10000) {
    return new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(n);
  }
  return Math.round(n).toLocaleString();
}

const ReportComposer: React.FC<Props> = ({ clientId, snapshotId, snapshot, onClose, onSaved }) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [asking, setAsking] = useState(false);

  const [available, setAvailable] = useState<Record<SectionKey, boolean> | null>(null);
  const [selected, setSelected] = useState<Record<SectionKey, boolean> | null>(null);

  const [definitions, setDefinitions] = useState<Record<string, MetricDef[]>>({});
  const [metricOn, setMetricOn] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);

  const [instruction, setInstruction] = useState('');
  const [aiNote, setAiNote] = useState<{ text: string; ignored: boolean } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.get(`/clients/${clientId}/reports/${snapshotId}/sections`)
      .then(res => {
        if (cancelled) return;
        setAvailable(res.data.available);
        setSelected(res.data.selected);
        const m = res.data.metrics || {};
        setDefinitions(m.definitions || {});
        setMetricOn(m.selected || {});
        setValues(
          Object.fromEntries(
            Object.entries(m.values || {}).map(([k, v]) => [k, String(v ?? 0)])
          )
        );
      })
      .catch(() => { /* Handled by global interceptor */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [clientId, snapshotId]);

  const toggleSection = (key: SectionKey) => {
    if (!selected || !available?.[key]) return;
    setSelected({ ...selected, [key]: !selected[key] });
    setAiNote(null);
  };

  const toggleMetric = (id: string) => {
    setMetricOn({ ...metricOn, [id]: !metricOn[id] });
    setAiNote(null);
  };

  const askAi = async () => {
    if (!instruction.trim()) return;
    setAsking(true);
    setAiNote(null);
    try {
      const res = await api.post(`/clients/${clientId}/reports/${snapshotId}/sections/suggest`, { instruction });
      setSelected(res.data.sections);
      if (res.data.metrics) setMetricOn(res.data.metrics);
      setAiNote({ text: res.data.note || '', ignored: !!res.data.ignored });
    } catch (err: any) {
      // Handled by global interceptor
    }
    setAsking(false);
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const grouped: Record<string, Record<string, number>> = {};
      for (const [id, v] of Object.entries(values)) {
        const [provider, key] = id.split('.');
        (grouped[provider] ||= {})[key] = Number(v) || 0;
      }
      await api.put(`/clients/${clientId}/reports/${snapshotId}/metrics`, { metrics: grouped });
      await api.put(`/clients/${clientId}/reports/${snapshotId}/sections`, {
        sections: selected,
        metrics: metricOn,
      });
      toast.success('Report updated.');
      onSaved();
    } catch (err: any) {
      // Handled by global interceptor
    }
    setSaving(false);
  };

  const summary = (key: SectionKey): string => {
    const s = snapshot || {};
    switch (key) {
      case 'traffic': {
        const on = Object.entries(metricOn).filter(([, v]) => v).length;
        return `${on} of ${Object.keys(metricOn).length} figures shown`;
      }
      case 'rankings': {
        const r = s.rankings || {};
        return `${(r.keywords || []).length} keywords · ${(r.summary || {}).top_10 || 0} in top 10`;
      }
      case 'ai_visibility': {
        const ai = s.ai_visibility || [];
        return `${ai.filter((m: any) => m.mentioned).length} of ${ai.length} prompts mention the brand`;
      }
      case 'links':  return `${(s.links || []).length} links built`;
      case 'work':   return `${(s.activities || []).length} activities · ${(s.screenshots || []).length} screenshots`;
    }
  };

  const chosen = selected ? SECTION_META.filter(m => selected[m.key]).length : 0;

  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal composer" role="dialog" aria-modal="true" aria-label="Build the report">
        <div className="composer-head">
          <div>
            <h2 className="modal-title">Build the report</h2>
            <p className="modal-desc" style={{ marginBottom: 0 }}>
              Untick anything the client shouldn't see, and correct any figure before it goes out.
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
                  placeholder="e.g. hide average CTR and drop the work done section"
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
              Sections · {chosen} of {SECTION_META.length} included
            </div>

            <div className="stack">
              {SECTION_META.map(m => {
                const has = available?.[m.key];
                const on = !!selected?.[m.key];
                return (
                  <div key={m.key} className={`composer-section ${on ? 'on' : ''} ${has ? '' : 'empty'}`}>
                    <label className="composer-section-head">
                      <input type="checkbox" checked={on} disabled={!has} onChange={() => toggleSection(m.key)} />
                      <span className="composer-section-text">
                        <span className="composer-section-title">{m.icon} {m.label}</span>
                        <span className="composer-section-sub">
                          {has ? summary(m.key) : 'No data — nothing to show'}
                        </span>
                      </span>
                    </label>

                    {/* Every figure inside Traffic gets its own tick and its own pencil. */}
                    {m.key === 'traffic' && has && on && (
                      <div className="composer-metrics">
                        {Object.entries(definitions).map(([provider, defs]) => (
                          <div key={provider}>
                            <div className="composer-metric-label">
                              {PROVIDER_META[provider]?.icon} {PROVIDER_META[provider]?.label || provider}
                            </div>
                            <div className="metric-grid">
                              {defs.map(d => {
                                const id = `${provider}.${d.key}`;
                                const isEditing = editing === id;
                                const on = metricOn[id] !== false;
                                return (
                                  <div key={id} className={`metric-card ${on ? '' : 'off'}`}>
                                    <label className="metric-card-head">
                                      <input type="checkbox" checked={on} onChange={() => toggleMetric(id)} />
                                      <span>{d.label}</span>
                                    </label>

                                    <div className="metric-card-value">
                                      {isEditing ? (
                                        <>
                                          <input
                                            className="form-input metric-input"
                                            type="number"
                                            min="0"
                                            step={d.format === 'int' ? '1' : d.format === 'percent' ? '0.0001' : '0.1'}
                                            value={values[id] ?? '0'}
                                            autoFocus
                                            onChange={e => setValues({ ...values, [id]: e.target.value })}
                                            onKeyDown={e => { if (e.key === 'Enter' || e.key === 'Escape') setEditing(null); }}
                                          />
                                          <button
                                            className="metric-pencil done"
                                            onClick={() => setEditing(null)}
                                            aria-label={`Done editing ${d.label}`}
                                          >
                                            <Check size={13} />
                                          </button>
                                        </>
                                      ) : (
                                        <>
                                          <span className="metric-number" title={values[id]}>
                                            {formatValue(Number(values[id] ?? 0), d.format)}
                                          </span>
                                          <button
                                            className="metric-pencil"
                                            onClick={() => setEditing(id)}
                                            aria-label={`Edit ${d.label}`}
                                          >
                                            <Pencil size={12} />
                                          </button>
                                        </>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ))}
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
