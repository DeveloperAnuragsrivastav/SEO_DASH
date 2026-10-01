import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../../api/client';
import {
  ArrowRight, Building2, ExternalLink, Search, KeyRound, Layers,
  LayoutGrid, List, ChevronDown,
} from 'lucide-react';

import { usePermissions } from '../../hooks/usePermissions';
import Page, { Summary, Empty, type Figure } from '../../components/ui/Page';
import PageSkeleton from '../../components/ui/PageSkeleton';

interface ClientRow {
  id: string;
  name: string;
  domain: string;
  status: string;
  package_keywords: number;
  business_type: string;
}

/** Stable tint per client so a monogram keeps its colour between visits. */
const TONES = ['amber', 'blue', 'violet', 'green', 'orange', 'rose'] as const;
const toneFor = (id: string) =>
  TONES[[...id].reduce((a, c) => a + c.charCodeAt(0), 0) % TONES.length];

const Clients: React.FC = () => {
  const { isManager, isSuperAdmin } = usePermissions();
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [loading, setLoading] = useState(true);

  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [type, setType] = useState('all');
  const [view, setView] = useState<'grid' | 'list'>(() => {
    try { return (localStorage.getItem('ez-clients-view') as 'grid' | 'list') || 'grid'; } catch { return 'grid'; }
  });

  const setViewMode = (v: 'grid' | 'list') => {
    setView(v);
    try { localStorage.setItem('ez-clients-view', v); } catch { /* storage unavailable */ }
  };

  const fetchClients = async () => {
    try {
      const res = await api.get('/clients');
      setClients(res.data || []);
    } catch (err) {
      // Handled by global interceptor
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchClients(); }, []);

  const active = clients.filter(c => c.status === 'active').length;
  const totalKw = clients.reduce((s, c) => s + (c.package_keywords || 0), 0);

  const types = useMemo(
    () => Array.from(new Set(clients.map(c => c.business_type).filter(Boolean))),
    [clients],
  );

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    return clients.filter(c => {
      if (status !== 'all' && c.status !== status) return false;
      if (type !== 'all' && c.business_type !== type) return false;
      if (!term) return true;
      return c.name.toLowerCase().includes(term) || (c.domain || '').toLowerCase().includes(term);
    });
  }, [clients, query, status, type]);

  if (loading) return <PageSkeleton cards={6} header={true} stats={0} />;

  const openDomain = (e: React.MouseEvent, domain: string) => {
    e.preventDefault();
    e.stopPropagation();
    window.open(`https://${domain}`, '_blank', 'noopener,noreferrer');
  };

  const figures: Figure[] = [
    { label: 'Clients', value: clients.length.toLocaleString() },
    { label: 'Active', value: active.toLocaleString(), note: `of ${clients.length}` },
    { label: 'Keywords tracked', value: totalKw.toLocaleString(), note: 'across all clients' },
  ];

  return (
    <Page
      title={isManager ? 'My Clients' : isSuperAdmin ? 'All Clients' : 'Assigned Clients'}
      lede="Every project you are responsible for."
      summary={clients.length > 0 ? <Summary figures={figures} /> : undefined}
    >

      {clients.length > 0 && (
        <div className="toolbar">
          <div className="toolbar-search">
            <Search size={15} />
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search clients by name or domain…"
              aria-label="Search clients"
            />
          </div>

          <label className="filter">
            <span className="filter-label">Status</span>
            <span className="filter-control">
              <span className={`dot ${status === 'active' ? 'on' : ''}`} />
              <select value={status} onChange={e => setStatus(e.target.value)} aria-label="Filter by status">
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="paused">Paused</option>
              </select>
              <ChevronDown size={14} />
            </span>
          </label>

          <label className="filter">
            <span className="filter-label">Type</span>
            <span className="filter-control">
              <Layers size={14} />
              <select value={type} onChange={e => setType(e.target.value)} aria-label="Filter by type">
                <option value="all">All Types</option>
                {types.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <ChevronDown size={14} />
            </span>
          </label>

          <div className="view-toggle" role="group" aria-label="View mode">
            <button
              className={view === 'grid' ? 'on' : ''}
              onClick={() => setViewMode('grid')}
              aria-pressed={view === 'grid'}
              aria-label="Grid view"
            >
              <LayoutGrid size={15} />
            </button>
            <button
              className={view === 'list' ? 'on' : ''}
              onClick={() => setViewMode('list')}
              aria-pressed={view === 'list'}
              aria-label="List view"
            >
              <List size={15} />
            </button>
          </div>
        </div>
      )}

      {clients.length === 0 ? (
        <section className="surface">
          <Empty
            icon={<Building2 size={22} />}
            title="No clients yet"
            hint="Once a client is assigned to you it appears here with its keywords, traffic and reporting history."
          />
        </section>
      ) : visible.length === 0 ? (
        <section className="surface">
          <Empty
            icon={<Search size={22} />}
            title="No clients match those filters"
            hint="Try a different search term, or clear the status and type filters."
            action={
              <button className="btn btn-secondary" onClick={() => { setQuery(''); setStatus('all'); setType('all'); }}>
                Clear filters
              </button>
            }
          />
        </section>
      ) : (
        <div className={view === 'grid' ? 'client-grid' : 'client-list'}>
          {visible.map(c => (
            <Link key={c.id} to={`/admin/clients/${c.id}`} className="client-card">
              <div className="client-card-top">
                <span className={`client-monogram tone-${toneFor(c.id)}`}>{c.name.slice(0, 2)}</span>
                <span className={`status-pill ${c.status === 'active' ? 'on' : ''}`}>
                  {c.status === 'active' ? 'Active' : c.status}
                </span>
              </div>

              <h3 className="client-name">{c.name}</h3>

              <span className="client-domain" onClick={e => openDomain(e, c.domain)} role="link" tabIndex={-1}>
                {c.domain} <ExternalLink size={12} />
              </span>

              <div className="client-meta">
                <div>
                  <div className="overline"><KeyRound size={12} /> Keywords</div>
                  <div className="client-meta-value">{c.package_keywords}</div>
                  <div className="client-meta-hint">keywords tracked</div>
                </div>
                <div>
                  <div className="overline"><Layers size={12} /> Type</div>
                  <span className="type-pill">{c.business_type}</span>
                </div>
              </div>

              <span className="client-cta">View Dashboard <ArrowRight size={14} /></span>
            </Link>
          ))}
        </div>
      )}
    </Page>
  );
};

export default Clients;
