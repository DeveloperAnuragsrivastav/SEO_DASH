import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';

import api from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import { AdminShell } from '../components/layout/AdminShell';
import {
  ManualEntryCard,
  ManualEntryBadge,
  TablePanel,
  Td,
  Th,
} from '../components/kit';

interface AudienceRow {
  dimension: string;
  sessions: number;
  users: number;
  engaged_sessions: number;
  conversions: number;
  revenue: number;
  source: 'api' | 'manual';
}

interface AudienceData {
  channel: AudienceRow[];
  device: AudienceRow[];
  country: AudienceRow[];
}

const DimensionTable: React.FC<{ title: string, data: AudienceRow[] }> = ({ title, data }) => {
  if (data.length === 0) return null;

  const maxSessions = Math.max(...data.map(d => d.sessions), 1);

  return (
    <TablePanel
      title={title}
      head={
        <>
          <Th>{title}</Th>
          <Th>Sessions (Volume)</Th>
          <Th align="right">Users</Th>
          <Th align="right">Engaged</Th>
          <Th align="right">Conversions</Th>
          <Th align="right">Source</Th>
        </>
      }
    >
      {data.map((row) => (
        <tr key={row.dimension} className="transition-colors hover:bg-secondary">
          <Td>
            <span className="font-medium">{row.dimension}</span>
          </Td>
          <Td>
            <div className="flex items-center gap-3">
              <div className="h-1.5 w-32 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-[#f5c400]"
                  style={{ width: `${(row.sessions / maxSessions) * 100}%` }}
                />
              </div>
              <span className="text-sm font-medium">{row.sessions.toLocaleString()}</span>
            </div>
          </Td>
          <Td align="right" className="text-[13px] text-muted-foreground">{row.users.toLocaleString()}</Td>
          <Td align="right" className="text-[13px] text-muted-foreground">{row.engaged_sessions.toLocaleString()}</Td>
          <Td align="right" className="text-[13px] text-muted-foreground">{row.conversions.toLocaleString()}</Td>
          <Td align="right">
            {row.source === 'manual' ? (
              <ManualEntryBadge />
            ) : (
              <span className="font-mono text-[10px] uppercase text-muted-foreground">
                GA4 API
              </span>
            )}
          </Td>
        </tr>
      ))}
    </TablePanel>
  );
};

const Audience: React.FC = () => {
  const { clientId, month } = useParams<{ clientId: string; month: string }>();
  const [data, setData] = useState<AudienceData>({ channel: [], device: [], country: [] });
  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState(true);

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
      const response = await api.get(`/clients/${clientId}/audience/${month}`);
      setData(response.data.data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load audience data');
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchClient(), fetchData()]).finally(() => setLoading(false));
  }, [clientId, month]);

  const handleFileUpload = async (_fileName: string, file: File) => {
    if (!clientId) return;
    
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
          
          if (!record.captured_on || !record.dimension_key || !record.dimension_value || !record.sessions || !record.users || !record.engaged_sessions || !record.conversions || !record.revenue) {
            throw new Error(`Row ${i} is missing required fields`);
          }
          
          records.push({
            captured_on: record.captured_on,
            dimension_key: record.dimension_key,
            dimension_value: record.dimension_value,
            sessions: parseInt(record.sessions, 10),
            users: parseInt(record.users, 10),
            engaged_sessions: parseInt(record.engaged_sessions, 10),
            conversions: parseInt(record.conversions, 10),
            revenue: parseFloat(record.revenue)
          });
        }

        const res = await api.post(`/clients/${clientId}/manual-ga4`, { records });
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
      await api.post(`/clients/${clientId}/manual-ga4`, {
        records: [
          {
            captured_on: `${month}-01`,
            sessions: parseInt(values['Sessions'], 10),
            users: parseInt(values['Total Users (Count)'], 10),
            engaged_sessions: parseInt(values['Engaged'], 10),
            conversions: parseInt(values['Conv.'], 10),
            revenue: parseFloat(values['Revenue'] || '0'),
            dimension_key: values['Dimension'].toLowerCase(),
            dimension_value: values["Value (e.g. 'Organic Search')"]
          }
        ]
      });
      fetchData();
    } catch (err: any) {
      if (err.response?.data?.detail) {
        toast.error(Array.isArray(err.response.data.detail) ? 'Validation Error' : err.response.data.detail);
      } else {
        toast.error('Failed to save manual GA4 metric');
      }
    }
  };

  if (loading || !client) {
    return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading audience breakdown…" /></div></AdminShell>;
  }

  return (
    <AdminShell
      breadcrumb={client.name}
      title="Audience Breakdown"
      subtitle={`Traffic sources, devices, and geography for ${month}.`}
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 mb-8">
        <div className="rounded-lg border border-border bg-card p-6">
           <h2 className="flex items-center gap-2 font-serif text-xl leading-none mb-4">
             Upload CSV
           </h2>
           <p className="rounded-md border border-dashed border-border bg-secondary px-3 py-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
             Required: captured_on, dimension_key, dimension_value, sessions, users, engaged_sessions, conversions, revenue
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
          title="Add Single Dimension Metric"
          submitLabel="Save Metric"
          fields={[
            { label: "Dimension", options: ["Channel", "Device", "Country"] },
            { label: "Value (e.g. 'Organic Search')" },
            { label: "Sessions", type: "number" },
            { label: "Total Users (Count)", type: "number" },
            { label: "Engaged", type: "number" },
            { label: "Conv.", type: "number" },
            { label: "Revenue", type: "number" },
          ]}
          onSubmit={handleManualEntry}
        />
      </div>

      <div className="flex flex-col gap-8">
        {data.channel.length === 0 && data.device.length === 0 && data.country.length === 0 && (
           <div className="rounded-lg border border-border bg-card px-6 py-12 text-center text-sm text-muted-foreground">
             No audience data found for this month.
           </div>
        )}
        <DimensionTable title="Acquisition Channels" data={data.channel} />
        <DimensionTable title="Device Categories" data={data.device} />
        <DimensionTable title="Top Countries" data={data.country} />
      </div>
    </AdminShell>
  );
}

export default Audience;
