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
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', marginBottom: '32px' }}>
      
      {/* CSV Upload Section */}
      <div className="card">
        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Upload size={18} style={{ color: 'var(--ink)' }} /> Upload CSV
        </h3>
        <p style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '16px' }}>
          Required: <code>captured_on, page_url, clicks, impressions, ctr, position</code>
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

      {/* Manual Entry Section */}
      <div className="card">
        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Plus size={18} style={{ color: 'var(--ink)' }} /> Add Single Page Metric
        </h3>
        
        {error && <div style={{ color: 'var(--down)', fontSize: '13px', marginBottom: '12px' }}>{error}</div>}
        {rowErrors[0] && <div style={{ color: 'var(--down)', fontSize: '13px', marginBottom: '12px' }}>Validation error: {rowErrors[0]}</div>}

        <form onSubmit={handleSingleSubmit} style={{ display: 'grid', gap: '14px' }}>
          <div>
            <label>Page URL</label>
            <input 
              required
              type="text" 
              value={pageUrl} 
              onChange={e => setPageUrl(e.target.value)}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Clicks</label>
              <input 
                required
                type="number" 
                value={clicks} 
                onChange={e => setClicks(e.target.value)}
              />
            </div>
            <div>
              <label>Impressions</label>
              <input 
                required
                type="number" 
                value={impressions} 
                onChange={e => setImpressions(e.target.value)}
              />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>CTR (e.g. 0.05 for 5%)</label>
              <input 
                required
                type="number" 
                step="0.001"
                max="1"
                value={ctr} 
                onChange={e => setCtr(e.target.value)}
              />
            </div>
            <div>
              <label>Avg Position</label>
              <input 
                required
                type="number" 
                step="0.1"
                value={position} 
                onChange={e => setPosition(e.target.value)}
              />
            </div>
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

export default ManualGSCUI;
