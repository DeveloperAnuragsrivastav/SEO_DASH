import React, { useState } from 'react';
import api from '../api/client';
import { Upload, Plus, CheckCircle, AlertCircle } from 'lucide-react';

interface ManualGSCUIProps {
  clientId: string;
  monthStr: string; // YYYY-MM
  onSuccess: () => void;
}

const ManualGSCUI: React.FC<ManualGSCUIProps> = ({ clientId, monthStr, onSuccess }) => {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Single Page Form State
  const [pageUrl, setPageUrl] = useState('');
  const [clicks, setClicks] = useState('');
  const [impressions, setImpressions] = useState('');
  const [ctr, setCtr] = useState('');
  const [position, setPosition] = useState('');

  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});

  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setRowErrors({});

    try {
      await api.post(`/clients/${clientId}/manual-gsc`, {
        records: [
          {
            captured_on: `${monthStr}-01`,
            clicks: parseInt(clicks, 10),
            impressions: parseInt(impressions, 10),
            ctr: parseFloat(ctr),
            position: parseFloat(position),
            dimension_key: 'page',
            dimension_value: pageUrl
          }
        ]
      });
      setPageUrl('');
      setClicks('');
      setImpressions('');
      setCtr('');
      setPosition('');
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
        setError('Failed to save manual GSC metric');
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
          if (values.length < 5) continue;
          
          const record: any = {};
          headers.forEach((h, idx) => {
            record[h.trim()] = values[idx]?.trim();
          });
          
          if (!record.captured_on || !record.page_url || !record.clicks || !record.impressions || !record.ctr || !record.position) {
            throw new Error(`Row ${i} is missing required fields`);
          }
          
          records.push({
            captured_on: record.captured_on,
            dimension_key: 'page',
            dimension_value: record.page_url,
            clicks: parseInt(record.clicks, 10),
            impressions: parseInt(record.impressions, 10),
            ctr: parseFloat(record.ctr),
            position: parseFloat(record.position)
          });
        }

        const res = await api.post(`/clients/${clientId}/manual-gsc`, { records });
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
              Required: <code>captured_on, page_url, clicks, impressions, ctr, position</code>
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
            <h3 className="form-card-title">Add Single Page Metric</h3>
            <p className="form-card-sub">Enter one Search Console row for the selected month.</p>
          </div>
        </div>
        
        <div className="form-card-body">
        {error && <div className="inline-status error">{error}</div>}
        {rowErrors[0] && <div className="inline-status error">Validation error: {rowErrors[0]}</div>}

        <form onSubmit={handleSingleSubmit} className="form-grid">
          <div>
            <label className="form-label">Page URL</label>
            <input className="form-input" 
              required
              type="text" 
              value={pageUrl} 
              onChange={e => setPageUrl(e.target.value)}
            />
          </div>
          <div className="field-grid">
            <div>
              <label className="form-label">Clicks</label>
              <input className="form-input" 
                required
                type="number" 
                value={clicks} 
                onChange={e => setClicks(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label">Impressions</label>
              <input className="form-input" 
                required
                type="number" 
                value={impressions} 
                onChange={e => setImpressions(e.target.value)}
              />
            </div>
          </div>
          <div className="field-grid">
            <div>
              <label className="form-label">CTR (e.g. 0.05 for 5%)</label>
              <input className="form-input" 
                required
                type="number" 
                step="0.001"
                max="1"
                value={ctr} 
                onChange={e => setCtr(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label">Avg Position</label>
              <input className="form-input" 
                required
                type="number" 
                step="0.1"
                value={position} 
                onChange={e => setPosition(e.target.value)}
              />
            </div>
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

export default ManualGSCUI;
