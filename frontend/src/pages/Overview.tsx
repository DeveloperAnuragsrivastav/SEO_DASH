import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Pencil, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import { AdminShell } from '../components/layout/AdminShell';
import {
  BarRow,
  Bento,
  Panel,
  StatCard,
  btnGhost,
  btnPrimary,
  inputCls
} from '../components/kit';

interface Snapshot {
  gsc?: { clicks?: number };
  ga4?: { sessions?: number };
  rankings?: {
    summary?: {
      top_10?: number;
      '11_20'?: number;
      '21_50'?: number;
      '51_plus'?: number;
      improved?: number;
      declined?: number;
    };
  };
  ai_visibility?: Array<{ mentioned: boolean }>;
  kpi_deltas?: {
    gsc?: { clicks?: number };
    ga4?: { sessions?: number };
  };
  sources?: {
    gsc?: string;
    ga4?: string;
    rankings?: string;
    ai_visibility?: string;
  };
}

interface ReportData {
  id: string;
  client_id: string;
  month: string;
  status: string;
  narrative: string | null;
  snapshot: Snapshot;
}

const Overview: React.FC = () => {
  const { clientId, month } = useParams<{ clientId: string; month: string }>();
  const { user } = useAuth();
  const [report, setReport] = useState<ReportData | null>(null);
  const [client, setClient] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);

  // Editable narrative state
  const [isEditingNarrative, setIsEditingNarrative] = useState(false);
  const [narrativeDraft, setNarrativeDraft] = useState('');
  const [isSavingNarrative, setIsSavingNarrative] = useState(false);

  const fetchClient = async () => {
    try {
      const res = await api.get(`/clients/${clientId}`);
      setClient(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchReport = async () => {
    try {
      setIsLoading(true);
      const res = await api.get(`/clients/${clientId}/reports/${month}`);
      setReport(res.data);
      setNarrativeDraft(res.data.narrative || '');
    } catch (err: any) {
      if (err.response?.status === 404) {
        setReport(null);
      } else {
        toast.error('Failed to fetch report data.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (clientId && month) {
      fetchClient();
      fetchReport();
    }
  }, [clientId, month]);

  const handleGenerate = async () => {
    try {
      setIsGenerating(true);
      await api.post(`/clients/${clientId}/reports/generate`, { month: `${month}-01` });
      toast.success('Report generated successfully.');
      await fetchReport();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to generate report.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveNarrative = async () => {
    if (!narrativeDraft.trim()) {
      toast.error('Summary cannot be empty.');
      return;
    }
    try {
      setIsSavingNarrative(true);
      const res = await api.put(`/clients/${clientId}/reports/${month}-01`, {
        narrative: narrativeDraft
      });
      setReport(prev => prev ? { ...prev, narrative: res.data.narrative } : null);
      setIsEditingNarrative(false);
      toast.success('Executive summary saved.');
    } catch (err: any) {
      toast.error('Failed to save narrative.');
    } finally {
      setIsSavingNarrative(false);
    }
  };

  if (isLoading || !client) {
    return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading overview…" /></div></AdminShell>;
  }

  if (!report) {
    return (
      <AdminShell
        breadcrumb={client.name}
        title="Overview"
        subtitle={`Performance snapshot for ${month}`}
      >
        <div className="mx-auto mt-10 max-w-lg rounded-xl border border-border bg-card p-8 text-center shadow-[0_12px_24px_-4px_rgba(0,0,0,0.08)]">
          <div className="mx-auto mb-6 flex size-20 items-center justify-center rounded-full bg-brand/10">
            <RefreshCw className="size-10 text-brand" />
          </div>
          <h2 className="mb-3 font-serif text-2xl text-foreground">No Report Generated</h2>
          <p className="mb-8 text-sm leading-relaxed text-muted-foreground">
            There is no report available for {month}. You can generate it now to aggregate performance metrics across all integrated sources.
          </p>
          <button 
            onClick={handleGenerate}
            disabled={isGenerating}
            className={`${btnPrimary} w-full justify-center text-base py-3`}
          >
            <RefreshCw className={`size-5 ${isGenerating ? 'animate-spin' : ''}`} />
            {isGenerating ? 'Generating Report...' : 'Generate Report'}
          </button>
        </div>
      </AdminShell>
    );
  }

  const snap = report.snapshot;
  const aiMentions = snap.ai_visibility?.filter(m => m.mentioned).length || 0;

  const distribution = [
    { label: "Top 10", value: snap.rankings?.summary?.top_10 || 0 },
    { label: "11 - 20", value: snap.rankings?.summary?.['11_20'] || 0 },
    { label: "21 - 50", value: snap.rankings?.summary?.['21_50'] || 0 },
    { label: "51+", value: snap.rankings?.summary?.['51_plus'] || 0 },
  ];
  const maxDist = Math.max(...distribution.map((d) => d.value), 1);

  return (
    <AdminShell
      breadcrumb={client.name}
      title="Overview"
      subtitle={`Performance snapshot for ${month}`}
    >
      <Bento>
        <StatCard 
          label="Search Clicks" 
          value={snap.gsc?.clicks?.toLocaleString() || '0'} 
          source={snap.sources?.gsc === 'manual' ? 'Agency: Manual Entry' : 'GSC · Daily'}
        />
        <StatCard 
          label="Website Sessions" 
          value={snap.ga4?.sessions?.toLocaleString() || '0'} 
          source={snap.sources?.ga4 === 'manual' ? 'Agency: Manual Entry' : 'GA4 · Daily'}
        />
        <StatCard 
          label="Rankings Improved" 
          value={snap.rankings?.summary?.improved || 0} 
          source={snap.sources?.rankings === 'manual' ? 'Agency: Manual Entry' : 'DataForSEO · Nightly'}
        />
        <StatCard 
          label="AI Mentions" 
          value={aiMentions} 
          source={snap.sources?.ai_visibility === 'manual' ? 'Agency: Manual Entry' : 'LLM Responses · On-demand'}
        />
      </Bento>

      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <Panel title="Position Distribution">
            <div className="space-y-5">
              {distribution.map((row) => (
                <BarRow key={row.label} label={row.label} value={row.value} max={maxDist} />
              ))}
            </div>
          </Panel>
        </div>

        <div className="lg:col-span-7">
          <Panel
            title="Executive Summary"
            action={
              user?.role && ['agency_admin', 'agency_staff'].includes(user.role) && (
                <button
                  type="button"
                  className={btnGhost}
                  onClick={() => setIsEditingNarrative((prev) => !prev)}
                >
                  <Pencil className="size-3.5" />
                  {isEditingNarrative ? "Close Editor" : "Edit Summary"}
                </button>
              )
            }
          >
            {isEditingNarrative ? (
              <div>
                <textarea
                  rows={7}
                  autoFocus
                  value={narrativeDraft}
                  onChange={(e) => setNarrativeDraft(e.target.value)}
                  placeholder="Write the monthly executive narrative..."
                  className={inputCls}
                />
                <div className="mt-4 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => { setIsEditingNarrative(false); setNarrativeDraft(report.narrative || ''); }}
                    className="rounded-md border border-border px-3 py-2 text-sm font-medium transition-colors hover:bg-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className={btnPrimary}
                    disabled={isSavingNarrative}
                    onClick={handleSaveNarrative}
                  >
                    {isSavingNarrative ? 'Saving...' : 'Save Summary'}
                  </button>
                </div>
              </div>
            ) : report.narrative?.trim() ? (
              <p className="max-w-[60ch] whitespace-pre-wrap text-pretty text-sm leading-relaxed">
                {report.narrative}
              </p>
            ) : (
              <>
                <p className="max-w-[60ch] text-pretty text-sm leading-relaxed text-muted-foreground">
                  Narrative auto-generation failed. Please draft manually.
                </p>
                {user?.role && ['agency_admin', 'agency_staff'].includes(user.role) && (
                  <button
                    type="button"
                    onClick={() => setIsEditingNarrative(true)}
                    className="mt-6 block w-full rounded-md border border-dashed border-border bg-secondary p-4 text-left transition-colors hover:border-brand"
                  >
                    <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                      Draft area
                    </span>
                    <span className="mt-2 block text-sm text-muted-foreground">
                      Write the monthly executive narrative...
                    </span>
                  </button>
                )}
              </>
            )}
          </Panel>
        </div>
      </div>
    </AdminShell>
  );
};

export default Overview;
