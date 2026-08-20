import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import api from '../../api/client';
import LoadingSpinner from '../../components/LoadingSpinner';
import { toast } from 'sonner';

import { AdminShell } from '../../components/layout/AdminShell';
import {
  Panel,
  StatusPill,
  TablePanel,
  Td,
  Th,
  btnPrimary,
  btnGhost,
  inputCls,
} from '../../components/kit';

interface Keyword {
  id: string;
  term: string;
  group_tag?: string;
  target_url?: string;
  search_volume?: number;
  initial_rank?: number;
  is_active: boolean;
  added_at: string;
}

const Keywords: React.FC = () => {
  const { clientId } = useParams<{ clientId: string }>();
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  const formRef = useRef<HTMLFormElement>(null);

  const fetchKeywords = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/keywords`);
      setKeywords(data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to fetch keywords');
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
    fetchKeywords().finally(() => setLoading(false));
  }, [clientId]);

  const addKeyword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    
    const formData = {
      term: String(data.get("term") ?? "").trim(),
      group_tag: String(data.get("group_tag") ?? "").trim(),
      target_url: String(data.get("target_url") ?? "").trim(),
      fetch_metrics: data.get("fetch_metrics") === "on"
    };

    if (!formData.term) {
      toast.error("Keyword term is required.");
      return;
    }

    try {
      await api.post(`/clients/${clientId}/keywords`, formData);
      toast.success(`Added "${formData.term}" to nightly tracking.`);
      form.reset();
      fetchKeywords();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'An error occurred while adding keyword');
    }
  };

  const handleToggleActive = async (kw: Keyword) => {
    try {
      await api.put(`/clients/${clientId}/keywords/${kw.id}?is_active=${!kw.is_active}`);
      const next = !kw.is_active ? "reactivated" : "deactivated";
      toast.success(`"${kw.term}" ${next}.`);
      fetchKeywords();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update keyword');
    }
  };

  if (loading || !client) return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading keywords…" /></div></AdminShell>;

  return (
    <AdminShell
      breadcrumb={`${client.name} / Keywords`}
      title="Keyword Management"
      subtitle="Terms tracked nightly via the DataForSEO SERP API."
      backLink={{ to: "/admin/clients", label: "Back to Clients" }}
      actions={
        <button
          type="button"
          className={btnPrimary}
          onClick={() => formRef.current?.querySelector("input")?.focus()}
        >
          Add Keyword
        </button>
      }
    >
      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <TablePanel
            title="Tracked Keywords"
            head={
              <>
                <Th>Term</Th>
                <Th>Group Tag</Th>
                <Th>Target URL</Th>
                <Th align="right">Search Volume</Th>
                <Th>Status</Th>
                <Th align="right">Actions</Th>
              </>
            }
            footer={
              <span className="text-xs text-muted-foreground">
                {keywords.filter((r) => r.is_active).length} of {client.package_keywords || 0} package keywords in use
              </span>
            }
          >
            {keywords.length === 0 ? (
               <tr>
                 <td colSpan={6} className="px-6 py-12 text-center text-sm text-muted-foreground">
                   No keywords found for this client.
                 </td>
               </tr>
            ) : (
              keywords.map((kw) => (
                <tr key={kw.id} className="transition-colors hover:bg-secondary">
                  <Td>
                    <span className="font-medium">{kw.term}</span>
                  </Td>
                  <Td>
                    <span className="rounded bg-secondary px-2 py-0.5 text-[11px] text-muted-foreground">
                      {kw.group_tag || 'ungrouped'}
                    </span>
                  </Td>
                  <Td className="max-w-[220px] truncate font-mono text-xs text-muted-foreground">
                    {kw.target_url || '-'}
                  </Td>
                  <Td align="right">
                    <span className="font-serif text-lg">{kw.search_volume !== null && kw.search_volume !== undefined ? kw.search_volume.toLocaleString() : '-'}</span>
                  </Td>
                  <Td>
                    <StatusPill status={kw.is_active ? "Active" : "Paused"} />
                  </Td>
                  <Td align="right">
                    <button
                      type="button"
                      onClick={() => handleToggleActive(kw)}
                      className={
                        kw.is_active
                          ? "px-2 py-1 text-[11px] font-medium text-status-churned-text hover:underline"
                          : "px-2 py-1 text-[11px] font-medium text-muted-foreground hover:underline"
                      }
                    >
                      {kw.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </Td>
                </tr>
              ))
            )}
          </TablePanel>
        </div>

        <div className="lg:col-span-4">
          <Panel title="Add Keyword">
            <form ref={formRef} onSubmit={addKeyword}>
              <div className="space-y-4">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    Keyword Term
                  </span>
                  <input name="term" placeholder="e.g. plumber near me" className={inputCls} />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    Group Tag (Optional)
                  </span>
                  <input name="group_tag" placeholder="e.g. emergency services" className={inputCls} />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-muted-foreground">
                    Target URL (Optional)
                  </span>
                  <input
                    name="target_url"
                    placeholder="https://example.com/plumbing"
                    className={inputCls}
                  />
                </label>
                <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <input
                    type="checkbox"
                    name="fetch_metrics"
                    defaultChecked
                    className="size-4 accent-[var(--brand)]"
                  />
                  Fetch Search Volume from DataForSEO
                </label>
              </div>
              <div className="mt-5 flex justify-end gap-2">
                <button
                  type="reset"
                  className={btnGhost}
                >
                  Clear
                </button>
                <button type="submit" className={btnPrimary}>
                  Add Keyword
                </button>
              </div>
            </form>
          </Panel>
        </div>
      </div>
    </AdminShell>
  );
};

export default Keywords;
