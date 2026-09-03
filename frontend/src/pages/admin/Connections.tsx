import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';

import api from '../../api/client';
import { toast } from 'sonner';

interface Connection {
  id: string;
  client_id: string;
  provider: string;
  access_mode: string;
  property_id: string;
  property_tz?: string;
  status: string;
  last_verified_at?: string;
  last_error?: string;
}

const Connections: React.FC = () => {
  const { clientId } = useParams<{ clientId: string }>();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [client, setClient] = useState<any>(null);
  
  // Verify UI feedback states
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [verifyStatus, setVerifyStatus] = useState<Record<string, {type: 'success'|'error', msg: string}>>({});

  // Form state
  const [formData, setFormData] = useState({
    provider: 'gsc',
    property_id: '',
    property_tz: '',
  });

  const isAgencyAdmin = true;

  const fetchConnections = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/connections`);
      setConnections(data.filter((c: Connection) => c.provider !== 'dataforseo'));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to fetch connections');
    } finally {
      setLoading(false);
    }
  };

  const fetchClient = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}`);
      setClient(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchClient();
    fetchConnections();
  }, [clientId]);

  const handleVerify = async (connId: string) => {
    setVerifyingId(connId);
    setVerifyStatus(prev => ({...prev, [connId]: {type: 'success', msg: 'Verifying...'}}));
    
    try {
      await api.post(`/connections/${connId}/verify`);
      setVerifyStatus(prev => ({...prev, [connId]: {type: 'success', msg: 'Connection verified successfully.'}}));
      fetchConnections(); 
    } catch (err: any) {
      setVerifyStatus(prev => ({...prev, [connId]: {type: 'error', msg: err.response?.data?.detail || 'Verification failed.'}}));
      fetchConnections(); 
    } finally {
      setVerifyingId(null);
    }
  };

  const addConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post(`/clients/${clientId}/connections`, {
        provider: formData.provider,
        property_id: formData.property_id,
        property_tz: (formData.provider === 'ga4' || formData.provider === 'gbp') ? formData.property_tz || undefined : undefined
      });
      toast.success(`${formData.provider.toUpperCase()} mapped successfully.`);
      setFormData({
        provider: 'gsc', property_id: '', property_tz: ''
      });
      fetchConnections();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'An error occurred while adding connection');
    }
  };

  const deleteConnection = async (connId: string) => {
    try {
      await api.delete(`/connections/${connId}`);
      toast.success('Connection unmapped.');
      fetchConnections();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'An error occurred while deleting connection');
    }
  };

  if (loading && !client) return <PageSkeleton />;

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <Link to={`/admin/clients/${clientId}`} style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-tertiary)', textDecoration: 'none' }}>← Back to {client?.name}</Link>
      </div>
      <PageHeader 
        title="Google Connections"
        subtitle="Map Google properties to the Agency Master Service Account."
      />

      <div style={{ display: 'grid', gap: 24 }}>
        <div className="card">
          <div className="card-header">
            <h3 className="h2">Mapped Properties</h3>
          </div>
          <table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Property ID</th>
                <th>Status</th>
                <th className="hide-s">Verified</th>
                {isAgencyAdmin && <th className="num">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {connections.length === 0 ? (
                <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-3)' }}>No Google properties mapped.</td></tr>
              ) : connections.map(conn => {
                const vState = verifyStatus[conn.id];
                return (
                  <tr key={conn.id}>
                    <td style={{ textTransform: 'uppercase' }}><b>{conn.provider}</b></td>
                    <td>
                      <div className="mono" style={{ fontSize: 12 }}>{conn.property_id}</div>
                      {conn.property_tz && <div className="mono" style={{ fontSize: 10, color: 'var(--ink-3)' }}>TZ: {conn.property_tz}</div>}
                    </td>
                    <td>
                      <span className={`badge ${conn.status === 'connected' ? 'badge-success' : 'badge-error'}`}>
                        {conn.status === 'connected' ? 'Active' : 'Error'}
                      </span>
                      {conn.status === 'error' && conn.last_error && (
                        <div style={{ fontSize: 10, color: 'var(--down)', marginTop: 4, maxWidth: 150 }}>{conn.last_error}</div>
                      )}
                      {vState && (
                        <div style={{ fontSize: 10, color: vState.type === 'error' ? 'var(--down)' : 'var(--up)', marginTop: 4 }}>{vState.msg}</div>
                      )}
                    </td>
                    <td className="hide-s mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                      {conn.last_verified_at ? new Date(conn.last_verified_at).toLocaleDateString() : 'Never'}
                    </td>
                    {isAgencyAdmin && (
                      <td className="num">
                        <button className="btn btn-secondary btn-sm" style={{ marginRight: 6 }} onClick={() => handleVerify(conn.id)} disabled={verifyingId === conn.id}>
                          {verifyingId === conn.id ? '...' : 'Verify'}
                        </button>
                        <button className="btn btn-secondary btn-sm" style={{ color: 'var(--down)', borderColor: 'var(--down-soft)' }} onClick={() => deleteConnection(conn.id)}>
                          Delete
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {isAgencyAdmin && (
          <div className="card">
            <div className="card-header">
              <h3 className="h2">Map Property</h3>
            </div>
            <div className="card-body">
              <div style={{ marginBottom: 24, padding: 16, backgroundColor: 'var(--yellow-soft)', borderLeft: '4px solid var(--yellow)', borderRadius: 4 }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: 14, color: '#554c11' }}>Grant Access First</h4>
                <p style={{ margin: '0 0 12px 0', fontSize: 13, color: '#554c11' }}>
                  Before mapping, you must grant <strong>Viewer</strong> access in your client's Google Search Console and Google Analytics 4 properties to the following Service Account email:
                </p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#fff', padding: '8px 12px', borderRadius: 4, border: '1px solid #e5e5e1' }}>
                  <code style={{ flex: 1, fontSize: 12, color: 'var(--ink)' }}>website-cheker@gen-lang-client-0684717370.iam.gserviceaccount.com</code>
                  <button 
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      navigator.clipboard.writeText('website-cheker@gen-lang-client-0684717370.iam.gserviceaccount.com');
                      toast.success('Email copied to clipboard!');
                    }}
                  >
                    Copy
                  </button>
                </div>
              </div>
            <form onSubmit={addConnection} style={{ display: 'grid', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Google Provider</label>
                <select
                  value={formData.provider}
                  onChange={e => setFormData({ ...formData, provider: e.target.value })}
                  className="form-select"
                >
                  <option value="gsc">Google Search Console (GSC)</option>
                  <option value="ga4">Google Analytics 4 (GA4)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Property ID</label>
                <input
                  type="text"
                  required value={formData.property_id}
                  onChange={e => setFormData({ ...formData, property_id: e.target.value })}
                  placeholder={formData.provider === 'gsc' ? "sc-domain:example.com" : "properties/123456"}
                  className="form-input"
                />
              </div>
              
              {(formData.provider === 'ga4') && (
                <div className="form-group">
                  <label className="form-label">Property Timezone</label>
                  <input
                    type="text"
                    required value={formData.property_tz}
                    onChange={e => setFormData({ ...formData, property_tz: e.target.value })}
                    placeholder="America/New_York"
                    className="form-input"
                  />
                </div>
              )}
              
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
                <button
                  type="reset"
                  onClick={() => setFormData({ provider: 'gsc', property_id: '', property_tz: '' })}
                  className="btn btn-secondary"
                >
                  Clear
                </button>
                <button type="submit" className="btn btn-primary">
                  Map Connection
                </button>
              </div>
            </form>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default Connections;
