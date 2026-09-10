import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../../api/client';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';
import PaginationBar from '../../components/ui/PaginationBar';

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
  
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);

  const fetchPrompts = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/ai_prompts`, {
        params: { page, page_size: pageSize }
      });
      setPrompts(data.items || []);
      setTotal(data.total || 0);
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
    fetchPrompts().finally(() => setLoading(false));
  }, [clientId, page, pageSize]);


  const togglePrompt = async (promptId: string, currentStatus: boolean) => {
    try {
      await api.put(`/clients/${clientId}/ai_prompts/${promptId}`, {
        is_active: !currentStatus
      });
      toast.success(`Prompt ${currentStatus ? "deactivated" : "reactivated"}.`);
      fetchPrompts();
    } catch (err: any) {
      // Handled by global interceptor
    }
  };

  if (loading && !client) return <PageSkeleton />;

  const exportExcel = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/ai_prompts`, {
        params: { page: 1, page_size: 100000 }
      });
      const ws = XLSX.utils.json_to_sheet(data.items);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "AI Prompts");
      XLSX.writeFile(wb, `AI_Prompts_${clientId}.xlsx`);
    } catch (err) {
      // Handled by global interceptor
    }
  };

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Link to={`/admin/clients/${clientId}`} style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-tertiary)', textDecoration: 'none' }}>← Back to {client?.name}</Link>
      </div>
      <PageHeader 
        title="AI Prompt Management"
        subtitle="Manage prompts used for nightly AI Visibility checks."
        actions={
          <button className="btn btn-secondary" onClick={exportExcel} disabled={prompts.length === 0}>
            Download Excel
          </button>
        }
      />

        <div className="page-card-flush data-panel">
          <div className="data-panel-head">
            <div>
              <h2 className="h2">Tracked Prompts</h2>
              <p className="section-sub">Prompts monitored for brand mentions.</p>
            </div>
          </div>
          <div className="table-wrapper">
          <div className="card-header">
            <h3 className="h2">Tracked Prompts</h3>
            <span className="text-subtle text-xs">
              {prompts.filter(p => p.is_active).length} active prompts
            </span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 34 }}>#</th>
                <th>Prompt Text</th>
                <th className="hide-s">Added At</th>
                <th>Status</th>
                <th className="num">Actions</th>
              </tr>
            </thead>
            <tbody>
              {prompts.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-3)' }}>
                    No AI prompts found for this client.
                  </td>
                </tr>
              ) : (
                prompts.map((prompt, i) => (
                  <tr key={prompt.id}>
                    <td className="mono" style={{ color: 'var(--ink-3)', fontSize: 12 }}>{i + 1}</td>
                    <td className="kwname">{prompt.prompt_text}</td>
                    <td className="hide-s mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                      {new Date(prompt.added_at).toLocaleDateString()}
                    </td>
                    <td>
                      <span className="st" style={{ background: prompt.is_active ? 'var(--up-soft)' : 'var(--neutral-bg)', color: prompt.is_active ? 'var(--up)' : 'var(--ink-3)', borderColor: 'transparent' }}>
                        {prompt.is_active ? 'Active' : 'Paused'}
                      </span>
                    </td>
                    <td className="num">
                      <button
                        className={prompt.is_active ? "btn-danger-ghost" : "btn ghost"}
                        style={{ padding: '4px 8px', fontSize: 11 }}
                        onClick={() => togglePrompt(prompt.id, prompt.is_active)}
                      >
                        {prompt.is_active ? "Pause" : "Resume"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          </div>
        </div>

        <PaginationBar 
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
    </>
  );
};

export default AIPrompts;
