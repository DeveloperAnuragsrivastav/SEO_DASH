import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { ImagePlus, Loader2, Trash2 } from 'lucide-react';
import api from '../../api/client';
import usePasteImage from '../../lib/usePasteImage';

const MAX_BYTES = 5 * 1024 * 1024;

type Slot = { slot: number; hasImage: boolean; caption: string };

/**
 * Numbered screenshot slots for one slide of a report (e.g. the five
 * Google Business Profile captures). Each image is kept on the report
 * itself, so every month's report carries its own.
 */
export default function ReportShots({
  base, section, editable, title, hint,
}: { base: string; section: string; editable: boolean; title: string; hint: string }) {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [urls, setUrls] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  // The box a pasted image goes into; none chosen means the first empty one.
  const [chosen, setChosen] = useState<number | null>(null);
  // Set the moment an upload starts: holding ⌘V fires several paste events
  // before `busy` re-renders, and each one used to fill another box.
  const lock = useRef(false);
  const urlsRef = useRef(urls);
  urlsRef.current = urls;

  const loadImage = useCallback(async (slot: number) => {
    try {
      const res = await api.get(`${base}/images/${section}/${slot}`, { responseType: 'blob', skipErrorToast: true } as any);
      const url = URL.createObjectURL(res.data);
      setUrls(u => {
        if (u[slot]) URL.revokeObjectURL(u[slot]);
        return { ...u, [slot]: url };
      });
    } catch {
      /* the slot is empty */
    }
  }, [base, section]);

  useEffect(() => {
    let alive = true;
    api.get(`${base}/images/${section}`, { skipErrorToast: true } as any)
      .then(res => {
        if (!alive) return;
        const list: Slot[] = res.data || [];
        setSlots(list);
        list.filter(s => s.hasImage).forEach(s => loadImage(s.slot));
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [base, section, loadImage]);

  // Release every preview on the way out.
  useEffect(() => () => { Object.values(urlsRef.current).forEach(u => URL.revokeObjectURL(u)); }, []);

  const replace = (next: Slot) => setSlots(list => list.map(s => (s.slot === next.slot ? next : s)));

  const upload = async (slot: number, file: File) => {
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) { toast.error('Use a PNG, JPEG or WebP image.'); return; }
    if (file.size > MAX_BYTES) { toast.error('Each screenshot must be 5 MB or smaller.'); return; }
    if (lock.current) return;
    lock.current = true;
    setBusy(slot);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.put(`${base}/images/${section}/${slot}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      replace(res.data);
      await loadImage(slot);
    } catch {
      // Handled by global interceptor
    }
    lock.current = false;
    setBusy(null);
  };

  const remove = async (slot: number) => {
    setBusy(slot);
    try {
      const res = await api.delete(`${base}/images/${section}/${slot}`);
      replace(res.data);
      setUrls(u => {
        if (u[slot]) URL.revokeObjectURL(u[slot]);
        const { [slot]: _, ...rest } = u;
        return rest;
      });
    } catch {
      // Handled by global interceptor
    }
    setBusy(null);
  };

  const saveCaption = async (slot: number, caption: string) => {
    const current = slots.find(s => s.slot === slot);
    if (!current?.hasImage || current.caption === caption.trim()) return;
    try {
      const res = await api.patch(`${base}/images/${section}/${slot}`, { caption });
      replace(res.data);
    } catch {
      // Handled by global interceptor
    }
  };

  usePasteImage(file => {
    if (!editable || lock.current) return;
    const target = chosen ?? slots.find(s => !s.hasImage)?.slot;
    if (target === undefined) { toast.info('All boxes are full — click one to replace it, then paste.'); return; }
    upload(target, file);
    setChosen(null);
  }, editable && slots.length > 0);

  if (slots.length === 0) return null;
  const filled = slots.filter(s => s.hasImage).length;
  // Only what has been added, plus one empty box for the next — not a wall of blanks.
  const nextEmpty = slots.find(s => !s.hasImage);
  const shown = slots.filter(s => s.hasImage || (editable && s === nextEmpty));

  return (
    <div className="rb-group rb-shots">
      <div className="rb-group-label">
        <span>{title} · {filled} of {slots.length} added</span>
      </div>
      <p className="rb-note">{hint}{editable && <> <strong>Paste (⌘V / Ctrl+V)</strong> a copied screenshot or image to add it — click a box first to choose where it goes.</>}</p>
      <div className="rb-shots-grid">
        {shown.map(s => (
          <div key={s.slot} className={`rb-shot ${s.hasImage ? 'filled' : ''} ${chosen === s.slot ? 'chosen' : ''}`}>
            <div
              className="rb-shot-frame"
              role={editable ? 'button' : undefined}
              tabIndex={editable ? 0 : undefined}
              title={editable ? 'Click, then paste an image here' : undefined}
              onClick={() => editable && setChosen(c => (c === s.slot ? null : s.slot))}
            >
              {busy === s.slot ? (
                <Loader2 size={20} className="spin" />
              ) : s.hasImage && urls[s.slot] ? (
                <img src={urls[s.slot]} alt={s.caption || `Screenshot ${s.slot + 1}`} />
              ) : (
                <span className="rb-shot-empty"><ImagePlus size={20} /><span>{chosen === s.slot ? 'Paste now (⌘V)' : `Add screenshot ${s.slot + 1} of ${slots.length}`}</span></span>
              )}
            </div>
            {editable && (
              <div className="rb-shot-actions">
                <label className={`btn btn-secondary btn-sm ${busy !== null ? 'is-disabled' : ''}`}>
                  <ImagePlus size={14} /> {s.hasImage ? 'Replace' : 'Add'}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    hidden
                    disabled={busy !== null}
                    onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) upload(s.slot, f); }}
                  />
                </label>
                {s.hasImage && (
                  <button className="btn ghost btn-sm" onClick={() => remove(s.slot)} disabled={busy !== null} aria-label="Remove screenshot">
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            )}
            {s.hasImage && (
              <input
                className="rb-shot-caption"
                placeholder="Caption (optional)"
                defaultValue={s.caption}
                maxLength={160}
                disabled={!editable}
                onBlur={e => saveCaption(s.slot, e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
