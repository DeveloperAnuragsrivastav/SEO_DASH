import React, { useState } from 'react';
import api from '../api/client';
import { Upload, Plus, AlertCircle, CheckCircle } from 'lucide-react';

interface ManualRankingUIProps {
  clientId: string;
  onSuccess: () => void;
}

const ManualRankingUI: React.FC<ManualRankingUIProps> = ({ clientId, onSuccess }) => {
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [uploadErrors, setUploadErrors] = useState<{row: number, error: string}[]>([]);
  const [rowsInserted, setRowsInserted] = useState(0);

  const [keywordId, setKeywordId] = useState('');
  const [capturedOn, setCapturedOn] = useState(new Date().toISOString().split('T')[0]);
  const [position, setPosition] = useState('');
  const [url, setUrl] = useState('');
  const [formStatus, setFormStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [formError, setFormError] = useState('');

  const handleFileUpload = async () => {
    if (!csvFile) return;
    setUploadStatus('loading');
    setUploadErrors([]);
    setRowsInserted(0);

    const formData = new FormData();
    formData.append('file', csvFile);

    try {
      const res = await api.post(`/clients/${clientId}/rankings/upload_csv`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      if (res.data.status === 'success' || res.data.status === 'partial') {
        setUploadStatus(res.data.status === 'partial' ? 'error' : 'success');
        setRowsInserted(res.data.rows_inserted || 0);
        setUploadErrors(res.data.errors || []);
        if (res.data.rows_inserted > 0) {
          onSuccess();
        }
      } else {
        setUploadStatus('error');
        setUploadErrors(res.data.errors || []);
      }
    } catch (err: any) {
      setUploadStatus('error');
      setUploadErrors([{ row: 0, error: err.response?.data?.detail || 'Upload failed' }]);
    }
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormStatus('loading');
    setFormError('');

    try {
      await api.post(`/clients/${clientId}/rankings/manual`, {
        keyword_id: keywordId,
        captured_on: capturedOn,
        position: position ? parseInt(position, 10) : null,
        url: url || null
      });
      setFormStatus('success');
      setKeywordId('');
      setPosition('');
      setUrl('');
      onSuccess();
    } catch (err: any) {
      setFormStatus('error');
      setFormError(err.response?.data?.detail || 'Failed to add ranking');
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', marginBottom: '24px' }}>
      {/* CSV Upload */}
      <div className="card">
        <h3 style={{ margin: '0 0 12px 0', fontSize: '16px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Upload size={18} style={{ color: 'var(--ink)' }} /> Upload CSV
        </h3>
        <p style={{ fontSize: '13px', color: 'var(--ink-2)', marginBottom: '16px' }}>
          Required columns: <code>keyword, position, date, url</code>
        </p>
        
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <input 
            type="file" 
            accept=".csv"
            data-testid="csv-input"
            onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
            style={{ fontSize: '13px', flex: 1 }}
          />
          <button 
            data-testid="csv-submit"
            onClick={handleFileUpload}
            disabled={!csvFile || uploadStatus === 'loading'}
            className="btn btn-primary btn-sm"
          >
            {uploadStatus === 'loading' ? 'Uploading...' : 'Upload'}
          </button>
        </div>

        {uploadStatus === 'success' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--up)', fontSize: '13px', fontWeight: 500 }}>
            <CheckCircle size={16} /> Successfully inserted {rowsInserted} rows.
          </div>
        )}

        {uploadErrors.length > 0 && (
          <div data-testid="upload-errors" style={{ marginTop: '16px', background: 'var(--down-soft)', padding: '12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--down)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--down)', fontWeight: 600, marginBottom: '8px', fontSize: '13px' }}>
              <AlertCircle size={16} /> Errors found {rowsInserted > 0 && `(Inserted ${rowsInserted} rows)`}
            </div>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '12px', color: 'var(--down)', fontFamily: 'var(--font-mono)' }}>
              {uploadErrors.map((err, i) => (
                <li key={i}>Row {err.row}: {err.error}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Manual Entry Form */}
      <div className="card">
        <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Plus size={18} style={{ color: 'var(--ink)' }} /> Add Single Keyword
        </h3>
        <form onSubmit={handleFormSubmit} data-testid="manual-form">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label>Keyword ID</label>
              <input 
                required
                type="text"
                data-testid="kw-input"
                value={keywordId}
                onChange={e => setKeywordId(e.target.value)}
              />
            </div>
            <div>
              <label>Date</label>
              <input 
                required
                type="date"
                value={capturedOn}
                onChange={e => setCapturedOn(e.target.value)}
              />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
            <div>
              <label>Position (optional)</label>
              <input 
                type="number"
                min="1"
                data-testid="pos-input"
                value={position}
                onChange={e => setPosition(e.target.value)}
              />
            </div>
            <div>
              <label>URL (optional)</label>
              <input 
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
              />
            </div>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button 
              type="submit"
              disabled={formStatus === 'loading'}
              className="btn btn-primary btn-sm"
            >
              {formStatus === 'loading' ? 'Saving...' : 'Save Ranking'}
            </button>

            {formStatus === 'success' && (
              <span style={{ color: 'var(--up)', fontSize: '13px', fontWeight: 600 }}>Saved!</span>
            )}
          </div>

          {formError && (
            <div data-testid="form-error" style={{ marginTop: '12px', color: 'var(--down)', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <AlertCircle size={14} />
              {formError}
            </div>
          )}
        </form>
      </div>
    </div>
  );
};

export default ManualRankingUI;
