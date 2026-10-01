import { useEffect, useRef, useSyncExternalStore } from 'react';

/** What a confirmation asks. `tone: 'danger'` paints the confirm button red. */
export type ConfirmOptions = {
  title: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
  tone?: 'default' | 'danger';
};

type Pending = ConfirmOptions & { resolve: (ok: boolean) => void };

// One dialog at a time, held outside React so any handler can ask.
let current: Pending | null = null;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach(l => l());

/**
 * The app's own replacement for window.confirm — same use, but awaited:
 *   if (!(await confirmDialog({ title: 'Publish?' }))) return;
 */
export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  current?.resolve(false);
  return new Promise(resolve => {
    current = { ...options, resolve };
    emit();
  });
}

function settle(ok: boolean) {
  const p = current;
  current = null;
  emit();
  p?.resolve(ok);
}

/** Mounted once, at the root of the app. */
export function ConfirmHost() {
  const dialog = useSyncExternalStore(
    cb => { listeners.add(cb); return () => { listeners.delete(cb); }; },
    () => current,
  );
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!dialog) return;
    const before = document.activeElement as HTMLElement | null;
    confirmRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); settle(false); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); before?.focus?.(); };
  }, [dialog]);

  if (!dialog) return null;
  return (
    <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) settle(false); }}>
      <div className="modal" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-desc">
        <h2 className="modal-title" id="confirm-title">{dialog.title}</h2>
        {dialog.message && <p className="modal-desc" id="confirm-desc">{dialog.message}</p>}
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={() => settle(false)}>{dialog.cancelText || 'Cancel'}</button>
          <button ref={confirmRef} className={`btn ${dialog.tone === 'danger' ? 'btn-danger' : 'btn-primary'}`} onClick={() => settle(true)}>
            {dialog.confirmText || 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}
