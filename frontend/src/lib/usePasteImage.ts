import { useEffect, useRef } from 'react';

/** The first image on the clipboard of a paste event, as a named file. */
export function imageFromPaste(e: ClipboardEvent): File | null {
  const items = Array.from(e.clipboardData?.items || []);
  const item = items.find(i => i.kind === 'file' && i.type.startsWith('image/'));
  const blob = item?.getAsFile();
  if (!blob) return null;
  const ext = (blob.type.split('/')[1] || 'png').replace('jpeg', 'jpg');
  return new File([blob], blob.name && blob.name !== 'image.png' ? blob.name : `pasted-${Date.now()}.${ext}`, { type: blob.type });
}

/**
 * Calls `onImage` when an image is pasted (Cmd/Ctrl+V) anywhere on the page —
 * a screenshot, or an image copied from a website. Text pastes into fields
 * are left alone; only a clipboard that holds an image is taken.
 */
export default function usePasteImage(onImage: (file: File) => void, enabled = true) {
  const handler = useRef(onImage);
  handler.current = onImage;

  useEffect(() => {
    if (!enabled) return;
    const onPaste = (e: ClipboardEvent) => {
      if (e.defaultPrevented) return;          // a targeted box (usePasteTarget) took it
      const file = imageFromPaste(e);
      if (!file) return;
      e.preventDefault();
      handler.current(file);
    };
    document.addEventListener('paste', onPaste);
    return () => document.removeEventListener('paste', onPaste);
  }, [enabled]);
}

/**
 * A paste target for one box on a page that has others: it takes a pasted
 * image only while the pointer is over it, or after it was clicked (until a
 * click lands elsewhere). It runs before page-wide listeners and claims the
 * paste, so two boxes never both receive the same image.
 * Returns a ref for the box and whether it is currently the target.
 */
export function usePasteTarget<T extends HTMLElement>(onImage: (file: File) => void, enabled = true) {
  const ref = useRef<T | null>(null);
  const hovered = useRef(false);
  const picked = useRef(false);
  const handler = useRef(onImage);
  handler.current = onImage;

  useEffect(() => {
    if (!enabled) return;
    const el = ref.current;
    const enter = () => { hovered.current = true; };
    const leave = () => { hovered.current = false; };
    const down = (e: PointerEvent) => { picked.current = !!(el && e.target instanceof Node && el.contains(e.target)); };
    const onPaste = (e: ClipboardEvent) => {
      if (!(hovered.current || picked.current)) return;
      const file = imageFromPaste(e);
      if (!file) return;
      e.preventDefault();
      handler.current(file);
    };
    el?.addEventListener('pointerenter', enter);
    el?.addEventListener('pointerleave', leave);
    document.addEventListener('pointerdown', down, true);
    document.addEventListener('paste', onPaste, true);   // capture: before page-wide listeners
    return () => {
      el?.removeEventListener('pointerenter', enter);
      el?.removeEventListener('pointerleave', leave);
      document.removeEventListener('pointerdown', down, true);
      document.removeEventListener('paste', onPaste, true);
    };
  }, [enabled]);

  return ref;
}
