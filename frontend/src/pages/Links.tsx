import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ExternalLink } from 'lucide-react';

import api from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import { AdminShell } from '../components/layout/AdminShell';
import {
  Bento,
  ManualEntryCard,
  StatCard,
  TablePanel,
  Td,
  Th,
} from '../components/kit';

interface LinkEntry {
  id: string;
  domain: string;
  url: string;
  activity_type: string;
  status: string;
  dr: number | null;
  last_checked: string | null;
  created_on: string;
}

interface LinksData {
  kpis: {
    total_links: number;
    unique_domains: number;
    activity_breakdown: Record<string, number>;
  };
  links: LinkEntry[];
}

const Links: React.FC = () => {
  const { clientId, month } = useParams<{ clientId: string, month: string }>();
  const [data, setData] = useState<LinksData | null>(null);
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
      const res = await api.get(`/clients/${clientId}/links/${month}`);
      setData(res.data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load links data');
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchClient(), fetchData()]).finally(() => setLoading(false));
  }, [clientId, month]);

  const handleManualEntry = async (values: Record<string, string>) => {
    if (!clientId) return;
    try {
      await api.post(`/clients/${clientId}/links`, {
        domain: values['Domain (e.g. forbes.com)'],
        url: values['URL'],
        activity_type: values['Activity Type (e.g. Guest Post)'],
        status: values['Status']?.toLowerCase() || 'active',
        dr: values['Domain Rating (DR) - Optional'] ? parseInt(values['Domain Rating (DR) - Optional'], 10) : null,
        created_on: values['Date']
      });
      toast.success('Link saved successfully.');
      fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create link');
    }
  };

  if (loading || !client || !data) {
    return (
      <AdminShell breadcrumb="Loading..." title="Loading...">
        <div className="flex h-64 items-center justify-center">
          <LoadingSpinner label="Loading links…" />
        </div>
      </AdminShell>
    );
  }

  const topActivity = Object.entries(data.kpis.activity_breakdown).sort((a, b) => b[1] - a[1])[0];

  return (
    <AdminShell
      breadcrumb={client.name}
      title="Links Built"
      subtitle={`Backlink activity and domain metrics for ${month}.`}
    >
      <section className="space-y-4">
        <Bento>
          <StatCard label="Total Links" value={data.kpis.total_links} source="Manual" />
          <StatCard label="Unique Domains" value={data.kpis.unique_domains} source="Manual" />
          <StatCard label="Top Activity" value={topActivity ? topActivity[0] : '-'} source={topActivity ? `${topActivity[1]} links` : 'Manual'} />
        </Bento>
      </section>

      <div className="flex flex-col gap-8">
        <div>
          <TablePanel
            title="Link Details"
            head={
              <>
                <Th>Domain</Th>
                <Th>URL</Th>
                <Th>Activity</Th>
                <Th>Status</Th>
                <Th align="right">DR</Th>
                <Th align="right">Last Checked</Th>
              </>
            }
          >
            {data.links.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-12 text-center text-sm text-muted-foreground">
                  No links found for this period.
                </td>
              </tr>
            ) : (
              data.links.map((link) => (
                <tr key={link.id} className="transition-colors hover:bg-secondary">
                  <Td className="font-medium text-ink">{link.domain}</Td>
                  <Td>
                    <a href={link.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-ink hover:underline">
                      <span className="truncate max-w-[200px]" title={link.url}>
                        {link.url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                      </span>
                      <ExternalLink className="size-3" />
                    </a>
                  </Td>
                  <Td className="text-muted-foreground">{link.activity_type}</Td>
                  <Td>
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${
                      link.status === 'active' ? 'bg-up-soft text-up border border-up/20' : 
                      link.status === 'removed' ? 'bg-down-soft text-down border border-down/20' : 
                      'bg-secondary text-muted-foreground border border-border'
                    }`}>
                      {link.status}
                    </span>
                  </Td>
                  <Td align="right" className="font-mono">{link.dr ?? '-'}</Td>
                  <Td align="right" className="font-mono text-xs text-muted-foreground">
                    {link.last_checked ? new Date(link.last_checked).toLocaleDateString() : 'Pending'}
                  </Td>
                </tr>
              ))
            )}
          </TablePanel>
        </div>

        <div>
          <ManualEntryCard
            title="Add Manual Link"
            submitLabel="Save Link"
            fields={[
              { label: "Date", type: "date", defaultValue: `${month}-01` },
              { label: "Domain (e.g. forbes.com)" },
              { label: "URL", type: "url" },
              { label: "Activity Type (e.g. Guest Post)" },
              { label: "Status", options: ["Active", "Pending", "Removed"] },
              { label: "Domain Rating (DR) - Optional", type: "number" },
            ]}
            onSubmit={handleManualEntry}
          />
        </div>
      </div>
    </AdminShell>
  );
}

export default Links;
