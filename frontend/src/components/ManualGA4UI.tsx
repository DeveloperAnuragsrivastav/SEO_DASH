import React, { useState } from 'react';
import api from '../api/client';
import { Upload, Plus, CheckCircle, AlertCircle } from 'lucide-react';

interface ManualGA4UIProps {
  clientId: string;
  monthStr: string; // YYYY-MM
  onSuccess: () => void;
}

const ManualGA4UI: React.FC<ManualGA4UIProps> = ({ clientId, monthStr, onSuccess }) => {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Single Dimension Form State
  const [dimensionKey, setDimensionKey] = useState<'channel' | 'device' | 'country'>('channel');
  const [dimensionValue, setDimensionValue] = useState('');
  const [sessions, setSessions] = useState('');
  const [users, setUsers] = useState('');
  const [engagedSessions, setEngagedSessions] = useState('');
  const [conversions, setConversions] = useState('');
  const [revenue, setRevenue] = useState('');

  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});

  const handleSingleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setRowErrors({});

    try {
      await api.post(`/clients/${clientId}/manual-ga4`, {
        records: [
          {
            captured_on: `${monthStr}-01`,
            sessions: parseInt(sessions, 10),
            users: parseInt(users, 10),
            engaged_sessions: parseInt(engagedSessions, 10),
            conversions: parseInt(conversions, 10),
            revenue: parseFloat(revenue || '0'),
            dimension_key: dimensionKey,
            dimension_value: dimensionValue
          }
        ]
      });
      setDimensionValue('');
      setSessions('');
      setUsers('');
      setEngagedSessions('');
      setConversions('');
      setRevenue('');
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
        setError('Failed to save manual GA4 metric');
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
          
          if (!record.captured_on || !record.dimension_key || !record.dimension_value || !record.sessions || !record.users || !record.engaged_sessions || !record.conversions || !record.revenue) {
            throw new Error(`Row ${i} is missing required fields`);
          }
          
          records.push({
            captured_on: record.captured_on,
            dimension_key: record.dimension_key,
            dimension_value: record.dimension_value,
            sessions: parseInt(record.sessions, 10),
            users: parseInt(record.users, 10),
            engaged_sessions: parseInt(record.engaged_sessions, 10),
            conversions: parseInt(record.conversions, 10),
            revenue: parseFloat(record.revenue)
          });
        }

        const res = await api.post(`/clients/${clientId}/manual-ga4`, { records });
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
          Required: <code>captured_on, dimension_key, dimension_value, sessions, users, engaged_sessions, conversions, revenue</code>
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

      {/* Single Form Section */}
      <div className="card">
        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Plus size={18} style={{ color: 'var(--ink)' }} /> Add Single Dimension Metric
        </h3>
        
        {error && <div style={{ color: 'var(--down)', fontSize: '13px', marginBottom: '12px' }}>{error}</div>}
        {rowErrors[0] && <div style={{ color: 'var(--down)', fontSize: '13px', marginBottom: '12px' }}>Validation error: {rowErrors[0]}</div>}

        <form onSubmit={handleSingleSubmit} style={{ display: 'grid', gap: '14px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '12px' }}>
            <div>
              <label className="form-label">Dimension</label>
              <select className="form-select" 
                value={dimensionKey} 
                onChange={e => setDimensionKey(e.target.value as any)}
              >
                <option value="channel">Channel</option>
                <option value="device">Device</option>
                <option value="country">Country</option>
              </select>
            </div>
            <div>
              <label className="form-label">Value (e.g. 'Organic Search')</label>
              <input className="form-input" 
                required
                type="text" 
                value={dimensionValue} 
                onChange={e => setDimensionValue(e.target.value)}
              />
            </div>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label className="form-label">Sessions</label>
              <input className="form-input" 
                required
                type="number" 
                value={sessions} 
                onChange={e => setSessions(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label">Total Users (Count)</label>
              <input className="form-input" 
                required
                type="number" 
                value={users} 
                onChange={e => setUsers(e.target.value)}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
            <div>
              <label className="form-label">Engaged</label>
              <input className="form-input" 
                required
                type="number" 
                value={engagedSessions} 
                onChange={e => setEngagedSessions(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label">Conv.</label>
              <input className="form-input" 
                required
                type="number" 
                value={conversions} 
                onChange={e => setConversions(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label">Revenue</label>
              <input className="form-input" 
                type="number" 
                step="0.01"
                value={revenue} 
                onChange={e => setRevenue(e.target.value)}
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

export default ManualGA4UI;
