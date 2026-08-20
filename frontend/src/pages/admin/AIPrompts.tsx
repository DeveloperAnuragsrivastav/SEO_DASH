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
  inputCls,
  btnGhost
} from '../../components/kit';

interface AIPrompt {
  id: string;
  client_id: string;
  prompt_text: string;
  is_active: boolean;
  added_at: string;
}

const AIPrompts: React.FC = () => {
  const { clientId } = useParams<{ clientId: string }>();
  const [prompts, setPrompts] = useState<AIPrompt[]>([]);
  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [draft, setDraft] = useState('');

  const fetchPrompts = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/ai_prompts`);
      setPrompts(data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to fetch AI Prompts');
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
    fetchPrompts().finally(() => setLoading(false));
  }, [clientId]);

  const addPrompt = async () => {
    const text = draft.trim();
    if (!text) {
      toast.error("Prompt text is required.");
      textareaRef.current?.focus();
      return;
    }
    try {
      await api.post(`/clients/${clientId}/ai_prompts`, { prompt_text: text });
      toast.success("Prompt added to the visibility run.");
      setDraft('');
      fetchPrompts();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'An error occurred while adding prompt');
    }
  };

  const togglePrompt = async (promptId: string, currentStatus: boolean) => {
    try {
      await api.put(`/clients/${clientId}/ai_prompts/${promptId}`, {
        is_active: !currentStatus
      });
      toast.success(`Prompt ${currentStatus ? "deactivated" : "reactivated"}.`);
      fetchPrompts();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update prompt');
    }
  };

  if (loading || !client) return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading AI prompts…" /></div></AdminShell>;

  return (
    <AdminShell
      breadcrumb={`${client.name} / AI Prompts`}
      title="AI Prompts Management"
      subtitle="Prompts replayed against LLMs to measure brand mentions."
      backLink={{ to: "/admin/clients", label: "Back to Clients" }}
      actions={
        <button type="button" className={btnPrimary} onClick={() => textareaRef.current?.focus()}>
          Add AI Prompt
        </button>
      }
    >
      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <TablePanel
            title="Tracked Prompts"
            head={
              <>
                <Th>Prompt Text</Th>
                <Th>Added At</Th>
                <Th>Status</Th>
                <Th align="right">Actions</Th>
              </>
            }
            footer={
              <span className="text-xs text-muted-foreground">
                {prompts.filter((p) => p.is_active).length} active prompts this month
              </span>
            }
          >
            {prompts.length === 0 ? (
               <tr>
                 <td colSpan={4} className="px-6 py-12 text-center text-sm text-muted-foreground">
                   No AI prompts found for this client.
                 </td>
               </tr>
            ) : (
              prompts.map((prompt, i) => (
                <tr key={prompt.id} className="transition-colors hover:bg-secondary">
                  <Td>
                    <span className="mr-3 font-mono text-[11px] text-muted-foreground">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="font-medium">{prompt.prompt_text}</span>
                  </Td>
                  <Td className="font-mono text-xs text-muted-foreground">{new Date(prompt.added_at).toLocaleDateString()}</Td>
                  <Td>
                    <StatusPill status={prompt.is_active ? "Active" : "Paused"} />
                  </Td>
                  <Td align="right">
                    <button
                      type="button"
                      onClick={() => togglePrompt(prompt.id, prompt.is_active)}
                      className={
                        prompt.is_active
                          ? "px-2 py-1 text-[11px] font-medium text-status-churned-text hover:underline"
                          : "px-2 py-1 text-[11px] font-medium text-muted-foreground hover:underline"
                      }
                    >
                      {prompt.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </Td>
                </tr>
              ))
            )}
          </TablePanel>
        </div>

        <div className="lg:col-span-4">
          <Panel title="Add AI Prompt">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-muted-foreground">
                Prompt Text
              </span>
              <textarea
                ref={textareaRef}
                rows={5}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="e.g. best seo agency in new york"
                className={inputCls}
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDraft("")}
                className={btnGhost}
              >
                Cancel
              </button>
              <button type="button" className={btnPrimary} onClick={addPrompt}>
                Add Prompt
              </button>
            </div>
          </Panel>
        </div>
      </div>
    </AdminShell>
  );
};

export default AIPrompts;
