import React, { useEffect, useState, useMemo, Fragment } from 'react';
import { useParams } from 'react-router-dom';
import { ChevronDown, Search } from 'lucide-react';
import { toast } from 'sonner';
import { AreaChart, Area, YAxis, XAxis, Tooltip, ResponsiveContainer, CartesianGrid, LabelList } from 'recharts';

import api from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import { AdminShell } from '../components/layout/AdminShell';
import {
  FilterChips,
  ManualEntryCard,
  Panel,
  SourcePill,
  TablePanel,
  Td,
  Th,
  inputCls,
} from '../components/kit';
import { type RankingRow } from '../components/RankingsTable';

const Rankings: React.FC = () => {
  const { clientId, month } = useParams<{ clientId: string; month: string }>();
  const [data, setData] = useState<RankingRow[]>([]);
  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetchClient = async () => {
    try {
      const res = await api.get(`/clients/${clientId}`);
      setClient(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchRankings = async () => {
    if (!clientId || !month) return;
    try {
      const response = await api.get(`/clients/${clientId}/rankings/${month}`);
      setData(response.data.data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to fetch rankings data.');
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchClient(), fetchRankings()]).finally(() => setLoading(false));
  }, [clientId, month]);

  const handleFileUpload = async (_fileName: string, file: File) => {
    if (!clientId) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await api.post(`/clients/${clientId}/rankings/upload_csv`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      if (res.data.status === 'success' || res.data.status === 'partial') {
        toast.success(`Successfully inserted ${res.data.rows_inserted || 0} rows.`);
        if (res.data.rows_inserted > 0) fetchRankings();
        if (res.data.errors?.length) {
          toast.warning(`Upload completed with ${res.data.errors.length} errors.`);
        }
      } else {
        toast.error(`Upload failed: ${res.data.errors?.[0]?.error || 'Unknown error'}`);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    }
  };

  const handleManualEntry = async (values: Record<string, string>) => {
    if (!clientId) return;
    try {
      await api.post(`/clients/${clientId}/rankings/manual`, {
        keyword_id: values['Keyword ID'],
        captured_on: values['Date'],
        position: values['Position (optional)'] ? parseInt(values['Position (optional)'], 10) : null,
        url: values['URL (optional)'] || null
      });
      toast.success('Ranking saved successfully.');
      fetchRankings();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to add ranking');
    }
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return data.filter((kw) => {
      const term = (kw.term || kw.keyword || '').toLowerCase();
      const change = kw.change || 0;
      if (filter === "Improved" && change <= 0) return false;
      if (filter === "Dropped" && change >= 0) return false;
      return !q || term.includes(q);
    });
  }, [query, filter, data]);

  const perPage = 10;
  const pageCount = Math.max(1, Math.ceil(filtered.length / perPage));
  const current = Math.min(page, pageCount);
  const rows = filtered.slice((current - 1) * perPage, current * perPage);

  if (loading || !client) {
    return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading rankings…" /></div></AdminShell>;
  }

  return (
    <AdminShell
      breadcrumb={client.name}
      title="Rankings"
      subtitle={`Keyword positions and history. Report month ${month}.`}
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Upload CSV" className="overflow-visible">
          <p className="rounded-md border border-dashed border-border bg-secondary px-3 py-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
            Required columns: keyword, position, date, url
          </p>
          <div className="mt-4 flex items-center gap-3">
            <input
              type="file"
              accept=".csv"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file.name, file);
                e.target.value = '';
              }}
              className="flex-1 text-xs text-muted-foreground"
            />
          </div>
        </Panel>

        <ManualEntryCard
          title="Add Single Keyword"
          submitLabel="Save Ranking"
          fields={[
            { label: "Keyword ID" },
            { label: "Date", type: "date", defaultValue: new Date().toISOString().split('T')[0] },
            { label: "Position (optional)", type: "number" },
            { label: "URL (optional)", type: "url" },
          ]}
          onSubmit={handleManualEntry}
        />
      </div>

      <TablePanel
        title={
          <div className="flex flex-wrap items-center gap-4">
            <h2 className="font-serif text-xl leading-none">Keyword Rankings</h2>
            <FilterChips
              items={["All", "Improved", "Dropped"]}
              value={filter}
              onChange={(next) => {
                setFilter(next);
                setPage(1);
              }}
            />
            <div className="flex flex-wrap gap-1">
              {Array.from({ length: pageCount }, (_, idx) => idx + 1).map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setPage(n)}
                  className={
                    n === current
                      ? "rounded border border-border bg-brand px-2.5 py-1 text-[11px] font-medium text-ink"
                      : "rounded border border-border px-2.5 py-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                  }
                >
                  Page {n}
                </button>
              ))}
            </div>
          </div>
        }
        action={
          <div className="relative mt-4 sm:mt-0">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              placeholder="Search keywords..."
              className={`${inputCls} w-full sm:w-64 pl-9`}
            />
          </div>
        }
        head={
          <>
            <Th>Keyword</Th>
            <Th align="right">Position</Th>
            <Th align="right">Change</Th>
            <Th align="right">Best</Th>
            <Th>Source</Th>
            <Th />
          </>
        }
      >
        {rows.length === 0 ? (
          <tr>
            <td colSpan={6} className="px-6 py-12 text-center text-sm text-muted-foreground">
              No rankings found.
            </td>
          </tr>
        ) : (
          rows.map((kw) => {
            const term = kw.term || kw.keyword || '-';
            const pos = kw.current_position || kw.position;
            const changeStr = kw.change && kw.change > 0 ? `+${kw.change}` : kw.change ? `${kw.change}` : '0';
            
            return (
              <Fragment key={kw.keyword_id}>
                <tr
                  onClick={() => {
                    // Only expand if there's history data
                    if (kw.history && kw.history.length > 0) {
                      setExpanded((prev) => (prev === kw.keyword_id ? null : kw.keyword_id));
                    } else {
                      toast.info(`No 90-day history available for "${term}".`);
                    }
                  }}
                  className={`transition-colors hover:bg-secondary ${kw.history?.length ? 'cursor-pointer' : ''}`}
                >
                  <Td>
                    <span className="font-medium">{term}</span>
                    {kw.ranking_url && (
                      <a href={kw.ranking_url} target="_blank" rel="noreferrer" className="block text-[10px] text-muted-foreground hover:underline mt-0.5 truncate max-w-[200px]" onClick={e => e.stopPropagation()}>
                        {kw.ranking_url}
                      </a>
                    )}
                  </Td>
                  <Td align="right">
                    <span className="rounded bg-brand-soft px-2 py-1 font-serif text-lg">
                      {pos || '-'}
                    </span>
                  </Td>
                  <Td align="right" className={`font-mono text-xs ${kw.change && kw.change > 0 ? 'text-up' : kw.change && kw.change < 0 ? 'text-down' : 'text-muted-foreground'}`}>
                    {changeStr}
                  </Td>
                  <Td align="right">
                    <span className="font-serif text-lg">{kw.best_position || '-'}</span>
                  </Td>
                  <Td>
                    <SourcePill>{kw.source === 'manual' ? 'Manual Entry' : 'DataForSEO'}</SourcePill>
                  </Td>
                  <Td align="right">
                    {kw.history && kw.history.length > 0 && (
                      <ChevronDown
                        className={`ml-auto size-4 text-muted-foreground transition-transform ${
                          expanded === kw.keyword_id ? "rotate-180" : ""
                        }`}
                      />
                    )}
                  </Td>
                </tr>
                {expanded === kw.keyword_id && kw.history && kw.history.length > 0 && (
                  <tr>
                    <td colSpan={6} className="bg-secondary px-6 py-5">
                      <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                        Position History
                      </p>
                      <div className="mt-8 h-48 w-full pr-4">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart
                            data={(() => {
                              const rawData = kw.history.slice(-30).map(h => ({
                                date: h.date,
                                position: h.position || 100
                              }));
                              // If only one point exists, duplicate it so a flat line can be drawn instead of a lone dot.
                              if (rawData.length === 1) {
                                return [
                                  { date: 'Start', position: rawData[0].position },
                                  { date: rawData[0].date, position: rawData[0].position }
                                ];
                              }
                              return rawData;
                            })()}
                            margin={{ top: 20, right: 10, left: 0, bottom: 0 }}
                          >
                            <defs>
                              <linearGradient id={`colorPos-${kw.keyword_id}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#f5c400" stopOpacity={0.2}/>
                                <stop offset="95%" stopColor="#f5c400" stopOpacity={0}/>
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.06)" />
                            <YAxis 
                              reversed 
                              axisLine={false}
                              tickLine={false}
                              tick={{ fill: '#8a8a85', fontSize: 11 }}
                              dx={-10}
                              domain={['dataMin - 5', 'dataMax + 5']} 
                            />
                            <XAxis 
                              dataKey="date" 
                              axisLine={false} 
                              tickLine={false} 
                              tick={{ fill: '#8a8a85', fontSize: 11 }}
                              dy={10}
                            />
                            <Tooltip
                              content={({ active, payload }) => {
                                if (active && payload && payload.length) {
                                  const data = payload[0].payload;
                                  return (
                                    <div className="rounded-lg border border-border bg-card/95 p-3 text-sm shadow-xl backdrop-blur-md">
                                      <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{data.date === 'Start' ? 'Initial' : data.date}</div>
                                      <div className="flex items-center gap-2 font-bold text-foreground">
                                        <div className="size-2 rounded-full bg-brand" />
                                        Position: {data.position}
                                      </div>
                                    </div>
                                  );
                                }
                                return null;
                              }}
                            />
                            <Area
                              type="linear"
                              dataKey="position"
                              stroke="#f5c400"
                              strokeWidth={2.5}
                              fillOpacity={1}
                              fill={`url(#colorPos-${kw.keyword_id})`}
                              dot={{ r: 4.5, fill: "#ffffff", stroke: "#f5c400", strokeWidth: 2 }}
                              activeDot={{ r: 6, fill: "#ffffff", stroke: "#1a1a1a", strokeWidth: 2.5 }}
                            >
                              <LabelList 
                                dataKey="position" 
                                position="top" 
                                offset={12}
                                fill="#1a1a1a"
                                style={{ fontSize: '11px', fontWeight: 600 }}
                              />
                            </Area>
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })
        )}
      </TablePanel>
    </AdminShell>
  );
};

export default Rankings;
