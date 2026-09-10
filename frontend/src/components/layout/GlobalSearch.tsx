import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, CornerDownLeft } from 'lucide-react';
import api from '../../api/client';

interface ClientRow { id: string; name: string; domain: string; }

/** Where you can jump to inside a client, once one is picked. */
const CLIENT_PAGES = [
  { label: 'Overview', path: (id: string) => `/admin/clients/${id}` },
  { label: 'Keyword Performance', path: (id: string) => `/clients/${id}/keywords` },
  { label: 'Search Console', path: (id: string) => `/clients/${id}/search-console` },
  { label: 'Google Analytics', path: (id: string) => `/clients/${id}/google-analytics` },
  { label: 'Backlinks', path: (id: string) => `/clients/${id}/links` },
  { label: 'Add Data', path: (id: string) => `/admin/clients/${id}/manual-entry` },
];

const GlobalSearch: React.FC = () => {
  const navigate = useNavigate();
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.get('/clients', { skipErrorToast: true } as any)
      .then(res => setClients(res.data || []))
      .catch(() => setClients([]));
  }, []);

  // ⌘K / Ctrl-K focuses search from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const results = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return [];
    const hits: { label: string; hint: string; to: string }[] = [];

    for (const c of clients) {
      if (c.name.toLowerCase().includes(term) || (c.domain || '').toLowerCase().includes(term)) {
        hits.push({ label: c.name, hint: c.domain, to: `/admin/clients/${c.id}` });
      }
    }

    // Also match a page name against the first few clients, so "keywords"
    // gets you somewhere useful rather than nothing.
    for (const page of CLIENT_PAGES) {
      if (page.label.toLowerCase().includes(term)) {
        for (const c of clients.slice(0, 4)) {
          hits.push({ label: `${page.label}`, hint: c.name, to: page.path(c.id) });
        }
      }
    }
    return hits.slice(0, 8);
  }, [q, clients]);

  useEffect(() => { setActive(0); }, [q]);

  const go = (to: string) => {
    setOpen(false);
    setQ('');
    inputRef.current?.blur();
    navigate(to);
  };

  return (
    <div className="gsearch" ref={boxRef}>
      <Search size={15} className="gsearch-icon" />
      <input
        ref={inputRef}
        className="gsearch-input"
        placeholder="Search clients, reports, or keywords…"
        value={q}
        onChange={e => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={e => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive(a => Math.min(a + 1, results.length - 1)); }
          if (e.key === 'ArrowUp') { e.preventDefault(); setActive(a => Math.max(a - 1, 0)); }
          if (e.key === 'Enter' && results[active]) { e.preventDefault(); go(results[active].to); }
        }}
        aria-label="Search"
      />
      {!q && <kbd className="gsearch-kbd">⌘K</kbd>}

      {open && q.trim() && (
        <div className="gsearch-results" role="listbox">
          {results.length === 0 ? (
            <div className="gsearch-empty">Nothing matches “{q}”.</div>
          ) : results.map((r, i) => (
            <button
              key={`${r.to}-${i}`}
              className={`gsearch-result ${i === active ? 'active' : ''}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => go(r.to)}
              role="option"
              aria-selected={i === active}
            >
              <span className="gsearch-result-label">{r.label}</span>
              <span className="gsearch-result-hint">{r.hint}</span>
              {i === active && <CornerDownLeft size={13} className="gsearch-enter" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default GlobalSearch;
