import React, { useState, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import Page from '../../components/ui/Page';
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

const FALLBACK_EMAIL = 'website-cheker@gen-lang-client-0684717370.iam.gserviceaccount.com';
const BROWSER_TZ = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch { return ''; } })();
const ALL_TZ: string[] = (() => {
  try { return (Intl as any).supportedValuesOf('timeZone') as string[]; } catch { return [BROWSER_TZ, 'UTC', 'Europe/London', 'Asia/Kolkata', 'Asia/Dubai', 'America/New_York', 'America/Los_Angeles'].filter(Boolean); }
})();

type Option = { value: string; label: string; account?: string };

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

  // What Google says this service account can already read, per provider —
  // offered as a list so the right property is picked, not guessed.
  const [email, setEmail] = useState(FALLBACK_EMAIL);
  const [options, setOptions] = useState<Record<string, { list: Option[]; error: string | null; loading: boolean }>>({});
  useEffect(() => {
    const p = formData.provider;
    if (options[p]) return;
    setOptions(o => ({ ...o, [p]: { list: [], error: null, loading: true } }));
    api.get('/connections/google/options', { params: { provider: p }, skipErrorToast: true } as any)
      .then(({ data }) => {
        if (data?.email) setEmail(data.email);
        setOptions(o => ({ ...o, [p]: { list: data?.properties || [], error: data?.error || null, loading: false } }));
      })
      .catch(() => setOptions(o => ({ ...o, [p]: { list: [], error: 'Could not load the list from Google.', loading: false } })));
  }, [formData.provider]);
  const current = options[formData.provider];
  const mapped = useMemo(() => new Set(connections.map(c => `${c.provider}:${c.property_id}`)), [connections]);

  const fetchConnections = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/connections`);
      setConnections(data.filter((c: Connection) => c.provider !== 'dataforseo'));
    } catch (err: any) {
      // Handled by global interceptor
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
      err._toastHandled = true;
      setVerifyStatus(prev => ({...prev, [connId]: {type: 'error', msg: err.response?.data?.detail || 'Verification failed.'}}));
      fetchConnections(); 
    } finally {
      setVerifyingId(null);
    }
  };

  const addConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const { data } = await api.post(`/clients/${clientId}/connections`, {
        provider: formData.provider,
        property_id: formData.property_id,
        property_tz: (formData.provider === 'ga4' || formData.provider === 'gbp') ? formData.property_tz || undefined : undefined
      });

      // Mapping now checks the property, so say which of the two happened
      // rather than calling a saved row a success.
      const label = formData.provider.toUpperCase();
      if (data?.status === 'connected') {
        toast.success(`${label} mapped and verified — data can be pulled from it.`);
      } else {
        toast.warning(`${label} mapped, but it could not be read yet.`, {
          description: data?.last_error || 'Ask the client to grant the service account access, then press Verify.',
          duration: 8000,
        });
      }
      setFormData({
        provider: 'gsc', property_id: '', property_tz: ''
      });
      fetchConnections();
    } catch (err: any) {
      // Handled by global interceptor
    }
  };

  const deleteConnection = async (connId: string) => {
    try {
      await api.delete(`/connections/${connId}`);
      toast.success('Connection unmapped.');
      fetchConnections();
    } catch (err: any) {
      // Handled by global interceptor
    }
  };

  if (loading && !client) return <PageSkeleton />;

  return (
      <Page screen="connections">

      <div className={`connection-layout ${isAgencyAdmin ? '' : 'single'}`}>
        <div className="page-card-flush data-panel">
          <div className="card-header">
            <div>
              <h3 className="h2">Mapped Properties</h3>
              <p className="section-sub">Google properties linked to this client.</p>
            </div>
          </div>
          <div className="table-wrapper">
          <table className="data-table">
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
                <tr>
                  <td colSpan={5}>
                    <div className="table-empty">
                      <strong>No Google properties mapped.</strong>
                      Add Search Console or GA4 details to start pulling data automatically.
                    </div>
                  </td>
                </tr>
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
                        <div style={{ fontSize: 11, color: 'var(--down)', marginTop: 4, maxWidth: 320, lineHeight: 1.35 }}>{conn.last_error}</div>
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
                        <span className="table-actions">
                        <button className="btn btn-secondary btn-sm" onClick={() => handleVerify(conn.id)} disabled={verifyingId === conn.id}>
                          {verifyingId === conn.id ? '...' : 'Verify'}
                        </button>
                        <button className="btn btn-secondary btn-sm" style={{ color: 'var(--down)', borderColor: 'var(--down-soft)' }} onClick={() => deleteConnection(conn.id)}>
                          Delete
                        </button>
                        </span>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        </div>

        {isAgencyAdmin && (
          <div className="form-card">
            <div className="card-header">
              <h3 className="h2">Map Property</h3>
            </div>
            <div className="form-card-body">
              <div className="notice-warning">
                <h4 className="notice-title">Grant Access First</h4>
                <p className="notice-body">
                  Before mapping, you must grant <strong>Viewer</strong> access in your client's Google Search Console and Google Analytics 4 properties to the following Service Account email:
                </p>
                <div className="code-copy">
                  <code>{email}</code>
                  <button 
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      navigator.clipboard.writeText(email);
                      toast.success('Email copied to clipboard!');
                    }}
                  >
                    Copy
                  </button>
                </div>
              </div>
            <form onSubmit={addConnection} className="form-grid">
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
                <label className="form-label">{formData.provider === 'gsc' ? 'Website / property' : 'GA4 property ID'}</label>
                <input
                  type="text"
                  required value={formData.property_id}
                  onChange={e => setFormData({ ...formData, property_id: e.target.value })}
                  placeholder={formData.provider === 'gsc' ? 'foodbazaar.co.uk' : '439694882'}
                  className="form-input"
                  list={`conn-options-${formData.provider}`}
                  autoComplete="off"
                />
                <datalist id={`conn-options-${formData.provider}`}>
                  {(current?.list || []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </datalist>
                <p className="form-help">
                  {formData.provider === 'gsc'
                    ? <>Any form works — <code>foodbazaar.co.uk</code>, <code>https://www.foodbazaar.co.uk/</code> or <code>sc-domain:foodbazaar.co.uk</code>. The matching Search Console property is found for you.</>
                    : <>The number under Analytics → Admin → Property details (not the <code>G-…</code> measurement ID). You can also paste the Analytics address from your browser.</>}
                </p>
                {current?.loading && <p className="form-help">Checking which properties the service account can read…</p>}
                {!current?.loading && (current?.list?.length || 0) > 0 && (
                  <div className="conn-picks">
                    <span className="form-help">Already shared with the service account — pick one:</span>
                    <div className="conn-pick-list">
                      {current!.list.map(o => {
                        const taken = mapped.has(`${formData.provider}:${o.value}`);
                        return (
                          <button type="button" key={o.value} disabled={taken}
                                  className={`conn-pick ${formData.property_id === o.value ? 'on' : ''}`}
                                  title={taken ? 'Already mapped to this client' : o.account || o.value}
                                  onClick={() => setFormData({ ...formData, property_id: o.value })}>
                            {o.label}{taken ? ' · mapped' : ''}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
                {!current?.loading && current?.error && <p className="form-help" style={{ color: 'var(--down)' }}>{current.error}</p>}
              </div>
              
              {(formData.provider === 'ga4') && (
                <div className="form-group">
                  <label className="form-label">Property timezone <span className="form-optional">optional</span></label>
                  <input
                    type="text"
                    value={formData.property_tz}
                    onChange={e => setFormData({ ...formData, property_tz: e.target.value })}
                    placeholder={BROWSER_TZ || 'Europe/London'}
                    className="form-input"
                    list="conn-timezones"
                    autoComplete="off"
                  />
                  <datalist id="conn-timezones">
                    {ALL_TZ.map(z => <option key={z} value={z} />)}
                  </datalist>
                  <p className="form-help">
                    Leave blank — it is read from Google Analytics when the property is mapped, so the report's days match
                    the client's. Set it only if you map before access is granted.
                    {BROWSER_TZ && <> <button type="button" className="link-btn" onClick={() => setFormData({ ...formData, property_tz: BROWSER_TZ })}>Use {BROWSER_TZ}</button></>}
                  </p>
                </div>
              )}
              
              <div className="form-actions">
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
    </Page>
  );
}

export default Connections;
