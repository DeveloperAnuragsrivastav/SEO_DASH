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
    <div className="surface-grid">
      <div className="form-card">
        <div className="form-card-head">
          <span className="form-card-icon"><Upload size={18} /></span>
          <div>
            <h3 className="form-card-title">Upload CSV</h3>
            <p className="form-card-sub">
              Required columns: <code>keyword, position, date, url</code>
            </p>
          </div>
        </div>
        
        <div className="form-card-body">
        <div className="upload-row">
          <input 
            className="file-input"
            type="file" 
            accept=".csv"
            data-testid="csv-input"
            onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
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
          <div className="inline-status success">
            <CheckCircle size={16} /> Successfully inserted {rowsInserted} rows.
          </div>
        )}

        {uploadErrors.length > 0 && (
          <div data-testid="upload-errors" className="inline-status error">
            <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, marginBottom: '8px' }}>
              <AlertCircle size={16} /> Errors found {rowsInserted > 0 && `(Inserted ${rowsInserted} rows)`}
            </div>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
              {uploadErrors.map((err, i) => (
                <li key={i}>Row {err.row}: {err.error}</li>
              ))}
            </ul>
            </div>
          </div>
        )}
        </div>
      </div>

      <div className="form-card">
        <div className="form-card-head">
          <span className="form-card-icon"><Plus size={18} /></span>
          <div>
            <h3 className="form-card-title">Add Single Keyword</h3>
            <p className="form-card-sub">Record a ranking update for one tracked keyword.</p>
          </div>
        </div>
        <div className="form-card-body">
        <form onSubmit={handleFormSubmit} data-testid="manual-form" className="form-grid">
          <div className="field-grid">
            <div>
              <label className="form-label">Keyword ID</label>
              <input
                className="form-input"
                required
                type="text"
                data-testid="kw-input"
                value={keywordId}
                onChange={e => setKeywordId(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label">Date</label>
              <input
                className="form-input"
                required
                type="date"
                value={capturedOn}
                onChange={e => setCapturedOn(e.target.value)}
              />
            </div>
          </div>
          <div className="field-grid">
            <div>
              <label className="form-label">Position (optional)</label>
              <input
                className="form-input"
                type="number"
                min="1"
                data-testid="pos-input"
                value={position}
                onChange={e => setPosition(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label">URL (optional)</label>
              <input
                className="form-input"
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
              />
            </div>
          </div>
          
          <div className="form-actions start">
            <button 
              type="submit"
              disabled={formStatus === 'loading'}
              className="btn btn-primary btn-sm"
            >
              {formStatus === 'loading' ? 'Saving...' : 'Save Ranking'}
            </button>

            {formStatus === 'success' && (
              <span className="inline-status success" style={{ marginTop: 0 }}>Saved!</span>
            )}
          </div>

          {formError && (
            <div data-testid="form-error" className="inline-status error">
              <AlertCircle size={14} />
              {formError}
            </div>
          )}
        </form>
        </div>
      </div>
    </div>
  );
};

export default ManualRankingUI;
