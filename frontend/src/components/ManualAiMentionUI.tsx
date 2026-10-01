import React, { useState } from 'react';
import api from '../api/client';
import { Upload, Plus, CheckCircle, AlertCircle } from 'lucide-react';

interface ManualAiMentionUIProps {
  clientId: string;
  monthStr: string; // YYYY-MM
  onSuccess: () => void;
}

const ManualAiMentionUI: React.FC<ManualAiMentionUIProps> = ({ clientId, monthStr, onSuccess }) => {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Single Page Form State
  const [platform, setPlatform] = useState('chatgpt');
  const [promptId, setPromptId] = useState('');
  const [mentioned, setMentioned] = useState(false);
  const [capturedOn, setCapturedOn] = useState(`${monthStr}-01`);

  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});

  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setRowErrors({});

    try {
      await api.post(`/api/clients/${clientId}/ai_mentions/manual`, {
        captured_on: capturedOn,
        platform,
        mentioned,
        prompt_id: promptId || null,
        cited_pages: null
      });
      setPromptId('');
      setMentioned(false);
      onSuccess();
    } catch (err: any) {
      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          const newErrors: Record<number, string> = {};
          err.response.data.detail.forEach((issue: any) => {
            const idx = issue.loc.includes('records') ? issue.loc[issue.loc.indexOf('records') + 1] : 0;
            newErrors[idx] = issue.msg;
          });
          setRowErrors(newErrors);
        } else {
          setError(err.response.data.detail);
        }
      } else {
        setError('Failed to save manual AI mention metric');
      }
    } finally {
      setLoading(false);
    }
  };

  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [rowsInserted, setRowsInserted] = useState(0);

  const handleFileUpload = async () => {
    if (!csvFile) return;
    setUploadStatus('loading');
    setUploadErrors([]);
    setRowsInserted(0);

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

        const res = await api.post(`/api/clients/${clientId}/ai_mentions/bulk`, records);
        setUploadStatus('success');
        setRowsInserted(res.data.rows_inserted);
        onSuccess();
      } catch (err: any) {
        setUploadStatus('error');
        setUploadErrors([err.message || 'Failed to parse or upload CSV']);
      }
    };
    reader.readAsText(csvFile);
  };

  return (
    <div className="surface-grid">
      <div className="form-card">
        <div className="form-card-head">
          <span className="form-card-icon"><Upload size={18} /></span>
          <div>
            <h3 className="form-card-title">Upload CSV</h3>
            <p className="form-card-sub">
              Required: <code>captured_on, platform, mentioned</code><br />Optional: <code>prompt_id</code>
            </p>
          </div>
        </div>
        <div className="form-card-body">
        <div className="upload-row">
          <input className="file-input" type="file" accept=".csv" onChange={e => setCsvFile(e.target.files?.[0] || null)} />
          <button onClick={handleFileUpload} disabled={!csvFile || uploadStatus === 'loading'} className="btn btn-primary btn-sm">
            {uploadStatus === 'loading' ? 'Uploading...' : 'Upload'}
          </button>
        </div>
        {uploadStatus === 'success' && (
          <div className="inline-status success">
            <CheckCircle size={16} /> Successfully uploaded {rowsInserted} rows.
          </div>
        )}
        {uploadErrors.length > 0 && (
          <div className="inline-status error">
            <AlertCircle size={16} /> {uploadErrors[0]}
          </div>
        )}
        </div>
      </div>

      <div className="form-card">
        <div className="form-card-head">
          <span className="form-card-icon"><Plus size={18} /></span>
          <div>
            <h3 className="form-card-title">Add Single AI Mention</h3>
            <p className="form-card-sub">Record one AI visibility check for this period.</p>
          </div>
        </div>
        
        <div className="form-card-body">
        {error && <div className="inline-status error">{error}</div>}
        {rowErrors[0] && <div className="inline-status error">Validation error: {rowErrors[0]}</div>}

        <form onSubmit={handleSingleSubmit} className="form-grid">
          <div>
            <label className="form-label">Platform</label>
            <select
              className="form-select"
              value={platform} 
              onChange={e => setPlatform(e.target.value)}
            >
              <option value="chatgpt">ChatGPT</option>
              <option value="claude">Claude</option>
              <option value="gemini">Gemini</option>
              <option value="perplexity">Perplexity</option>
            </select>
          </div>
          <div className="field-grid">
            <div>
              <label className="form-label">Captured On</label>
              <input
                className="form-input"
                required
                type="date" 
                value={capturedOn} 
                onChange={e => setCapturedOn(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label">Mention Status</label>
              <label className="inline-check">
                <input 
                  type="checkbox" 
                  checked={mentioned} 
                  onChange={e => setMentioned(e.target.checked)}
                />
                <span>Mentioned?</span>
              </label>
            </div>
          </div>
          <div>
            <label className="form-label">Prompt ID (optional UUID)</label>
            <input
              className="form-input mono"
              type="text" 
              value={promptId} 
              onChange={e => setPromptId(e.target.value)}
              placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
            />
          </div>
          <div className="form-actions start">
            <button 
              type="submit" 
              disabled={loading}
              className="btn btn-primary btn-sm"
            >
              {loading ? 'Saving...' : 'Save Metric'}
            </button>
          </div>
        </form>
        </div>
      </div>
    </div>
  );
};

export default ManualAiMentionUI;
