import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { Pencil, Plus, Upload } from 'lucide-react';

import api from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import { AdminShell } from '../components/layout/AdminShell';
import { Panel, TablePanel, Td, Th, btnGhost } from '../components/kit';

interface ActivityEntry {
  id: string;
  month: string;
  activity_type: string;
  count: number;
  notes: string | null;
}

interface ScreenshotEntry {
  id: string;
  month: string;
  keyword_id: string | null;
  file_url: string;
  caption: string | null;
}

interface WorkMonthData {
  activities: ActivityEntry[];
  screenshots: ScreenshotEntry[];
  next_month_plan: { text: string } | null;
}

const WorkDone: React.FC = () => {
  const { clientId, month } = useParams<{ clientId: string, month: string }>();
  const [data, setData] = useState<WorkMonthData | null>(null);
  const [client, setClient] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Plan State
  const [planText, setPlanText] = useState('');
  const [planEditing, setPlanEditing] = useState(false);
  const [planSaving, setPlanSaving] = useState(false);

  const fileRef = useRef<HTMLInputElement>(null);

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
      const res = await api.get(`/clients/${clientId}/work/${month}`);
      setData(res.data);
      if (res.data.next_month_plan && res.data.next_month_plan.text) {
        setPlanText(res.data.next_month_plan.text);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load work done data');
    }
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchClient(), fetchData()]).finally(() => setLoading(false));
  }, [clientId, month]);

  const addActivity = async () => {
    const type = window.prompt("Activity type (e.g. Blogs Published)");
    if (!type?.trim()) return;
    const countStr = window.prompt("How many?", "1");
    const count = Number(countStr ?? 0);
    const notes = window.prompt("Notes (optional)", "Manual entry");

    if (!Number.isFinite(count)) {
      toast.error("Count must be a valid number.");
      return;
    }

    try {
      await api.post(`/clients/${clientId}/work/activities`, {
        month: `${month}-01`,
        activity_type: type.trim(),
        count: count,
        notes: notes || null
      });
      toast.success(`Logged ${type.trim()}.`);
      fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save activity');
    }
  };

  const handleScreenshotUpload = async (files: FileList) => {
    let successCount = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append("file", file);
      formData.append("month", `${month}-01`);
      
      // We don't prompt for caption/keyword per file in bulk upload to keep it simple,
      // but they can be passed if needed. We use the file name as a default caption.
      formData.append("caption", file.name);

      try {
        await api.post(`/clients/${clientId}/work/screenshots`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        successCount++;
      } catch (err: any) {
        toast.error(`Failed to upload ${file.name}: ${err.response?.data?.detail || 'Unknown error'}`);
      }
    }
    
    if (successCount > 0) {
      toast.success(`${successCount} screenshot(s) attached.`);
      fetchData();
    }
  };

  const removeScreenshot = async (id: string) => {
    // Current API doesn't seem to have a delete endpoint explicitly for screenshots based on the code provided,
    // assuming it exists or we just filter locally if not. Wait, backend usually has DELETE.
    try {
      await api.delete(`/clients/${clientId}/work/screenshots/${id}`);
      toast.success("Screenshot removed.");
      fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to remove screenshot. Endpoint might not exist.');
      // Local optimistic update if backend endpoint fails
      if (data) {
        setData({
          ...data,
          screenshots: data.screenshots.filter(s => s.id !== id)
        });
      }
    }
  };

  const handlePlanSave = async () => {
    setPlanSaving(true);
    try {
      await api.put(`/clients/${clientId}/work/${month}/plan`, {
        next_month_plan: { text: planText }
      });
      toast.success('Plan saved successfully');
      setPlanEditing(false);
      fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save plan');
    } finally {
      setPlanSaving(false);
    }
  };

  if (loading || !client || !data) {
    return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading work done…" /></div></AdminShell>;
  }

  // Parse next month plan items by splitting by newline
  const planItems = (data.next_month_plan?.text || "No plan defined yet.")
    .split('\n')
    .filter(line => line.trim().length > 0)
    .map(line => line.replace(/^-\s*/, '').trim());

  return (
    <AdminShell
      breadcrumb={client.name}
      title="Work Done & Execution"
      subtitle={`Activities, proof of execution, and next month's focus. Report month ${month}.`}
    >
      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
        <div className="space-y-8 lg:col-span-7">
          <TablePanel
            title="Activities Completed"
            action={
              <button type="button" className={btnGhost} onClick={addActivity}>
                <Plus className="size-3.5" />
                Add Activity
              </button>
            }
            head={
              <>
                <Th>Activity Type</Th>
                <Th align="right">Count</Th>
                <Th>Notes</Th>
              </>
            }
            footer={
              <span className="text-xs text-muted-foreground">
                {data.activities.reduce((sum, a) => sum + a.count, 0)} tasks logged this month
              </span>
            }
          >
            {data.activities.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-6 py-12 text-center text-sm text-muted-foreground">
                  No activities logged for this month.
                </td>
              </tr>
            ) : (
              data.activities.map((activity) => (
                <tr key={activity.id} className="transition-colors hover:bg-secondary">
                  <Td>
                    <span className="font-medium">{activity.activity_type}</span>
                  </Td>
                  <Td align="right">
                    <span className="font-serif text-lg">{activity.count}</span>
                  </Td>
                  <Td className="text-muted-foreground">{activity.notes || '-'}</Td>
                </tr>
              ))
            )}
          </TablePanel>

          <Panel
            title="Proof of Execution"
            action={
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files.length > 0) {
                      handleScreenshotUpload(e.target.files);
                    }
                    e.target.value = "";
                  }}
                />
                <button
                  type="button"
                  className={`${btnGhost} border-brand`}
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload className="size-3.5" />
                  Upload Screenshot
                </button>
              </>
            }
          >
            {data.screenshots.length === 0 ? (
              <div className="flex h-40 items-center justify-center rounded-md border border-dashed border-border bg-secondary">
                <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                  No screenshots uploaded
                </span>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                {data.screenshots.map((s) => (
                  <div key={s.id} className="group relative overflow-hidden rounded-md border border-border bg-secondary">
                    <div 
                      className="h-32 bg-cover bg-center transition-transform group-hover:scale-105"
                      style={{ backgroundImage: `url(${api.defaults.baseURL?.replace('/api', '') || 'http://localhost:8000'}${s.file_url})` }}
                    />
                    <div className="flex items-center justify-between bg-card px-3 py-2 text-sm border-t border-border">
                      <span className="truncate font-mono text-[10px] text-muted-foreground" title={s.caption || ''}>
                        {s.caption || 'Screenshot'}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeScreenshot(s.id)}
                        className="text-[10px] font-medium text-status-churned-text hover:underline ml-2"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="GSC Performance Spikes">
            <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border bg-secondary">
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
                Awaiting GSC data
              </span>
            </div>
          </Panel>
        </div>

        <div className="lg:col-span-5">
          <div className="relative overflow-hidden rounded-lg bg-ink p-6 text-white shadow-xl shadow-brand/10">
            <div className="absolute right-0 top-0 size-40 rounded-full bg-brand/15 blur-[80px]" />
            
            {planEditing ? (
              <div className="relative z-10 space-y-4">
                <div>
                  <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/40">
                    Next Month Plan
                  </span>
                  <h2 className="mt-2 font-serif text-2xl leading-tight">Editing plan...</h2>
                </div>
                <textarea 
                  value={planText} 
                  onChange={e => setPlanText(e.target.value)} 
                  rows={8}
                  placeholder="Enter next month's focus (each line will be a bullet point)..."
                  className="w-full rounded bg-white/5 border border-white/20 p-3 text-sm text-white/90 placeholder:text-white/30 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand font-mono"
                />
                <div className="flex justify-end gap-3 pt-2">
                  <button 
                    onClick={() => { setPlanEditing(false); setPlanText(data.next_month_plan?.text || ''); }}
                    className="rounded border border-white/20 px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/10"
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={handlePlanSave} 
                    disabled={planSaving}
                    className="rounded bg-brand px-3 py-1.5 text-xs font-medium text-ink hover:bg-brand/90"
                  >
                    {planSaving ? 'Saving...' : 'Save Plan'}
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="relative z-10 flex items-start justify-between gap-4">
                  <div>
                    <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-white/40">
                      Next Month Plan
                    </span>
                    <h2 className="mt-2 font-serif text-2xl leading-tight">Upcoming focus</h2>
                  </div>
                  <button
                    type="button"
                    onClick={() => setPlanEditing(true)}
                    className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1.5 text-xs font-medium text-white/80 transition-colors hover:bg-white/10"
                  >
                    <Pencil className="size-3" />
                    Edit Plan
                  </button>
                </div>
                <ol className="relative z-10 mt-6 space-y-4">
                  {planItems.map((item, i) => (
                    <li key={i} className="flex gap-4 border-t border-white/10 pt-4">
                      <span className="font-mono text-[11px] text-brand">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="text-sm text-white/75">{item}</span>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </div>
        </div>
      </div>
    </AdminShell>
  );
}

export default WorkDone;
