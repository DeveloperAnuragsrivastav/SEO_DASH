import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../../api/client';

import * as XLSX from 'xlsx';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';
import Sparkline from '../../components/ui/Sparkline';
import {
  Search, BarChart3, TrendingUp, TrendingDown, Download, ChevronDown, Crosshair,
} from 'lucide-react';

interface KeywordHistory {
  id: string;
  keyword: string;
  search_volume?: number;
  initial_rank?: number;
  history: Record<string, number>;
}

const Keywords: React.FC = () => {
  const { clientId } = useParams<{ clientId: string }>();
  const [keywords, setKeywords] = useState<KeywordHistory[]>([]);
  const [months, setMonths] = useState<string[]>([]);
  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);

  const [query, setQuery] = useState('');
  const [band, setBand] = useState('all');
  const [sortBy, setSortBy] = useState<'change' | 'position' | 'volume' | 'keyword'>('change');

  const fetchKeywords = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/keywords/history`, {
        params: { page, page_size: pageSize }
      });
      setKeywords(data.items);
      setTotal(data.total);

      // Extract all unique months across all keywords in current view
      const allMonths = new Set<string>();
      data.items.forEach((k: KeywordHistory) => {
        Object.keys(k.history || {}).forEach(m => allMonths.add(m));
      });
      // Sort months descending (newest first)
      setMonths(Array.from(allMonths).sort().reverse());
    } catch (err: any) {
      // Handled by global interceptor
    }
  };

  const fetchClient = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}`);
      setClient(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchClient();
  }, [clientId]);

  useEffect(() => {
    setLoading(true);
    fetchKeywords().finally(() => setLoading(false));
  }, [clientId, page, pageSize]);

  if (loading && !keywords.length) return <PageSkeleton />;

  const exportExcel = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/keywords/history`, {
        params: { page: 1, page_size: 100000 }
      });
      const ws = XLSX.utils.json_to_sheet(data.items);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Keywords");
      XLSX.writeFile(wb, `Keywords_${clientId}.xlsx`);
    } catch (err) {
      // Handled by global interceptor
    }
  };

  /** Latest position and movement for a keyword, from its own history. */
  const readRow = (kw: KeywordHistory) => {
    const initial = kw.initial_rank || 0;
    const latest = months.length > 0 ? (kw.history[months[0]] || initial) : initial;
    const change = initial && latest ? initial - latest : 0;
    // Oldest → newest, so the trend line reads left to right.
    const series = [...months].reverse().map(m => kw.history[m]).filter((v): v is number => typeof v === 'number');
    return { initial, latest, change, series };
  };

  const rows = keywords
    .map(kw => ({ kw, ...readRow(kw) }))
    .filter(r => {
      const term = query.trim().toLowerCase();
      if (term && !r.kw.keyword.toLowerCase().includes(term)) return false;
      if (band === 'top10') return r.latest > 0 && r.latest <= 10;
      if (band === 'p2') return r.latest > 10 && r.latest <= 20;
      if (band === 'beyond') return r.latest > 20;
      if (band === 'improved') return r.change > 0;
      if (band === 'declined') return r.change < 0;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === 'change') return b.change - a.change;
      if (sortBy === 'position') return (a.latest || 999) - (b.latest || 999);
      if (sortBy === 'volume') return (b.kw.search_volume || 0) - (a.kw.search_volume || 0);
      return a.kw.keyword.localeCompare(b.kw.keyword);
    });

  const all = keywords.map(readRow);
  const improved = all.filter(r => r.change > 0).length;
  const declined = all.filter(r => r.change < 0).length;
  const ranked = all.filter(r => r.latest > 0);
  const avgPosition = ranked.length
    ? ranked.reduce((sum, r) => sum + r.latest, 0) / ranked.length
    : 0;
  const avgInitial = ranked.length
    ? ranked.reduce((sum, r) => sum + (r.initial || r.latest), 0) / ranked.length
    : 0;
  const pct = (n: number) => (keywords.length ? Math.round((n / keywords.length) * 100) : 0);

  const stats = [
    {
      key: 'total', tone: 'violet', icon: <Crosshair size={17} />,
      label: 'Total Keywords', value: keywords.length.toLocaleString(),
      delta: null as string | null, foot: 'tracked for this client', series: [] as number[],
    },
    {
      key: 'avg', tone: 'blue', icon: <BarChart3 size={17} />,
      label: 'Avg. Position', value: avgPosition ? avgPosition.toFixed(1) : '—',
      delta: avgInitial && avgPosition ? `${(avgInitial - avgPosition).toFixed(1)}` : null,
      foot: 'across ranked keywords', series: [],
    },
    {
      key: 'up', tone: 'green', icon: <TrendingUp size={17} />,
      label: 'Keywords Improved', value: improved.toLocaleString(),
      delta: null, foot: `${pct(improved)}% of tracked keywords`, series: [],
    },
    {
      key: 'down', tone: 'amber', icon: <TrendingDown size={17} />,
      label: 'Keywords Declined', value: declined.toLocaleString(),
      delta: null, foot: `${pct(declined)}% of tracked keywords`, series: [],
    },
  ];

  return (
    <>
      <PageHeader
        title="Keyword Performance"
        subtitle="Track and manage target keywords for this client."
        breadcrumbs={[
          { label: 'Home', href: '/' },
          { label: 'Clients', href: '/admin/clients' },
          { label: client?.name || 'Client', href: `/admin/clients/${clientId}` },
          { label: 'Keyword Performance' },
        ]}
        actions={
          <button className="btn btn-primary" onClick={exportExcel} disabled={keywords.length === 0}>
            <Download size={15} /> Download Excel
          </button>
        }
      />

      <div className="kpi-row" style={{ marginBottom: 24 }}>
        {stats.map(st => (
          <div key={st.key} className="stat">
            <div className="stat-top">
              <span className={`stat-chip tone-${st.tone}`}>{st.icon}</span>
              <span className="stat-label">{st.label}</span>
            </div>
            <div className="stat-figure">
              <span className="stat-value">{st.value}</span>
              {st.delta && Number(st.delta) !== 0 && (
                <span className={`trend ${Number(st.delta) > 0 ? 'up' : 'down'}`}>
                  {Number(st.delta) > 0 ? '↑' : '↓'} {Math.abs(Number(st.delta))}
                </span>
              )}
              <span className="stat-spark">
                <Sparkline values={st.series} color={`var(--tone-${st.tone})`} label={`${st.label} trend`} />
              </span>
            </div>
            <div className="stat-foot">{st.foot}</div>
          </div>
        ))}
      </div>

      <div className="page-card-flush data-panel">
        <div className="data-panel-head">
          <div>
            <h2 className="h2">Keyword Rankings</h2>
            <p className="section-sub">How your target keywords are performing in search results.</p>
          </div>

          <div className="data-panel-tools">
            <div className="toolbar-search sm">
              <Search size={14} />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search keywords…"
                aria-label="Search keywords"
              />
            </div>
            <label className="select-chip">
              <select value={band} onChange={e => setBand(e.target.value)} aria-label="Filter by position">
                <option value="all">All Positions</option>
                <option value="top10">Top 10</option>
                <option value="p2">11–20</option>
                <option value="beyond">Beyond 20</option>
                <option value="improved">Improved</option>
                <option value="declined">Declined</option>
              </select>
              <ChevronDown size={14} />
            </label>
            <label className="select-chip">
              <select value={sortBy} onChange={e => setSortBy(e.target.value as any)} aria-label="Sort by">
                <option value="change">Sort by: Change</option>
                <option value="position">Sort by: Position</option>
                <option value="volume">Sort by: Volume</option>
                <option value="keyword">Sort by: Keyword</option>
              </select>
              <ChevronDown size={14} />
            </label>
          </div>
        </div>

        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 48 }} className="num">#</th>
                <th>Keyword</th>
                <th className="num">Search Volume</th>
                <th className="num">Initial Rank</th>
                {months.map(m => <th key={m} className="num">{m}</th>)}
                <th className="num">Change</th>
                <th style={{ width: 96 }}>Trend</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.kw.id}>
                  <td className="num row-index">{i + 1}</td>
                  <td className="kwname">{r.kw.keyword}</td>
                  <td className="num">{r.kw.search_volume ? r.kw.search_volume.toLocaleString() : '—'}</td>
                  <td className="num">{r.kw.initial_rank || '—'}</td>
                  {months.map(m => <td key={m} className="num">{r.kw.history[m] ?? '—'}</td>)}
                  <td className="num">
                    <span className={`trend ${r.change > 0 ? 'up' : r.change < 0 ? 'down' : 'flat'}`}>
                      {r.change > 0 ? `↑ +${r.change}` : r.change < 0 ? `↓ ${r.change}` : '—'}
                    </span>
                  </td>
                  <td>
                    <Sparkline
                      values={r.series}
                      color={r.change >= 0 ? 'var(--tone-green)' : 'var(--tone-rose)'}
                      width={72}
                      height={26}
                      label={`${r.kw.keyword} trend`}
                    />
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={6 + months.length}>
                    <div className="empty-state" style={{ padding: '40px 20px' }}>
                      <span className="empty-state-icon"><Search size={20} /></span>
                      <h3>{keywords.length === 0 ? 'No keywords yet' : 'Nothing matches those filters'}</h3>
                      <p>
                        {keywords.length === 0
                          ? 'Add keywords from the Add Data page to start tracking positions.'
                          : 'Try a different search term or position filter.'}
                      </p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <PaginationBar
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      </div>
    </>
  );
};

export default Keywords;
