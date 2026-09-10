import React, { useState, useRef, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api, { API_BASE_URL } from '../../api/client';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';
import PageHeader from '../../components/ui/PageHeader';
import ManualGSCUI from '../../components/ManualGSCUI';
import ManualGA4UI from '../../components/ManualGA4UI';
import { FileSpreadsheet, X, Check, Download, Database, ChevronRight,
         MapPin, Link as LinkIcon, CheckSquare, Crosshair, Bot, Image as ImageIcon,
         Search, BarChart2, MoreVertical, Pencil, HelpCircle } from 'lucide-react';

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
      // Handled by global interceptor
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
      <div className="form-group" style={{ gridColumn: '1 / -1' }}><label className="form-label">Date</label><input type="date" max={new Date().toISOString().split('T')[0]} className="form-input" required value={form.captured_on} onChange={e => setForm({ ...form, captured_on: e.target.value })} /></div>
      <div className="form-group"><label className="form-label">Desk Maps</label><input type="number" className="form-input" required value={form.impressions_desktop_maps} onChange={e => setForm({ ...form, impressions_desktop_maps: parseInt(e.target.value) || 0 })} /></div>
      <div className="form-group"><label className="form-label">Desk Search</label><input type="number" className="form-input" required value={form.impressions_desktop_search} onChange={e => setForm({ ...form, impressions_desktop_search: parseInt(e.target.value) || 0 })} /></div>
      <div className="form-group"><label className="form-label">Mob Maps</label><input type="number" className="form-input" required value={form.impressions_mobile_maps} onChange={e => setForm({ ...form, impressions_mobile_maps: parseInt(e.target.value) || 0 })} /></div>
      <div className="form-group"><label className="form-label">Mob Search</label><input type="number" className="form-input" required value={form.impressions_mobile_search} onChange={e => setForm({ ...form, impressions_mobile_search: parseInt(e.target.value) || 0 })} /></div>
      <div className="form-group"><label className="form-label">Calls</label><input type="number" className="form-input" required value={form.calls} onChange={e => setForm({ ...form, calls: parseInt(e.target.value) || 0 })} /></div>
      <div className="form-group"><label className="form-label">Directions</label><input type="number" className="form-input" required value={form.direction_requests} onChange={e => setForm({ ...form, direction_requests: parseInt(e.target.value) || 0 })} /></div>
      <div className="form-group"><label className="form-label">Clicks</label><input type="number" className="form-input" required value={form.website_clicks} onChange={e => setForm({ ...form, website_clicks: parseInt(e.target.value) || 0 })} /></div>
      <div className="form-group"><label className="form-label">Bookings</label><input type="number" className="form-input" required value={form.bookings} onChange={e => setForm({ ...form, bookings: parseInt(e.target.value) || 0 })} /></div>
      <div style={{ gridColumn: '1 / -1', marginTop: '8px' }}><button type="submit" className="btn btn-primary" style={{ width: '100%' }}>Save Record</button></div>
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
      // Handled by global interceptor
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Date</label><input type="date" max={new Date().toISOString().split('T')[0]} className="form-input" required value={form.created_on} onChange={e => setForm({ ...form, created_on: e.target.value })} /></div>
      <div className="form-group"><label className="form-label">URL</label><input type="url" className="form-input" required placeholder="https://example.com" value={form.url} onChange={e => setForm({ ...form, url: e.target.value })} /></div>
      <div className="form-group"><label className="form-label">Domain</label><input type="text" className="form-input" required placeholder="example.com" value={form.domain} onChange={e => setForm({ ...form, domain: e.target.value })} /></div>
      <div className="form-group"><label className="form-label">Activity Type</label><input type="text" className="form-input" required placeholder="Guest Post" value={form.activity_type} onChange={e => setForm({ ...form, activity_type: e.target.value })} /></div>
      <div className="form-group"><label className="form-label">Domain Rating (DR)</label><input type="number" className="form-input" value={form.dr} onChange={e => setForm({ ...form, dr: e.target.value })} /></div>
      <button type="submit" className="btn btn-primary" style={{ marginTop: '8px', width: '100%' }}>Save Link</button>
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
      // Handled by global interceptor
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Date (Month mapping)</label><input type="date" max={new Date().toISOString().split('T')[0]} className="form-input" required value={form.month} onChange={e => setForm({ ...form, month: e.target.value })} /></div>
      <div className="form-group"><label className="form-label">Activity Type</label><input type="text" className="form-input" required placeholder="Content Optimization" value={form.activity_type} onChange={e => setForm({ ...form, activity_type: e.target.value })} /></div>
      <div className="form-group"><label className="form-label">Count</label><input type="number" className="form-input" required value={form.count} onChange={e => setForm({ ...form, count: parseInt(e.target.value) || 1 })} /></div>
      <div className="form-group"><label className="form-label">Notes (Optional)</label><input type="text" className="form-input" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} /></div>
      <button type="submit" className="btn btn-primary" style={{ marginTop: '8px', width: '100%' }}>Save Activity</button>
    </form>
  );
};

const KeywordsManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => {
  const [form, setForm] = useState({ term: '', group_tag: '', target_url: '', fetch_metrics: true });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        term: form.term,
        group_tag: form.group_tag || null,
        target_url: form.target_url || null,
        fetch_metrics: form.fetch_metrics
      };
      await api.post(`/clients/${clientId}/keywords`, payload);
      toast.success('Keyword added successfully');
      onComplete();
    } catch (err: any) {
      // Handled by global interceptor
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Keyword Term</label><input type="text" className="form-input" required placeholder="plumber near me" value={form.term} onChange={e => setForm({ ...form, term: e.target.value })} /></div>
      <div className="form-group"><label className="form-label">Group Tag (Optional)</label><input type="text" className="form-input" placeholder="emergency services" value={form.group_tag} onChange={e => setForm({ ...form, group_tag: e.target.value })} /></div>
      <div className="form-group"><label className="form-label">Target URL (Optional)</label><input type="text" className="form-input" placeholder="https://example.com/plumbing" value={form.target_url} onChange={e => setForm({ ...form, target_url: e.target.value })} /></div>

      <button type="submit" className="btn btn-primary" style={{ marginTop: '8px', width: '100%' }}>Save Keyword</button>
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
      // Handled by global interceptor
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px' }}>
      <div className="form-group"><label className="form-label">Prompt Text</label><textarea className="form-input" rows={4} required placeholder="best seo agency in new york" value={prompt_text} onChange={e => setPromptText(e.target.value)} /></div>
      <button type="submit" className="btn btn-primary" style={{ marginTop: '8px', width: '100%' }}>Save Prompt</button>
    </form>
  );
};


