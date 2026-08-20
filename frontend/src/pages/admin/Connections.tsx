import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import api from '../../api/client';
import LoadingSpinner from '../../components/LoadingSpinner';
import { toast } from 'sonner';

import { AdminShell } from '../../components/layout/AdminShell';
import {
  EmptyState,
  Panel,
  StatusPill,
  btnPrimary,
  btnGhost,
  inputCls
} from '../../components/kit';

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

const COLUMNS = ["Provider", "Property / Mode", "Status", "Last Verified", "Actions / Feedback"];

const Connections: React.FC = () => {
  const { clientId } = useParams<{ clientId: string }>();
  const { user } = useAuth();
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
    access_mode: 'platform_shared',
    login: '',
    password: ''
  });

  const isAgencyAdmin = user?.role === 'agency_admin';

  const fetchConnections = async () => {
    try {
      const { data } = await api.get(`/clients/${clientId}/connections`);
      setConnections(data);
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
      fetchConnections(); // Refresh status
    } catch (err: any) {
      setVerifyStatus(prev => ({...prev, [connId]: {type: 'error', msg: err.response?.data?.detail || 'Verification failed.'}}));
      fetchConnections(); // Refresh status
    } finally {
      setVerifyingId(null);
    }
  };

  const addConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (formData.provider === 'dataforseo') {
        await api.post(`/clients/${clientId}/connections/dataforseo`, {
          access_mode: formData.access_mode,
          login: formData.access_mode === 'client_owned' ? formData.login : undefined,
          password: formData.access_mode === 'client_owned' ? formData.password : undefined,
        });
      } else {
        await api.post(`/clients/${clientId}/connections`, {
          provider: formData.provider,
          property_id: formData.property_id,
          property_tz: (formData.provider === 'ga4' || formData.provider === 'gbp') ? formData.property_tz || undefined : undefined
        });
      }
      toast.success(`${formData.provider.toUpperCase()} connected.`);
      setFormData({
        provider: 'gsc', property_id: '', property_tz: '', access_mode: 'platform_shared', login: '', password: ''
      });
      fetchConnections();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'An error occurred while adding connection');
    }
  };

  const deleteConnection = async (connId: string) => {
    try {
      await api.delete(`/connections/${connId}`);
      toast.success('Connection disconnected.');
      fetchConnections();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'An error occurred while deleting connection');
    }
  };

  if (loading || !client) return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading connections…" /></div></AdminShell>;

  return (
    <AdminShell
      breadcrumb={`${client.name} / Connections`}
      title="Connections"
      subtitle="Data sources feeding this client's monthly reports."
      actions={
        isAgencyAdmin && (
          <button
            type="button"
            className={btnPrimary}
            onClick={() =>
              document
                .getElementById("add-connection")
                ?.scrollIntoView({ behavior: "smooth", block: "center" })
            }
          >
            Add Connection
          </button>
        )
      }
    >
      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-12">
        <section className="overflow-hidden rounded-lg border border-border bg-card lg:col-span-8">
          <header className="flex items-center justify-between border-b border-border px-6 py-4">
            <h2 className="font-serif text-xl leading-none">Connected Sources</h2>
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
              {connections.length} active
            </span>
          </header>
          <div className="flex flex-wrap gap-x-8 gap-y-2 border-b border-border bg-secondary px-6 py-3">
            {COLUMNS.map((col) => (
              <span
                key={col}
                className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground"
              >
                {col}
              </span>
            ))}
          </div>
          {connections.length === 0 ? (
            <EmptyState>No connections found for this client.</EmptyState>
          ) : (
            <ul className="divide-y divide-border">
              {connections.map((conn) => {
                const vState = verifyStatus[conn.id];
                const isGoogle = ['gsc', 'ga4', 'gbp'].includes(conn.provider);
                return (
                  <li
                    key={conn.id}
                    className="flex flex-col gap-2 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="flex flex-1 items-center justify-between gap-4">
                      <span className="text-sm font-medium uppercase min-w-[80px]">{conn.provider}</span>
                      <div className="flex-1 min-w-[120px]">
                        <span className="font-mono text-xs text-muted-foreground">
                          {conn.provider === 'dataforseo' ? conn.access_mode : conn.property_id}
                        </span>
                        {conn.property_tz && (
                          <div className="text-[10px] text-muted-foreground mt-0.5">TZ: {conn.property_tz}</div>
                        )}
                      </div>
                      <div className="w-[80px]">
                        <StatusPill status={conn.status === 'connected' ? 'Active' : conn.status === 'error' ? 'Paused' : 'Churned'} />
                        {conn.status === 'error' && conn.last_error && (
                          <div className="text-[10px] text-red-500 mt-1 max-w-[150px] truncate" title={conn.last_error}>
                            {conn.last_error}
                          </div>
                        )}
                      </div>
                      <span className="font-mono text-[11px] text-muted-foreground w-[100px]">
                        {conn.last_verified_at ? new Date(conn.last_verified_at).toLocaleDateString() : 'Never'}
                      </span>
                    </div>

                    <div className="flex w-full flex-col sm:w-auto sm:items-end mt-2 sm:mt-0">
                      <div className="flex items-center gap-3">
                        {isAgencyAdmin && isGoogle && (
                          <button
                            type="button"
                            onClick={() => handleVerify(conn.id)}
                            disabled={verifyingId === conn.id}
                            className="rounded border border-border px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
                          >
                            {verifyingId === conn.id ? 'Verifying...' : 'Verify'}
                          </button>
                        )}
                        {isAgencyAdmin && (
                          <button
                            type="button"
                            onClick={() => deleteConnection(conn.id)}
                            className="text-[11px] font-medium text-status-churned-text hover:underline"
                          >
                            Disconnect
                          </button>
                        )}
                      </div>
                      {vState && (
                        <div className={`mt-1.5 text-[11px] font-medium ${vState.type === 'error' ? 'text-red-500' : 'text-green-500'}`}>
                          {vState.msg}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {isAgencyAdmin && (
          <div id="add-connection" className="lg:col-span-4">
            <Panel title="Add Connection">
              <form onSubmit={addConnection}>
                <div className="space-y-4">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Provider</label>
                    <select
                      value={formData.provider}
                      onChange={e => setFormData({ ...formData, provider: e.target.value })}
                      className={inputCls}
                    >
                      <option value="gsc">Google Search Console (GSC)</option>
                      <option value="ga4">Google Analytics 4 (GA4)</option>
                      <option value="gbp">Google Business Profile (GBP)</option>
                      <option value="dataforseo">DataForSEO</option>
                    </select>
                  </div>

                  {formData.provider !== 'dataforseo' ? (
                    <>
                      <div>
                        <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Property ID</label>
                        <input
                          type="text"
                          required value={formData.property_id}
                          onChange={e => setFormData({ ...formData, property_id: e.target.value })}
                          placeholder={formData.provider === 'gsc' ? "sc-domain:example.com" : "properties/123456"}
                          className={inputCls}
                        />
                      </div>
                      {(formData.provider === 'ga4' || formData.provider === 'gbp') && (
                        <div>
                          <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Property Timezone</label>
                          <input
                            type="text"
                            required value={formData.property_tz}
                            onChange={e => setFormData({ ...formData, property_tz: e.target.value })}
                            placeholder="America/New_York"
                            className={inputCls}
                          />
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <div>
                        <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Access Mode</label>
                        <select
                          value={formData.access_mode}
                          onChange={e => setFormData({ ...formData, access_mode: e.target.value })}
                          className={inputCls}
                        >
                          <option value="platform_shared">Platform Shared (Default)</option>
                          <option value="client_owned">Client Owned</option>
                        </select>
                      </div>
                      {formData.access_mode === 'client_owned' && (
                        <>
                          <div>
                            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Login ID</label>
                            <input
                              type="text"
                              required value={formData.login}
                              onChange={e => setFormData({ ...formData, login: e.target.value })}
                              className={inputCls}
                            />
                          </div>
                          <div>
                            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Password (API Key)</label>
                            <input
                              type="password"
                              required value={formData.password}
                              onChange={e => setFormData({ ...formData, password: e.target.value })}
                              className={inputCls}
                            />
                          </div>
                        </>
                      )}
                    </>
                  )}
                </div>
                <div className="mt-5 flex justify-end gap-2">
                  <button
                    type="reset"
                    onClick={() => setFormData({ provider: 'gsc', property_id: '', property_tz: '', access_mode: 'platform_shared', login: '', password: '' })}
                    className={btnGhost}
                  >
                    Clear
                  </button>
                  <button type="submit" className={btnPrimary}>
                    Add Connection
                  </button>
                </div>
              </form>
            </Panel>
          </div>
        )}
      </div>
    </AdminShell>
  );
}

export default Connections;
