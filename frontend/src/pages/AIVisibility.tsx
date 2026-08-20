import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { SlidersHorizontal } from 'lucide-react';

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
  btnGhost,
} from '../components/kit';

interface CitedPage {
  url: string;
  mentions: number;
}

interface AIOverviewKeyword {
  keyword_id: string;
  term: string;
  position: number;
}

interface AIVisibilityData {
  section1: {
    total_tracked_prompts: number;
    platforms: Record<string, { mentions: number }>;
    cited_pages: CitedPage[];
  };
  section2: {
    total_ai_overview_keywords: number;
    keywords: AIOverviewKeyword[];
  };
  section3?: {
    ai_referrals: { source: string; sessions: number }[];
  };
}

const AIVisibility: React.FC = () => {
  const { clientId, month } = useParams<{ clientId: string, month: string }>();
  const [data, setData] = useState<AIVisibilityData | null>(null);
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
      const res = await api.get(`/clients/${clientId}/ai-visibility/${month}`);
      setData(res.data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load AI Visibility data');
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
          if (values.length < 3) continue;
          
          const record: any = {};
          headers.forEach((h, idx) => {
            record[h.trim()] = values[idx]?.trim();
          });
          
          if (!record.captured_on || !record.platform || !record.mentioned) {
            throw new Error(`Row ${i} is missing required fields: captured_on, platform, mentioned`);
          }

          const isMentioned = record.mentioned.toLowerCase() === 'true' || record.mentioned === '1';
          
          records.push({
            captured_on: record.captured_on,
            platform: record.platform,
            mentioned: isMentioned,
            prompt_id: record.prompt_id || null,
            cited_pages: null
          });
        }

        const res = await api.post(`/clients/${clientId}/ai_mentions/bulk`, records);
        toast.success(`Successfully uploaded ${res.data.rows_inserted} rows.`);
        fetchData();
      } catch (err: any) {
        toast.error(err.message || 'Failed to parse or upload CSV');
      }
    };
    reader.readAsText(file);
  };

  const handleManualEntry = async (values: Record<string, string>) => {
    if (!clientId) return;
    try {
      await api.post(`/clients/${clientId}/ai_mentions/manual`, {
        captured_on: values['Captured On'],
        platform: values['Platform'].toLowerCase(),
        mentioned: values['Mentioned?'] === 'on',
        prompt_id: values['Prompt ID (optional UUID)'] || null,
        cited_pages: null
      });
      toast.success('AI Mention saved successfully.');
      fetchData();
    } catch (err: any) {
      if (err.response?.data?.detail) {
        toast.error(Array.isArray(err.response.data.detail) ? 'Validation Error' : err.response.data.detail);
      } else {
        toast.error('Failed to save manual AI mention metric');
      }
    }
  };

  if (loading || !client || !data) {
    return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading AI visibility…" /></div></AdminShell>;
  }

  return (
    <AdminShell
      breadcrumb={client.name}
      title="AI Visibility"
      subtitle={`Brand visibility across LLMs and AI Overviews. Report month ${month}.`}
      actions={
        <button
          type="button"
          onClick={() => {
            document
              .getElementById("manual-entry")
              ?.scrollIntoView({ behavior: "smooth", block: "center" });
            toast.info("Manual data entry is at the bottom of this report.");
          }}
          className={`${btnGhost} border-brand text-ink`}
        >
          <SlidersHorizontal className="size-3.5" />
          Manual Data Entry
        </button>
      }
    >
      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <h2 className="font-serif text-2xl leading-none">LLM Brand Mentions</h2>
          <span className="text-sm text-muted-foreground">
            Based on {data.section1.total_tracked_prompts} tracked prompts this month.
          </span>
        </div>
        <Bento>
          <StatCard label="ChatGPT Mentions" value={data.section1.platforms['chatgpt']?.mentions || 0} source="LLM responses" />
          <StatCard label="Claude Mentions" value={data.section1.platforms['claude']?.mentions || 0} source="LLM responses" />
          <StatCard label="Gemini Mentions" value={data.section1.platforms['gemini']?.mentions || 0} source="LLM responses" />
          <StatCard label="Perplexity Mentions" value={data.section1.platforms['perplexity']?.mentions || 0} source="LLM responses" />
        </Bento>
      </section>

      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <TablePanel
            title="Most Cited Pages"
            head={
              <>
                <Th>URL</Th>
                <Th align="right">Citations</Th>
              </>
            }
          >
            {data.section1.cited_pages.length === 0 ? (
              <tr>
                <td colSpan={2} className="px-6 py-12 text-center text-sm text-muted-foreground">
                  No citations found for this period.
                </td>
              </tr>
            ) : (
              data.section1.cited_pages.map((page) => (
                <tr key={page.url} className="transition-colors hover:bg-secondary">
                  <Td className="font-mono text-xs text-muted-foreground">{page.url}</Td>
                  <Td align="right">
                    <span className="font-serif text-lg">{page.mentions}</span>
                  </Td>
                </tr>
              ))
            )}
          </TablePanel>
        </div>

        <div className="lg:col-span-5">
          <TablePanel
            title={
              <div>
                <h2 className="font-serif text-xl leading-none">Google AI Overview Presence</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  {data.section2.total_ai_overview_keywords} keywords triggered AI Overviews this month.
                </p>
              </div>
            }
            head={
              <>
                <Th>Keyword</Th>
                <Th align="right">Rank Position</Th>
              </>
            }
          >
            {data.section2.keywords.length === 0 ? (
              <tr>
                <td colSpan={2} className="px-6 py-12 text-center text-sm text-muted-foreground">
                  No AI Overviews detected for tracked keywords this period.
                </td>
              </tr>
            ) : (
              data.section2.keywords.map((row) => (
                <tr key={row.keyword_id} className="transition-colors hover:bg-secondary">
                  <Td>{row.term}</Td>
                  <Td align="right">
                    <span className="rounded bg-brand-soft px-2 py-1 font-serif text-lg">
                      {row.position}
                    </span>
                  </Td>
                </tr>
              ))
            )}
          </TablePanel>
        </div>
      </div>

      {data.section3 && (
        <div className="mt-8">
          <TablePanel
            title={
              <div>
                <h2 className="font-serif text-xl leading-none">AI Referral Traffic (GA4)</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Traffic attributed to AI platforms via sessionSource.
                </p>
              </div>
            }
            head={
              <>
                <Th>Source</Th>
                <Th align="right">Sessions</Th>
              </>
            }
          >
            {data.section3.ai_referrals.length === 0 ? (
              <tr>
                <td colSpan={2} className="px-6 py-12 text-center text-sm text-muted-foreground">
                  No AI referral traffic detected this period.
                </td>
              </tr>
            ) : (
              data.section3.ai_referrals.map((row) => (
                <tr key={row.source} className="transition-colors hover:bg-secondary">
                  <Td className="font-medium">{row.source}</Td>
                  <Td align="right">
                    <span className="font-serif text-lg">{row.sessions}</span>
                  </Td>
                </tr>
              ))
            )}
          </TablePanel>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 mt-8" id="manual-entry">
        <div className="rounded-lg border border-border bg-card p-6">
           <h2 className="flex items-center gap-2 font-serif text-xl leading-none mb-4">
             Upload CSV
           </h2>
           <p className="rounded-md border border-dashed border-border bg-secondary px-3 py-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
             Required: captured_on, platform, mentioned; Optional: prompt_id
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
          title="Add Single AI Mention"
          submitLabel="Save Metric"
          fields={[
            { label: "Platform", options: ["ChatGPT", "Claude", "Gemini", "Perplexity"] },
            { label: "Captured On", type: "date", defaultValue: `${month}-01` },
            { label: "Mentioned?", checkbox: true },
            {
              label: "Prompt ID (optional UUID)",
              placeholder: "e.g. 123e4567-e89b-12d3-a456-426614174000",
            },
          ]}
          onSubmit={handleManualEntry}
        />
      </div>
    </AdminShell>
  );
}

export default AIVisibility;
