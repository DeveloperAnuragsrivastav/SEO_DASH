import React, { useState, useMemo } from 'react';
import { Search } from 'lucide-react';
import { rankClass } from './ReportUtils';

interface RankingsSectionProps {
  rankings: any;
  keywords: any[];
  months: string[];
}

const formatMonth = (m: string) => {
  const parts = m.split(' ');
  if (parts.length === 2) {
    return `${parts[0].substring(0, 3)}'${parts[1].substring(2)}`;
  }
  return m;
};

const Sparkline: React.FC<{ data: (number | null)[] }> = ({ data }) => {
  if (!data || data.length < 2) return <span style={{ color: 'var(--ink-3)', fontSize: '12px' }}>Insufficient data</span>;
  
  const width = 80;
  const height = 24;
  const padding = 2;
  
  // Clean data: null -> 100 (out of top 100)
  const cleanData = data.map(v => (v === null || v === undefined) ? 100 : v);
  
  // Calculate points
  const stepX = (width - padding * 2) / (cleanData.length - 1);
  const minRank = Math.min(...cleanData);
  const maxRank = Math.max(...cleanData);
  
  // If all ranks are the same, draw a straight line in the middle
  const range = maxRank - minRank === 0 ? 1 : maxRank - minRank;
  
  const points = cleanData.map((val, i) => {
    const x = padding + i * stepX;
    // Invert Y because lower rank (e.g. 1) is better/higher
    const normalizedY = (val - minRank) / range;
    const y = padding + (normalizedY * (height - padding * 2));
    return `${x},${y}`;
  }).join(' ');
  
  // Determine color based on trend (first vs last)
  const first = cleanData[0];
  const last = cleanData[cleanData.length - 1];
  let strokeColor = 'var(--text-tertiary)'; // neutral
  if (last < first) strokeColor = 'var(--up)'; // improved (lower rank)
  if (last > first) strokeColor = 'var(--down)'; // declined (higher rank)

  return (
    <svg width={width} height={height} style={{ overflow: 'visible' }}>
      <polyline 
        points={points}
        fill="none"
        stroke={strokeColor}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={padding + (cleanData.length - 1) * stepX} cy={padding + ((last - minRank) / range) * (height - padding * 2)} r="3" fill={strokeColor} />
    </svg>
  );
};

