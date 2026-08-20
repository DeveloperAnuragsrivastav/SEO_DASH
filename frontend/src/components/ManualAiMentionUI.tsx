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
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', marginBottom: '32px' }}>
      
      {/* CSV Upload Section */}
      <div className="card">
        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Upload size={18} style={{ color: 'var(--ink)' }} /> Upload CSV
        </h3>
        <p style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '16px' }}>
          Required: <code>captured_on, platform, mentioned</code><br/>Optional: <code>prompt_id</code>
        </p>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <input type="file" accept=".csv" onChange={e => setCsvFile(e.target.files?.[0] || null)} style={{ fontSize: '13px', flex: 1 }} />
          <button onClick={handleFileUpload} disabled={!csvFile || uploadStatus === 'loading'} className="btn btn-primary btn-sm">
            {uploadStatus === 'loading' ? 'Uploading...' : 'Upload'}
          </button>
        </div>
        {uploadStatus === 'success' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--up)', marginTop: '12px', fontSize: '13px', fontWeight: 500 }}>
            <CheckCircle size={16} /> Successfully uploaded {rowsInserted} rows.
          </div>
        )}
        {uploadErrors.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--down)', marginTop: '12px', fontSize: '13px', fontWeight: 500 }}>
            <AlertCircle size={16} /> {uploadErrors[0]}
          </div>
        )}
      </div>

      {/* Manual Add Section */}
      <div className="card">
        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Plus size={18} style={{ color: 'var(--ink)' }} /> Add Single AI Mention
        </h3>
        
        {error && <div style={{ color: 'var(--down)', fontSize: '13px', marginBottom: '12px' }}>{error}</div>}
        {rowErrors[0] && <div style={{ color: 'var(--down)', fontSize: '13px', marginBottom: '12px' }}>Validation error: {rowErrors[0]}</div>}

        <form onSubmit={handleSingleSubmit} style={{ display: 'grid', gap: '14px' }}>
          <div>
            <label>Platform</label>
            <select 
              value={platform} 
              onChange={e => setPlatform(e.target.value)}
            >
              <option value="chatgpt">ChatGPT</option>
              <option value="claude">Claude</option>
              <option value="gemini">Gemini</option>
              <option value="perplexity">Perplexity</option>
            </select>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Captured On</label>
              <input 
                required
                type="date" 
                value={capturedOn} 
                onChange={e => setCapturedOn(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', margin: 0, marginTop: '16px' }}>
                <input 
                  type="checkbox" 
                  checked={mentioned} 
                  onChange={e => setMentioned(e.target.checked)}
                  style={{ width: 'auto' }}
                />
                <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--ink)' }}>Mentioned?</span>
              </label>
            </div>
          </div>
          <div>
            <label>Prompt ID (optional UUID)</label>
            <input 
              type="text" 
              value={promptId} 
              onChange={e => setPromptId(e.target.value)}
              placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
              style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}
            />
          </div>
          <div>
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
  );
};

export default ManualAiMentionUI;