const ScreenshotsManualForm = ({ clientId }: { clientId: string }) => {
  const [month, setMonth] = useState('');
  const [files, setFiles] = useState<{ file: File, caption: string }[]>([]);
  const [uploading, setUploading] = useState(false);
  const [recent, setRecent] = useState<any[]>([]);

  useEffect(() => {
    api.get(`/clients/${clientId}/screenshots`).then(res => {
      setRecent(res.data);
    }).catch(() => { });
  }, [clientId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (files.length === 0) {
      toast.error('Please select at least one image file');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('month', month);
    for (const f of files) {
      formData.append('files', f.file);
      formData.append('captions', f.caption);
    }

    try {
      await api.post(`/clients/${clientId}/screenshots/bulk`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Screenshots uploaded successfully');
      const res = await api.get(`/clients/${clientId}/screenshots`);
      setRecent(res.data);
      setFiles([]);
      setMonth('');
    } catch (err: any) {
      // Handled by global interceptor
    }
    setUploading(false);
  };

  return (
    <div>
      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '12px', marginBottom: '24px' }}>
        <div className="form-group"><label className="form-label">Report Month</label><input type="date" max={new Date().toISOString().split('T')[0]} className="form-input" required value={month} onChange={e => setMonth(e.target.value)} /></div>
        <div className="form-group">
          <label className="form-label">Image Files</label>
          <input type="file" className="form-input" accept="image/*" multiple onChange={e => {
            const newFiles = Array.from(e.target.files || []).map(f => ({ file: f, caption: '' }));
            setFiles(prev => [...prev, ...newFiles]);
          }} />
        </div>

        {files.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
            <label className="form-label">File Captions (Optional)</label>
            {files.map((f, i) => (
              <div key={i} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <div style={{ flex: '1', fontSize: '12px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', background: 'var(--neutral-bg)', padding: '8px', borderRadius: '4px' }}>
                  {f.file.name}
                </div>
                <input type="text" className="form-input" style={{ flex: '2', padding: '6px 12px' }} placeholder="Caption" value={f.caption} onChange={e => {
                  const newF = [...files];
                  newF[i].caption = e.target.value;
                  setFiles(newF);
                }} />
                <button type="button" className="btn btn-secondary btn-sm" style={{ padding: '6px 10px' }} onClick={() => {
                  const newF = [...files];
                  newF.splice(i, 1);
                  setFiles(newF);
                }}>✕</button>
              </div>
            ))}
          </div>
        )}

        <button type="submit" className="btn btn-primary" style={{ marginTop: '12px', width: '100%' }} disabled={uploading || files.length === 0}>
          {uploading ? 'Uploading...' : 'Upload Screenshots'}
        </button>
      </form>

      {recent.length > 0 && (
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <h4 style={{ fontSize: '13px', marginBottom: '12px' }}>Recently Uploaded</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {recent.map((r, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px', background: 'var(--neutral-bg)', borderRadius: '6px' }}>
                {r.file_url && (
                  <img src={`${API_BASE_URL}${r.file_url}`} alt="proof" style={{ width: '40px', height: '40px', objectFit: 'cover', borderRadius: '4px' }} />
                )}
                <div style={{ fontSize: '12px' }}>
                  <div style={{ fontWeight: 500 }}>{r.month}</div>
                  <div style={{ color: 'var(--ink-3)' }}>{r.caption || 'No caption'}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// --- Main Components ---


/**
 * ManualGSCUI / ManualGA4UI are month-scoped, so wrap them with a month
 * picker to match the { clientId, onComplete } shape the other forms use.
 */
const MonthScopedForm: React.FC<{
  clientId: string;
  onComplete: () => void;
  render: (clientId: string, monthStr: string, onSuccess: () => void) => React.ReactNode;
}> = ({ clientId, onComplete, render }) => {
  const [monthStr, setMonthStr] = useState(() => new Date().toISOString().slice(0, 7));

  return (
    <div>
      <div className="form-group">
        <label className="form-label">Data Month</label>
        <input
          type="month"
          className="form-input"
          value={monthStr}
          onChange={e => setMonthStr(e.target.value)}
          required
        />
      </div>
      {monthStr ? render(clientId, monthStr, onComplete) : null}
    </div>
  );
};

const GSCManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => (
  <MonthScopedForm
    clientId={clientId}
    onComplete={onComplete}
    render={(cid, m, ok) => <ManualGSCUI clientId={cid} monthStr={m} onSuccess={ok} />}
  />
);

const GA4ManualForm = ({ clientId, onComplete }: { clientId: string, onComplete: () => void }) => (
  <MonthScopedForm
    clientId={clientId}
    onComplete={onComplete}
    render={(cid, m, ok) => <ManualGA4UI clientId={cid} monthStr={m} onSuccess={ok} />}
  />
);

interface SectionStatus {
  loading: boolean;
  total: number;
  latest: string | null;
}

interface UploaderProps {
  title: string;
  endpoint?: string;
  templateColumns?: string;
  manualForm: React.ReactNode;
  requiresMonth?: boolean;
  icon?: React.ReactNode;
  hint?: string;
  tone?: string;
  status?: SectionStatus;
}

const IngestionCard: React.FC<UploaderProps> = ({ title, endpoint, templateColumns, manualForm, requiresMonth, icon, hint, tone, status }) => {
  const [modalOpen, setModalOpen] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [showManual, setShowManual] = useState(false);

  const [file, setFile] = useState<File | null>(null);
  const [uploadMonth, setUploadMonth] = useState('');
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
        const csvStr = XLSX.utils.sheet_to_csv(ws, { dateNF: "yyyy-mm-dd" });
        const blob = new Blob([csvStr], { type: 'text/csv' });
        const csvFile = new File([blob], f.name.replace('.xlsx', '.csv'), { type: 'text/csv' });
        setFile(csvFile);
        setDisplayFileName(f.name);
      } catch (err) {
        // Handled by global interceptor
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
    if (requiresMonth && !uploadMonth) {
      toast.error('Please select a month for this upload.');
      return;
    }
    setUploading(true);

    const formData = new FormData();
    formData.append('file', file);
    if (requiresMonth) {
      formData.append('month', uploadMonth);
    }

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
      // Handled by global interceptor
    }
    setUploading(false);
  };

  const downloadTemplate = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!templateColumns) return;

    const rows = templateColumns.split('\n').map(row => row.split(','));
    const ws = XLSX.utils.aoa_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Template");
    XLSX.writeFile(wb, `${title.toLowerCase().replace(/ /g, '_')}_template.xlsx`);
  };

  const closeModal = () => {
    setModalOpen(false);
    setShowUploader(false);
    setShowManual(false);
  };

  return (
    <>
      <div
        className={`ingest-row ${status && !status.loading && status.total > 0 ? 'done' : ''}`}
        onClick={() => setModalOpen(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setModalOpen(true); } }}
      >
        <span className="ingest-state">
          {status?.loading
            ? <span className="checklist-spin" />
            : status && status.total > 0
              ? <Check size={13} />
              : null}
        </span>

        <span className={`stat-chip sm tone-${tone || 'blue'}`}>{icon}</span>

        <span className="ingest-main">
          <span className="ingest-title">
            {title}
            {!status?.loading && (
              <span className={`badge ${status && status.total > 0 ? 'badge-success' : 'badge-warning'}`}>
                {status && status.total > 0 ? 'Completed' : 'Pending'}
              </span>
            )}
          </span>
          <span className="ingest-desc">{hint}</span>
        </span>

        <span className="ingest-count">
          <Database size={13} />
          <span>
            <b>
              {status?.loading
                ? 'Checking…'
                : status && status.total > 0
                  ? `${status.total.toLocaleString()} ${status.total === 1 ? 'record' : 'records'}`
                  : 'No data added yet'}
            </b>
            <small>{status?.latest ? `Last updated ${status.latest}` : '—'}</small>
          </span>
        </span>

        <span className="ingest-actions" onClick={e => e.stopPropagation()}>
          {templateColumns && (
            <button className="btn btn-secondary btn-sm hide-s" onClick={downloadTemplate}>
              <Download size={13} /> Download Template
            </button>
          )}
          <button
            className={`btn btn-sm ${status && !status.loading && status.total > 0 ? 'btn-secondary' : 'btn-primary'}`}
            onClick={() => setModalOpen(true)}
          >
            {status && !status.loading && status.total > 0
              ? <><Pencil size={13} /> Update</>
              : <><Download size={13} /> Add Data</>}
          </button>
          <span className="ingest-more" aria-hidden="true"><MoreVertical size={15} /></span>
        </span>
      </div>

      {modalOpen && (
        <div className="overlay">
          <div className="card" style={{ width: '450px', margin: 0, maxHeight: '90vh', overflowY: 'auto' }}>
            <div className="card-header" style={{ position: 'sticky', top: 0, background: 'var(--card)', zIndex: 10 }}>
              <h3 className="h2">{showManual ? `Add ${title}` : `Inject ${title}`}</h3>
              <button className="icon-btn" onClick={closeModal} aria-label="Close"><X size={17} /></button>
            </div>
            <div className="card-body">
              {!showUploader && !showManual ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {endpoint && (
                    <button className="btn btn-primary" style={{ width: '100%', padding: '12px' }} onClick={() => setShowUploader(true)}>
                      Upload Sheet (Excel)
                    </button>
                  )}
                  <button className="btn btn-secondary" style={{ width: '100%', padding: '12px' }} onClick={() => setShowManual(true)}>
                    Select Mutiple Images At once
                  </button>
                </div>
              ) : showManual ? (
                <div>
                  {manualForm}
                  <button className="btn btn-secondary" style={{ width: '100%', marginTop: '8px' }} onClick={() => setShowManual(false)}>Back</button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {requiresMonth && (
                    <div className="form-group">
                      <label className="form-label">Data Month</label>
                      <input
                        type="month"
                        className="form-input"
                        value={uploadMonth}
                        onChange={e => setUploadMonth(e.target.value)}
                        required
                      />
                    </div>
                  )}
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
                    <div className="dropzone-icon"><FileSpreadsheet size={22} /></div>
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

const BASE_KEYS = ['keywords', 'links', 'work', 'gbp', 'ai', 'screenshots'] as const;
/** Only listed when the client is set to hand-enter that traffic source. */
const TRAFFIC_KEYS = ['gsc', 'ga4'] as const;
const SECTION_KEYS = [...BASE_KEYS, ...TRAFFIC_KEYS] as const;
type SectionKey = typeof SECTION_KEYS[number];

/** Read-only presence check per data set — drives the checklist ticks. */
const STATUS_PATHS: Record<SectionKey, string> = {
  gbp: 'manual-gbp',
  links: 'links',
  work: 'work',
  keywords: 'keywords/history',
  ai: 'ai_mentions',
  screenshots: 'screenshots',
  gsc: 'search/history',
  ga4: 'audience/history',
};

const DATE_FIELDS = ['captured_on', 'created_on', 'month', 'date'];

/** Newest date visible in the returned page, formatted for display. */
function latestDate(items: any[]): string | null {
  let best: number | null = null;
  for (const it of items || []) {
    for (const f of DATE_FIELDS) {
      const raw = it?.[f];
      if (!raw) continue;
      const t = new Date(raw).getTime();
      if (!Number.isNaN(t) && (best === null || t > best)) best = t;
      break;
    }
  }
  if (best === null) return null;
  return new Date(best).toLocaleDateString('default', { day: 'numeric', month: 'short', year: 'numeric' });
}

const ManualEntryHub: React.FC = () => {
  const { clientId } = useParams();

  const [statuses, setStatuses] = useState<Record<SectionKey, SectionStatus>>(() =>
    Object.fromEntries(SECTION_KEYS.map(k => [k, { loading: true, total: 0, latest: null }])) as Record<SectionKey, SectionStatus>
  );

  // Which traffic sources this client hand-enters (null = still loading).
  const [manualTraffic, setManualTraffic] = useState<Record<'gsc' | 'ga4', boolean> | null>(null);

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;

    api.get(`/clients/${clientId}/sections`, { skipErrorToast: true } as any)
      .then((res) => {
        if (cancelled) return;
        const on = (k: string) => (res.data || []).some((r: any) => r.section_key === k && r.enabled);
        setManualTraffic({ gsc: on('gsc_manual'), ga4: on('ga4_manual') });
      })
      .catch(() => { if (!cancelled) setManualTraffic({ gsc: false, ga4: false }); });

    SECTION_KEYS.forEach((key) => {
      api.get(`/clients/${clientId}/${STATUS_PATHS[key]}`, { skipErrorToast: true } as any)
        .then((res) => {
          if (cancelled) return;
          const items = res.data?.items || [];
          setStatuses(prev => ({
            ...prev,
            [key]: { loading: false, total: res.data?.total ?? items.length, latest: latestDate(items) },
          }));
        })
        .catch(() => {
          // A missing/empty data set is a normal state here, not an error worth shouting about.
          if (cancelled) return;
          setStatuses(prev => ({ ...prev, [key]: { loading: false, total: 0, latest: null } }));
        });
    });

    return () => { cancelled = true; };
  }, [clientId]);

  if (!clientId) return null;

  const activeKeys: SectionKey[] = [
    ...BASE_KEYS,
    ...TRAFFIC_KEYS.filter(k => manualTraffic?.[k]),
  ];

  const checked = activeKeys.filter(k => !statuses[k].loading && statuses[k].total > 0).length;
  const stillLoading = manualTraffic === null || activeKeys.some(k => statuses[k].loading);
  const total = activeKeys.length;
  const pct = Math.round((checked / total) * 100);
  const thisMonth = new Date().toLocaleString('default', { month: 'long', year: 'numeric' });

  const STEP_COPY: Record<SectionKey, { label: string; hint: string }> = {
    keywords: { label: 'Add Keyword Performance', hint: 'Rankings for the keywords you track' },
    links: { label: 'Add Backlinks', hint: 'Links built for this client' },
    work: { label: 'Add On-Site SEO Activities', hint: 'Work done on the site this month' },
    gbp: { label: 'Add GBP Metrics', hint: 'Calls, directions and clicks' },
    ai: { label: 'Add Target AI Prompts', hint: 'Whether AI tools mention this brand' },
    screenshots: { label: 'Add Screenshots', hint: 'Evidence images to attach to the report' },
    gsc: { label: 'Add Search Console', hint: 'Clicks, impressions, CTR and position' },
    ga4: { label: 'Add Google Analytics', hint: 'Sessions, users and conversions' },
  };

  const nextKey = activeKeys.find(k => !statuses[k].loading && statuses[k].total === 0);
  const nextStep = nextKey ? STEP_COPY[nextKey] : null;

  return (
    <>
      <PageHeader
        title="Add Data"
        subtitle="Everything this client's report is built from. Work down the list."
        breadcrumbs={[
          { label: 'Home', href: '/' },
          { label: 'Clients', href: '/admin/clients' },
          { label: 'Add Data' },
        ]}
      />

      <div className="progress-card">
        <span className="stat-chip lg tone-amber"><Database size={22} /></span>

        <div className="progress-main">
          <h2 className="progress-title">Data Ingestion Progress</h2>
          <p className="progress-count">
            {stillLoading ? 'Checking data…' : `${checked} of ${total} data sets ready`}
          </p>
          <p className="progress-sub">
            {checked === total
              ? `Everything is in. You can generate the ${thisMonth} report.`
              : `Add the remaining data, then generate the ${thisMonth} report.`}
          </p>
          <div className="progress-bar-row">
            <div className={`bar checklist-bar ${checked < total ? 'partial' : ''}`}>
              <span className="fill" style={{ width: `${stillLoading ? 0 : pct}%` }} />
            </div>
            <span className="progress-pct">{stillLoading ? '—' : `${pct}%`}</span>
          </div>
        </div>

        {nextStep && (
          <div className="next-step">
            <div className="next-step-head">
              <span>Next Step</span>
              <ChevronRight size={14} />
            </div>
            <div className="next-step-body">
              <span className="stat-chip sm tone-blue"><FileSpreadsheet size={14} /></span>
              <div>
                <strong>{nextStep.label}</strong>
                <small>{nextStep.hint}</small>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="checklist">
        <IngestionCard
          title="Keyword Performance"
          tone="violet"
          icon={<Crosshair size={15} />}
          hint="Rankings for the keywords you track"
          status={statuses.keywords}
          endpoint={`/clients/${clientId}/keywords/upload_csv`}
          templateColumns="Keyword,SV,Initial Ranking,Aug'26"
          manualForm={<KeywordsManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />

        <IngestionCard
          title="Performed Backlinks Activities"
          tone="blue"
          icon={<LinkIcon size={15} />}
          hint="Links built for this client"
          status={statuses.links}
          endpoint={`/clients/${clientId}/links/upload_csv`}
          templateColumns="Month,Activity Name,URL,Count
Aug'26,Guest Post,https://example.com/post,1"
          manualForm={<LinksManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />

        <IngestionCard
          title="On-Site SEO Activities Performed"
          tone="green"
          icon={<CheckSquare size={15} />}
          hint="Work done on the site this month"
          status={statuses.work}
          endpoint={`/clients/${clientId}/work/upload_csv`}
          templateColumns="Activity Type,Count,Notes
Optimized Homepage,1,Updated meta titles"
          manualForm={<WorkManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />

        <IngestionCard
          title="GBP Metrics"
          tone="rose"
          icon={<MapPin size={15} />}
          hint="Google Business Profile calls, directions and clicks"
          status={statuses.gbp}
          endpoint={`/clients/${clientId}/manual-gbp/upload_csv`}
          templateColumns="Date,Impressions Desktop Maps,Impressions Desktop Search,Impressions Mobile Maps,Impressions Mobile Search,Calls,Direction Requests,Website Clicks,Bookings
Aug'26,100,50,300,150,5,2,10,1"
          manualForm={<GBPManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />

        <IngestionCard
          title="Target AI Prompts"
          tone="amber"
          icon={<Bot size={15} />}
          hint="Whether AI tools mention this brand"
          status={statuses.ai}
          endpoint={`/clients/${clientId}/ai_mentions/upload_csv`}
          templateColumns="Month,Prompts,ChatGPT,AI Overview,Google Gemini,Perplexity,Claude
Aug'26,Best pizza in NY,Yes,No,Yes,Yes,No"
          manualForm={<AIPromptsManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
        />

        {manualTraffic?.gsc && (
          <IngestionCard
            title="Search Console"
          tone="blue"
            icon={<Search size={15} />}
            hint="Clicks, impressions, CTR and position"
            status={statuses.gsc}
            endpoint={`/clients/${clientId}/manual-gsc/upload_csv`}
            templateColumns="date,clicks,impressions,ctr,position
2026-08-01,120,4500,0.027,12.4"
            manualForm={<GSCManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
          />
        )}

        {manualTraffic?.ga4 && (
          <IngestionCard
            title="Google Analytics"
          tone="orange"
            icon={<BarChart2 size={15} />}
            hint="Sessions, users, engagement and conversions"
            status={statuses.ga4}
            endpoint={`/clients/${clientId}/manual-ga4/upload_csv`}
            templateColumns="date,sessions,users,engaged_sessions,conversions,revenue
2026-08-01,761,589,147,3,0"
            manualForm={<GA4ManualForm clientId={clientId} onComplete={() => window.location.reload()} />}
          />
        )}

        <IngestionCard
          title="Screenshots"
          tone="orange"
          icon={<ImageIcon size={15} />}
          hint="Evidence images to attach to the report"
          status={statuses.screenshots}
          manualForm={<ScreenshotsManualForm clientId={clientId} />}
        />
      </div>

      <div className="help-strip">
        <span className="stat-chip sm tone-violet"><HelpCircle size={14} /></span>
        <div>
          <strong>Need help adding data?</strong>
          <small>Download a template for any row above, or upload an Excel sheet you already have.</small>
        </div>
      </div>
    </>
  );
};

export default ManualEntryHub;