const RankingsSection: React.FC<RankingsSectionProps> = ({ rankings, keywords, months }) => {
  const [kwFilter, setKwFilter] = useState('all');
  const [kwSearch, setKwSearch] = useState('');

  const kwList = keywords || [];
  
  const filterCounts = useMemo(() => {
    const c = { all: kwList.length, up: 0, down: 0, p1: 0, p2: 0 };
    kwList.forEach((kw: any) => {
      const change = kw.change || 0;
      if (change > 0) c.up++;
      if (change < 0) c.down++;
      
      const currentPos = kw.positions?.[months[months.length - 1]] || 999;
      if (currentPos > 0 && currentPos <= 10) c.p1++;
      if (currentPos > 10 && currentPos <= 20) c.p2++;
    });
    return c;
  }, [kwList, months]);
  
  const filteredKw = useMemo(() => {
    return kwList.filter((kw: any) => {
      const term = (kw.term || kw.keyword || '').toLowerCase();
      const q = kwSearch.toLowerCase();
      if (q && !term.includes(q)) return false;
      const change = kw.change || 0;
      if (kwFilter === 'up') return change > 0;
      if (kwFilter === 'down') return change < 0;
      
      const currentPos = kw.positions?.[months[months.length - 1]] || 999;
      if (kwFilter === 'p1') return currentPos > 0 && currentPos <= 10;
      if (kwFilter === 'p2') return currentPos > 10 && currentPos <= 20;
      return true;
    });
  }, [kwList, kwFilter, kwSearch]);

  return (
    <section id="rankings" className="report-section">
      <div className="head">
        <div>
          <div className="eyebrow">Keyword Performance</div>
          <h2>Rankings</h2>
        </div>
        <span className="spacer" />
        <span className="src man">Manual entry</span>
      </div>
      
      {/* Position Distribution — the PDF's position bands, same numbers */}
      <div className="card pad" style={{ marginBottom: 'var(--space-lg)' }}>
        <h3 className="h2" style={{ marginBottom: '12px' }}>Positioning Summary</h3>
        {(() => {
          const bands = [
            { label: 'Top 10', value: rankings.summary?.top_10 || 0 },
            { label: '11–20', value: rankings.summary?.['11_20'] || 0 },
            { label: '21–50', value: rankings.summary?.['21_50'] || 0 },
            { label: 'Below 50', value: rankings.summary?.['51_plus'] || 0 },
          ];
          const total = bands.reduce((a, b) => a + b.value, 0) || 1;
          return bands.map(b => (
            <div className="position-row" key={b.label}>
              <span>{b.label}</span>
              <div className="track">
                <div className="fill" style={{ width: `${Math.round((b.value / total) * 100)}%` }} />
              </div>
              <b>{b.value}</b>
            </div>
          ));
        })()}
      </div>

      <div className="ctrl">
        {['all', 'up', 'down', 'p1', 'p2']
          .filter(f => filterCounts[f as keyof typeof filterCounts] > 0)
          .map(f => (
          <button 
            key={f} 
            className={`chip ${kwFilter === f ? 'on' : ''}`} 
            onClick={() => setKwFilter(f)}
            aria-pressed={kwFilter === f}
          >
            {f === 'all' ? 'All' : f === 'up' ? 'Improved' : f === 'down' ? 'Dropped' : f === 'p1' ? 'Page 1' : 'Page 2'}
          </button>
        ))}
        <span className="spacer" />
        <input 
          className="search" 
          value={kwSearch} 
          onChange={e => setKwSearch(e.target.value)} 
          placeholder="Search keyword..." 
          aria-label="Search keyword"
        />
      </div>
      
      <div className="card table-wrapper">
        <table>
          <thead>
            <tr>
              <th style={{ width: 40, textAlign: 'center' }}>#</th>
              <th>Keyword</th>
              <th className="num">SV</th>
              <th className="num">Initial</th>
              {months.map(m => (
                <th key={m} className="num">{formatMonth(m)}</th>
              ))}
              <th style={{ textAlign: 'center' }}>Trend</th>
              <th className="num">Change</th>
            </tr>
          </thead>
          <tbody>
            {filteredKw.length === 0 ? (
              <tr>
                <td colSpan={6 + months.length} style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
                  <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
                    <Search size={32} color="var(--ink-3)" />
                  </div>
                  No keywords found. Try adjusting your filters.
                </td>
              </tr>
            ) : (
              filteredKw.map((kw: any, i: number) => {
                const change = kw.change || 0;
                return (
                  <tr key={kw.keyword_id || i}>
                    <td className="mono" style={{ color: 'var(--text-tertiary)', fontSize: 12, textAlign: 'center' }}>{i + 1}</td>
                    <td className="kwname">{kw.term || kw.keyword || '—'}</td>
                    <td className="num">{kw.search_volume ? kw.search_volume.toLocaleString() : '—'}</td>
                    <td className="num"><span className={rankClass(kw.initial_rank)}>{kw.initial_rank || '—'}</span></td>
                    {months.map(m => (
                      <td key={m} className="num">
                        <span className={rankClass(kw.positions?.[m])}>
                          {kw.positions?.[m] || '—'}
                        </span>
                      </td>
                    ))}
                    <td style={{ textAlign: 'center' }}>
                      <Sparkline data={months.map(m => kw.positions?.[m] || null)} />
                    </td>
                    <td className="num">
                      {change > 0 ? <span className="d up">▲ {change}</span> :
                       change < 0 ? <span className="d dn">▼ {Math.abs(change)}</span> :
                       <span className="d flat">—</span>}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};

export default RankingsSection;
