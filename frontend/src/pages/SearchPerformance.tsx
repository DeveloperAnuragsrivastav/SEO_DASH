import React, { useEffect, useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';

import api from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import { AdminShell } from '../components/layout/AdminShell';
import {
  Bento,
  EmptyState,
  FilterChips,
  ManualEntryCard,
  SourcePill,
  StatCard,
  TablePanel,
  Td,
  Th,
} from '../components/kit';

interface SearchRow {
  url: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
  categories: string[];
  source: 'api' | 'manual';
}

const SearchPerformance: React.FC = () => {
  const { clientId, month } = useParams<{ clientId: string; month: string }>();
  const [data, setData] = useState<SearchRow[]>([]);
  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  const [pageFilter, setPageFilter] = useState("All");

  const fetchClient = async () => {
    try {
      const res = await api.get(`/clients/${clientId}`);
      setClient(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchData = async () => {
    try {
      const response = await api.get(`/clients/${clientId}/search/${month}`);
      setData(response.data.data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load search data');
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchClient(), fetchData()]).finally(() => setLoading(false));
  }, [clientId, month]);

  const handleFileUpload = async (_fileName: string, file: File) => {
    if (!clientId) return;
    
    // We parse the CSV on client-side as done originally in ManualGSCUI
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const text = e.target?.result as string;
        const lines = text.split('\n').map(l => l.trim()).filter(l => l);
        if (lines.length < 2) throw new Error('CSV is empty or missing headers');
        
        const headers = lines[0].toLowerCase().split(',');
        const records = [];
        
        for (let i = 1; i < lines.length; i++) {
          const values = lines[i].split(',');
          if (values.length < 5) continue;
          
          const record: any = {};
          headers.forEach((h, idx) => {
            record[h.trim()] = values[idx]?.trim();
          });
          
          if (!record.captured_on || !record.page_url || !record.clicks || !record.impressions || !record.ctr || !record.position) {
            throw new Error(`Row ${i} is missing required fields`);
          }
          
          records.push({
            captured_on: record.captured_on,
            dimension_key: 'page',
            dimension_value: record.page_url,
            clicks: parseInt(record.clicks, 10),
            impressions: parseInt(record.impressions, 10),
            ctr: parseFloat(record.ctr),
            position: parseFloat(record.position)
          });
        }

        const res = await api.post(`/clients/${clientId}/manual-gsc`, { records });
        toast.success(`Successfully uploaded ${res.data.rows_inserted} rows.`);
        fetchData();
      } catch (err: any) {
        toast.error(err.message || 'Failed to parse or upload CSV');
      }
    };
    reader.readAsText(file);
  };

  const handleManualEntry = async (values: Record<string, string>) => {
    if (!clientId || !month) return;
    try {
      await api.post(`/clients/${clientId}/manual-gsc`, {
        records: [
          {
            captured_on: `${month}-01`, // Default to first day of report month
            clicks: parseInt(values['Clicks'], 10),
            impressions: parseInt(values['Impressions'], 10),
            ctr: parseFloat(values['CTR (e.g. 0.05 for 5%)']),
            position: parseFloat(values['Avg Position']),
            dimension_key: 'page',
            dimension_value: values['Page URL']
          }
        ]
      });
      fetchData();
    } catch (err: any) {
      if (err.response?.data?.detail) {
        toast.error(Array.isArray(err.response.data.detail) ? 'Validation Error' : err.response.data.detail);
      } else {
        toast.error('Failed to save manual GSC metric');
      }
    }
  };

  const filteredData = useMemo(() => {
    return data.filter(row => {
      if (pageFilter === 'All') return true;
      return row.categories.includes(pageFilter);
    });
  }, [data, pageFilter]);

  if (loading || !client) {
    return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading search performance…" /></div></AdminShell>;
  }

  // Calculate aggregates for Bento
  const totalClicks = data.reduce((acc, row) => acc + row.clicks, 0);
  const totalImpressions = data.reduce((acc, row) => acc + row.impressions, 0);
  const avgCtr = data.length > 0 ? (data.reduce((acc, row) => acc + row.ctr, 0) / data.length) : 0;
  const avgPos = data.length > 0 ? (data.reduce((acc, row) => acc + row.position, 0) / data.length) : 0;

  return (
    <AdminShell
      breadcrumb={client.name}
      title="Search Performance"
      subtitle={`Landing page breakdown and trends for ${month}.`}
    >
      <Bento>
        <StatCard label="Clicks" value={totalClicks.toLocaleString()} source="GSC · daily" />
        <StatCard label="Impressions" value={totalImpressions.toLocaleString()} source="GSC · daily" />
        <StatCard label="CTR" value={`${(avgCtr * 100).toFixed(1)}%`} source="GSC · daily" />
        <StatCard label="Avg Position" value={avgPos.toFixed(1)} source="GSC · daily" />
      </Bento>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-6">
           <h2 className="flex items-center gap-2 font-serif text-xl leading-none mb-4">
             Upload CSV
           </h2>
           <p className="rounded-md border border-dashed border-border bg-secondary px-3 py-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
             Required: captured_on, page_url, clicks, impressions, ctr, position
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
        </div>

        <ManualEntryCard
          title="Add Single Page Metric"
          submitLabel="Save Metric"
          fields={[
            { label: "Page URL" },
            { label: "Clicks", type: "number" },
            { label: "Impressions", type: "number" },
            { label: "CTR (e.g. 0.05 for 5%)", type: "number" },
            { label: "Avg Position", type: "number" },
          ]}
          onSubmit={handleManualEntry}
        />
      </div>

      <TablePanel
        title={
          <div className="flex flex-wrap items-center gap-4">
            <h2 className="font-serif text-xl leading-none">Landing Pages</h2>
            <FilterChips
              items={["All", "Top", "Trending Up", "Trending Down", "New"]}
              value={pageFilter}
              onChange={setPageFilter}
            />
          </div>
        }
        head={
          <>
            <Th>Page URL</Th>
            <Th align="right">Clicks</Th>
            <Th align="right">Impressions</Th>
            <Th align="right">CTR</Th>
            <Th align="right">Avg Pos</Th>
            <Th>Source</Th>
          </>
        }
      >
        {filteredData.length === 0 ? (
          <tr>
            <td colSpan={6} className="px-6 py-12 text-center text-sm text-muted-foreground">
              <EmptyState>{`No pages found for the "${pageFilter}" filter.`}</EmptyState>
            </td>
          </tr>
        ) : (
          filteredData.map((row, i) => (
            <tr key={i} className="transition-colors hover:bg-secondary">
              <Td>
                <div className="font-medium max-w-[300px] truncate" title={row.url}>{row.url}</div>
                <div className="mt-1 flex gap-1.5 flex-wrap">
                  {row.categories.map(cat => (
                    <span 
                      key={cat} 
                      className={`px-1.5 py-0.5 rounded text-[9px] font-medium uppercase tracking-wider ${
                        cat === 'Top' || cat === 'Trending Up' 
                          ? 'bg-brand-soft text-ink border border-brand' 
                          : 'bg-secondary text-muted-foreground border border-border'
                      }`}
                    >
                      {cat}
                    </span>
                  ))}
                </div>
              </Td>
              <Td align="right" className="font-mono text-sm">{row.clicks.toLocaleString()}</Td>
              <Td align="right" className="font-mono text-sm text-muted-foreground">{row.impressions.toLocaleString()}</Td>
              <Td align="right" className="font-mono text-sm text-muted-foreground">{(row.ctr * 100).toFixed(1)}%</Td>
              <Td align="right" className="font-mono text-sm text-muted-foreground">{row.position.toFixed(1)}</Td>
              <Td>
                <SourcePill>{row.source === 'manual' ? 'Manual Entry' : 'GSC API'}</SourcePill>
              </Td>
            </tr>
          ))
        )}
      </TablePanel>
    </AdminShell>
  );
};

export default SearchPerformance;
