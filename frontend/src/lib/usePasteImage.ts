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
      const file = imageFromPaste(e);
      if (!file) return;
      e.preventDefault();
      handler.current(file);
    };
    document.addEventListener('paste', onPaste);
    return () => document.removeEventListener('paste', onPaste);
  }, [enabled]);
}
