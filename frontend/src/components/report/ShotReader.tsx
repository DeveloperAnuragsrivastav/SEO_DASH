import React, { useState } from 'react';
import { toast } from 'sonner';
import { Download, ImagePlus, Loader2, Upload, X, AlertTriangle, Info } from 'lucide-react';
import api from '../../api/client';
import { usePasteTarget } from '../../lib/usePasteImage';

/** A sample screenshot: which screen of Google's to open, and how. */
export interface ShotSample { file: string; title: string; how: string }

interface Notice { level: 'warning' | 'info'; text: string }

interface Props {
  base: string;
  /** The slide this box sits on — the server says so when a screenshot fills another. */
  slide: string;
  label?: string;
  hint?: string;
  samples: ShotSample[];
  editable: boolean;
  /** Saves what is on screen first, so the fill is built on it. */
  beforeRead: () => Promise<unknown>;
  /** The composer, as it is after the fill. */
  onFilled: (composer: any) => void;
}

const MAX_MB = 5;

/**
 * Fill a slide from a screenshot of Google's own report, for anyone who
 * cannot connect Search Console or Analytics. Upload or paste it; whatever it
 * shows is filled in and stays editable. Anything to check — a date range a
 * day off, a rounded total — is shown here and as a notification.
 */
const ShotReader: React.FC<Props> = ({ base, slide, label, hint, samples, editable, beforeRead, onFilled }) => {
  const [busy, setBusy] = useState(false);
  const [period, setPeriod] = useState<'auto' | 'current' | 'previous'>('auto');
  const [notices, setNotices] = useState<Notice[]>([]);
  const [filled, setFilled] = useState<string[]>([]);
  const [shot, setShot] = useState<string | null>(null);

  const read = async (file: File) => {
    if (busy) return;
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) { toast.error('Use a PNG, JPEG or WebP screenshot.'); return; }
    if (file.size > MAX_MB * 1024 * 1024) { toast.error(`The screenshot must be ${MAX_MB} MB or smaller.`); return; }
    setBusy(true);
    try { await beforeRead(); } catch { setBusy(false); return; }
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('slide', slide);
      fd.append('period', period);
      const res = await api.post(`${base}/screenshot/read`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      onFilled(res.data || {});
      const got = res.data?.shot || {};
      const list: Notice[] = got.notices || [];
      setNotices(list);
      setFilled(got.filled || []);
      setShot(cur => { if (cur) URL.revokeObjectURL(cur); return URL.createObjectURL(file); });
      toast.success('Filled from the screenshot', {
        description: `${(got.filled || []).join(' · ') || 'Figures filled in'} — check them and edit any that are off.`,
      });
      // The things to check are notifications too, not only the list below.
      list.filter(n => n.level === 'warning').forEach(n => toast.warning('Please check', { description: n.text, duration: 12000 }));
    } catch {
      // Handled by the global interceptor (it shows the server's message).
    }
    setBusy(false);
  };

  const ref = usePasteTarget<HTMLDivElement>(f => { read(f); }, editable && !busy);
  if (!editable) return null;

  return (
    <div ref={ref} className="rb-upload rb-paste-zone rb-shotread" tabIndex={-1}>
      <div className="rb-upload-text">
        <ImagePlus size={16} />
        <span>
          <strong>{label || 'Fill from a screenshot'}</strong>
          {hint}{hint ? ' ' : ''}
          Upload it, or copy it and <strong className="rb-inline">paste with ⌘V / Ctrl+V</strong> over this box.
          Every figure stays editable.
        </span>
      </div>
      <div className="rb-upload-actions">
        <select className="form-select rb-shot-period" value={period} disabled={busy}
          onChange={e => setPeriod(e.target.value as typeof period)}
          title="Which period the screenshot shows. By default its own dates decide.">
          <option value="auto">Period: from its dates</option>
          <option value="current">This period</option>
          <option value="previous">Last period</option>
        </select>
        {shot && <a href={shot} target="_blank" rel="noreferrer" className="btn ghost btn-sm">View screenshot</a>}
        <label className={`btn btn-primary btn-sm ${busy ? 'is-disabled' : ''}`}>
          {busy ? <><Loader2 size={13} className="spin" /> Reading…</> : <><Upload size={13} /> Upload screenshot</>}
          <input type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={busy}
            onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) read(f); }} />
        </label>
      </div>

      {samples.length > 0 && (
        <div className="rb-shot-samples">
          {samples.map(s => (
            <div key={s.file} className="rb-shot-sample">
              <a href={`/samples/${s.file}`} target="_blank" rel="noreferrer" className="rb-shot-thumb" title="Open the sample full size">
                <img src={`/samples/${s.file}`} alt={`Sample: ${s.title}`} loading="lazy" />
              </a>
              <div className="rb-shot-sample-text">
                <strong>{s.title}</strong>
                <span>{s.how} Set the dates to this report's period.</span>
                <a href={`/samples/${s.file}`} download={`sample-${s.file}`} className="btn ghost btn-sm">
                  <Download size={13} /> Download sample screenshot
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      {(filled.length > 0 || notices.length > 0) && (
        <div className="rb-shot-result">
          {filled.length > 0 && <p className="rb-shot-filled">Filled: {filled.join(' · ')}.</p>}
          {notices.map((n, i) => (
            <div key={i} className={`rb-shot-notice ${n.level}`}>
              {n.level === 'warning' ? <AlertTriangle size={14} /> : <Info size={14} />}
              <span>{n.text}</span>
              <button type="button" className="rb-shot-x" aria-label="Dismiss"
                onClick={() => setNotices(list => list.filter((_, j) => j !== i))}><X size={13} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ShotReader;
