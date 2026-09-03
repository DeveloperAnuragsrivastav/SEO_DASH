import re

content = """
import React, { useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import api from '../../api/client';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';

// --- Manual Entry Forms ---

const GBPManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => {
  const [form, setForm] = useState({
    captured_on: '', impressions_desktop_maps: 0, impressions_desktop_search: 0,
    impressions_mobile_maps: 0, impressions_mobile_search: 0, calls: 0,
    direction_requests: 0, website_clicks: 0, bookings: 0
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post(`/clients/${clientId}/manual-gbp`, { records: [form] });
      toast.success('GBP Record added successfully');
      onComplete();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to add record');
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
      <div className="form-group" style={{ gridColumn: '1 / -1' }}><label className="form-label">Date</label><input type="date" className="form-input" required value={form.captured_on} onChange={e => setForm({...form, captured_on: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">Desk Maps</label><input type="number" className="form-input" required value={form.impressions_desktop_maps} onChange={e => setForm({...form, impressions_desktop_maps: parseInt(e.target.value) || 0})} /></div>
      <div className="form-group"><label className="form-label">Desk Search</label><input type="number" className="form-input" required value={form.impressions_desktop_search} onChange={e => setForm({...form, impressions_desktop_search: parseInt(e.target.value) || 0})} /></div>
      <div className="form-group"><label className="form-label">Mob Maps</label><input type="number" className="form-input" required value={form.impressions_mobile_maps} onChange={e => setForm({...form, impressions_mobile_maps: parseInt(e.target.value) || 0})} /></div>
      <div className="form-group"><label className="form-label">Mob Search</label><input type="number" className="form-input" required value={form.impressions_mobile_search} onChange={e => setForm({...form, impressions_mobile_search: parseInt(e.target.value) || 0})} /></div>
      <div className="form-group"><label className="form-label">Calls</label><input type="number" className="form-input" required value={form.calls} onChange={e => setForm({...form, calls: parseInt(e.target.value) || 0})} /></div>
      <div className="form-group"><label className="form-label">Directions</label><input type="number" className="form-input" required value={form.direction_requests} onChange={e => setForm({...form, direction_requests: parseInt(e.target.value) || 0})} /></div>
      <div className="form-group"><label className="form-label">Clicks</label><input type="number" className="form-input" required value={form.website_clicks} onChange={e => setForm({...form, website_clicks: parseInt(e.target.value) || 0})} /></div>
      <div className="form-group"><label className="form-label">Bookings</label><input type="number" className="form-input" required value={form.bookings} onChange={e => setForm({...form, bookings: parseInt(e.target.value) || 0})} /></div>
      <div style={{ gridColumn: '1 / -1', marginTop: '8px' }}><button type="submit" className="btn btn-primary" style={{width: '100%'}}>Save Record</button></div>
    </form>
  );
};

const AIMentionsManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => {
  const [form, setForm] = useState({ captured_on: '', platform: 'chatgpt', prompt: '', mentioned: false, cited_pages: '' });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const citedPagesArr = form.cited_pages ? form.cited_pages.split(',').map(u => ({ url: u.trim() })) : [];
      await api.post(`/clients/${clientId}/ai_mentions/bulk`, [{
        captured_on: form.captured_on, platform: form.platform, prompt_id: null, mentioned: form.mentioned, cited_pages: citedPagesArr
      }]);
      toast.success('AI Mention added successfully');
      onComplete();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to add record');
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Date</label><input type="date" className="form-input" required value={form.captured_on} onChange={e => setForm({...form, captured_on: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">Platform</label><select className="form-input" value={form.platform} onChange={e => setForm({...form, platform: e.target.value})}><option value="chatgpt">ChatGPT</option><option value="claude">Claude</option><option value="gemini">Gemini</option><option value="perplexity">Perplexity</option><option value="grok">Grok</option></select></div>
      <div className="form-group"><label className="form-label">Prompt</label><input type="text" className="form-input" required placeholder="e.g. best seo tools" value={form.prompt} onChange={e => setForm({...form, prompt: e.target.value})} /></div>
      <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><input type="checkbox" id="mentioned" checked={form.mentioned} onChange={e => setForm({...form, mentioned: e.target.checked})} /><label htmlFor="mentioned" className="form-label" style={{margin:0}}>Brand Mentioned?</label></div>
      <div className="form-group"><label className="form-label">Cited Pages (Comma separated URLs)</label><input type="text" className="form-input" placeholder="https://..., https://..." value={form.cited_pages} onChange={e => setForm({...form, cited_pages: e.target.value})} /></div>
      <button type="submit" className="btn btn-primary" style={{marginTop: '8px', width: '100%'}}>Save Record</button>
    </form>
  );
};

const LinksManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => {
  const [form, setForm] = useState({ created_on: '', domain: '', url: '', activity_type: '', dr: '' });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post(`/clients/${clientId}/links`, { ...form, dr: form.dr ? parseInt(form.dr) : null, status: 'active' });
      toast.success('Link added successfully');
      onComplete();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to add link');
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Date</label><input type="date" className="form-input" required value={form.created_on} onChange={e => setForm({...form, created_on: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">URL</label><input type="url" className="form-input" required placeholder="https://example.com" value={form.url} onChange={e => setForm({...form, url: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">Domain</label><input type="text" className="form-input" required placeholder="example.com" value={form.domain} onChange={e => setForm({...form, domain: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">Activity Type</label><input type="text" className="form-input" required placeholder="Guest Post" value={form.activity_type} onChange={e => setForm({...form, activity_type: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">Domain Rating (DR)</label><input type="number" className="form-input" value={form.dr} onChange={e => setForm({...form, dr: e.target.value})} /></div>
      <button type="submit" className="btn btn-primary" style={{marginTop: '8px', width: '100%'}}>Save Link</button>
    </form>
  );
};

const WorkManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => {
  const [form, setForm] = useState({ month: '', activity_type: '', count: 1, notes: '' });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post(`/clients/${clientId}/work/activities`, form);
      toast.success('Activity added successfully');
      onComplete();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to add activity');
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Date (Month mapping)</label><input type="date" className="form-input" required value={form.month} onChange={e => setForm({...form, month: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">Activity Type</label><input type="text" className="form-input" required placeholder="Content Optimization" value={form.activity_type} onChange={e => setForm({...form, activity_type: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">Count</label><input type="number" className="form-input" required value={form.count} onChange={e => setForm({...form, count: parseInt(e.target.value) || 1})} /></div>
      <div className="form-group"><label className="form-label">Notes (Optional)</label><input type="text" className="form-input" value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} /></div>
      <button type="submit" className="btn btn-primary" style={{marginTop: '8px', width: '100%'}}>Save Activity</button>
    </form>
  );
};

const KeywordsManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => {
  const [form, setForm] = useState({ term: '', group_tag: '', target_url: '', fetch_metrics: true });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post(`/clients/${clientId}/keywords`, form);
      toast.success('Keyword added successfully');
      onComplete();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to add keyword');
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Keyword Term</label><input type="text" className="form-input" required placeholder="plumber near me" value={form.term} onChange={e => setForm({...form, term: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">Group Tag (Optional)</label><input type="text" className="form-input" placeholder="emergency services" value={form.group_tag} onChange={e => setForm({...form, group_tag: e.target.value})} /></div>
      <div className="form-group"><label className="form-label">Target URL (Optional)</label><input type="text" className="form-input" placeholder="https://example.com/plumbing" value={form.target_url} onChange={e => setForm({...form, target_url: e.target.value})} /></div>
      <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><input type="checkbox" id="fetch_metrics" checked={form.fetch_metrics} onChange={e => setForm({...form, fetch_metrics: e.target.checked})} /><label htmlFor="fetch_metrics" className="form-label" style={{margin:0}}>Fetch Search Volume</label></div>
      <button type="submit" className="btn btn-primary" style={{marginTop: '8px', width: '100%'}}>Save Keyword</button>
    </form>
  );
};

const AIPromptsManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => {
  const [prompt_text, setPromptText] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post(`/clients/${clientId}/ai_prompts`, { prompt_text });
      toast.success('Prompt added successfully');
      onComplete();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to add prompt');
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Prompt Text</label><textarea className="form-input" rows={4} required placeholder="best seo agency in new york" value={prompt_text} onChange={e => setPromptText(e.target.value)} /></div>
      <button type="submit" className="btn btn-primary" style={{marginTop: '8px', width: '100%'}}>Save Prompt</button>
    </form>
  );
};

// --- Main Components ---

interface UploaderProps {
  title: string;
  endpoint?: string;
  templateColumns?: string;
  manualForm: React.ReactNode;
}

const IngestionCard: React.FC<UploaderProps> = ({ title, endpoint, templateColumns, manualForm }) => {
  const [modalOpen, setModalOpen] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [showManual, setShowManual] = useState(false);
  
  const [file, setFile] = useState<File | null>(null);
  const [displayFileName, setDisplayFileName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processFile = async (f: File) => {
    if (f.name.endsWith('.xlsx')) {
      try {
        const data = await f.arrayBuffer();
        const wb = XLSX.read(data);
        const ws = wb.Sheets[wb.SheetNames[0]];
        const csvStr = XLSX.utils.sheet_to_csv(ws, { raw: false, dateNF: "yyyy-mm-dd" });
        const blob = new Blob([csvStr], { type: 'text/csv' });
        const csvFile = new File([blob], f.name.replace('.xlsx', '.csv'), { type: 'text/csv' });
        setFile(csvFile);
        setDisplayFileName(f.name);
      } catch (err) {
        toast.error('Failed to parse Excel file');
      }
    } else {
      setFile(f);
      setDisplayFileName(f.name);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFile(e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file || !endpoint) return;
    setUploading(true);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await api.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success(`${title}: Successfully processed ${res.data.rows_processed} rows.`);
      if (res.data.errors && res.data.errors.length > 0) {
        toast.error(`Row ${res.data.errors[0].row}: ${res.data.errors[0].error}`);
      }
      setFile(null);
      setDisplayFileName('');
      setModalOpen(false);
      setShowUploader(false);
      setShowManual(false);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    }
    setUploading(false);
  };

  const downloadTemplate = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!templateColumns) return;
    const blob = new Blob([templateColumns], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.toLowerCase().replace(/ /g, '_')}_template.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };
  
  const closeModal = () => {
      setModalOpen(false);
      setShowUploader(false);
      setShowManual(false);
  };

  return (
    <>
      <div className="card" style={{ cursor: 'pointer', transition: 'all 0.15s ease' }} onClick={() => setModalOpen(true)}>
        <div className="card-header">
          <h3 className="h2">{title}</h3>
          {templateColumns && (
              <button className="btn btn-secondary" style={{ fontSize: '12px', padding: '4px 8px' }} onClick={downloadTemplate}>
                Template
              </button>
          )}
        </div>
        <div className="card-body" style={{ textAlign: 'center', padding: '32px 24px' }}>
          <div style={{ fontSize: '24px', marginBottom: '12px', color: 'var(--brand-accent)' }}>📥</div>
          <div style={{ fontWeight: 500 }}>Click to inject data</div>
          <div className="text-subtle text-xs" style={{ marginTop: '4px' }}>
              {endpoint ? "Supports Excel (.xlsx), CSV, and manual entry" : "Supports manual entry"}
          </div>
        </div>
      </div>

      {modalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="card" style={{ width: '450px', margin: 0, maxHeight: '90vh', overflowY: 'auto' }}>
            <div className="card-header" style={{position:'sticky', top:0, background:'white', zIndex: 10}}>
              <h3 className="h2">{showManual ? `Add ${title}` : `Inject ${title}`}</h3>
              <button className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: '12px' }} onClick={closeModal}>Close</button>
            </div>
            <div className="card-body">
              {!showUploader && !showManual ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {endpoint && (
                      <button className="btn btn-primary" style={{ width: '100%', padding: '12px' }} onClick={() => setShowUploader(true)}>
                        Upload Sheet (Excel/CSV)
                      </button>
                  )}
                  <button className="btn btn-secondary" style={{ width: '100%', padding: '12px' }} onClick={() => setShowManual(true)}>
                    Manual Entry (One-by-one)
                  </button>
                </div>
              ) : showManual ? (
                  <div>
                      {manualForm}
                      <button className="btn btn-secondary" style={{ width: '100%', marginTop: '8px' }} onClick={() => setShowManual(false)}>Back</button>
                  </div>
              ) : (
                <div>
                  <div 
                    className={`dropzone ${isDragging ? 'dragging' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    style={{
                      border: `2px dashed ${isDragging ? 'var(--brand-primary)' : 'var(--border)'}`,
                      backgroundColor: isDragging ? 'rgba(99, 102, 241, 0.05)' : 'transparent',
                      padding: '32px',
                      textAlign: 'center',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div className="dropzone-icon" style={{ fontSize: '24px', marginBottom: '8px' }}>📄</div>
                    <div className="dropzone-text" style={{ fontWeight: 500 }}>
                      {displayFileName || 'Click to select Excel/CSV file'}
                    </div>
                    <div className="dropzone-subtext" style={{ color: 'var(--text-subtle)', fontSize: '12px', marginTop: '4px' }}>
                      {file ? `${(file.size / 1024).toFixed(1)} KB` : 'or drag and drop here'}
                    </div>
                    <input type="file" accept=".csv,.xlsx" ref={fileInputRef} onChange={handleFileChange} style={{ display: 'none' }} />
                  </div>
                  
                  {file && (
                    <button className="btn btn-primary" style={{ width: '100%', marginTop: '16px' }} onClick={handleUpload} disabled={uploading}>
                      {uploading ? 'Uploading...' : `Upload Data`}
                    </button>
                  )}
                  <button className="btn btn-secondary" style={{ width: '100%', marginTop: '8px' }} onClick={() => setShowUploader(false)}>
                    Back
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

const ManualEntryHub: React.FC = () => {
  const { clientId } = useParams();
  
  if (!clientId) return null;

  return (
    <>
      <div style={{ marginBottom: '32px' }}>
        <h1 className="h1">Data Ingestion Hub</h1>
        <p className="text-subtle" style={{ marginTop: '4px' }}>Central hub to inject data (Upload or Manual) into the system.</p>
      </div>

      <div className="grid-cols-2">
        <IngestionCard 
          title="GBP Metrics" 
          endpoint={`/clients/${clientId}/manual-gbp/upload_csv`}
          templateColumns="date,impressions_desktop_maps,impressions_desktop_search,impressions_mobile_maps,impressions_mobile_search,calls,direction_requests,website_clicks,bookings\n2026-08-01,100,50,300,150,5,2,10,1"
          manualForm={<GBPManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />
        <IngestionCard 
          title="AI Mentions Data" 
          endpoint={`/clients/${clientId}/ai_mentions/upload_csv`}
          templateColumns="date,platform,prompt,mentioned,cited_pages\n2026-08-01,chatgpt,best pizza in NY,true,https://example.com/pizza"
          manualForm={<AIMentionsManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />
        <IngestionCard 
          title="Backlinks" 
          endpoint={`/clients/${clientId}/links/upload_csv`}
          templateColumns="date,url,domain,activity_type,dr\n2026-08-01,https://target.com/page,target.com,Guest Post,45"
          manualForm={<LinksManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />
        <IngestionCard 
          title="Work Activity" 
          endpoint={`/clients/${clientId}/work/upload_csv`}
          templateColumns="date,activity_type,count,notes\n2026-08-01,Optimized Homepage,1,Updated meta titles"
          manualForm={<WorkManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />
        <IngestionCard 
          title="Keywords"
          manualForm={<KeywordsManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />
        <IngestionCard 
          title="AI Prompts"
          manualForm={<AIPromptsManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />
      </div>
    </>
  );
};

export default ManualEntryHub;
"""
with open('frontend/src/pages/admin/ManualEntryHub.tsx', 'w') as f:
    f.write(content)
