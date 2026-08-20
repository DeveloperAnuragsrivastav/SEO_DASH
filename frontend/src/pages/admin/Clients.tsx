import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Search } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../api/client';
import LoadingSpinner from '../../components/LoadingSpinner';
import { AdminShell } from '../../components/layout/AdminShell';
import {
  Bento,
  FilterChips,
  StatCard,
  StatusPill,
  TablePanel,
  Td,
  Th,
  btnGhost,
  btnPrimary,
  inputCls,
} from '../../components/kit';

interface Client {
  id: string;
  name: string;
  domain: string;
  business_type: string;
  status: string;
  package_keywords: number;
  locale: string;
}

const FILTERS = ["All", "Active", "Paused", "Churned"];

const Clients: React.FC = () => {
  const { user } = useAuth();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    domain: '',
    logo_url: '',
    business_type: 'local',
    locale: 'en-US',
    package_keywords: 10,
    status: 'active'
  });

  const isAgencyAdmin = user?.role === 'agency_admin';

  const fetchClients = async () => {
    try {
      const { data } = await api.get('/clients');
      setClients(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch clients');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
  }, []);

  const handleOpenModal = (client?: Client) => {
    if (client) {
      setEditingClient(client);
      setFormData({
        name: client.name,
        domain: client.domain,
        logo_url: (client as any).logo_url || '',
        business_type: client.business_type,
        locale: client.locale || 'en-US',
        package_keywords: client.package_keywords || 10,
        status: client.status,
      });
    } else {
      setEditingClient(null);
      setFormData({
        name: '',
        domain: '',
        logo_url: '',
        business_type: 'local',
        locale: 'en-US',
        package_keywords: 10,
        status: 'active'
      });
    }
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingClient) {
        await api.put(`/clients/${editingClient.id}`, formData);
      } else {
        await api.post('/clients', formData);
      }
      setShowModal(false);
      fetchClients();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'An error occurred');
    }
  };

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return clients.filter((c) => filter === "All" || c.status.toLowerCase() === filter.toLowerCase()).filter(
      (c) => !q || c.name.toLowerCase().includes(q) || c.domain.toLowerCase().includes(q)
    );
  }, [query, filter, clients]);

  const currentMonth = new Date().toISOString().slice(0, 7);

  if (loading) return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading clients…" /></div></AdminShell>;
  if (error) return <div className="p-8 text-red-500">Error: {error}</div>;

  return (
    <AdminShell
      breadcrumb="Clients"
      title="Clients"
      subtitle="Every managed account, its business type, and its current engagement status."
      actions={
        isAgencyAdmin && (
          <button
            type="button"
            className={btnPrimary}
            onClick={() => handleOpenModal()}
          >
            Add Client
          </button>
        )
      }
    >
      <Bento>
        <StatCard label="Managed Clients" value={clients.length} source="Agency · live" />
        <StatCard
          label="Tracked Keywords"
          value={clients.reduce((sum, c) => sum + (c.package_keywords || 0), 0)}
          source="DataForSEO · nightly"
        />
        <StatCard
          label="Active Accounts"
          value={clients.filter((c) => c.status === "active").length}
          source="Agency · live"
        />
        <StatCard label="Report Period" value={new Date(currentMonth + '-01').toLocaleString('default', { month: 'short', year: 'numeric' })} source="Agency · live" />
      </Bento>

      {clients.length > 0 && (
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <Link to="/admin/users" className={`${btnGhost}`}>
            User Management <span className="text-muted-foreground">→</span>
          </Link>
          <Link to={`/admin/clients/${clients[0].id}/connections`} className={`${btnGhost}`}>
            Global Connections <span className="text-muted-foreground">→</span>
          </Link>
          <Link to={`/clients/${clients[0].id}/keywords`} className={`${btnGhost}`}>
            Keyword Management <span className="text-muted-foreground">→</span>
          </Link>
        </div>
      )}

      <div>
        <div>
          <TablePanel
            title={
              <div className="flex flex-wrap items-center gap-4">
                <h2 className="font-serif text-xl leading-none">Client Portfolio</h2>
                <FilterChips items={FILTERS} value={filter} onChange={setFilter} />
              </div>
            }
            action={
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search clients..."
                  className={`${inputCls} w-56 pl-9`}
                />
              </div>
            }
            head={
              <>
                <Th>Name</Th>
                <Th>Domain</Th>
                <Th>Type</Th>
                <Th>Status</Th>
                <Th align="right">Actions</Th>
              </>
            }
            footer={
              <span className="text-xs text-muted-foreground">
                Showing {rows.length} of {clients.length} clients
              </span>
            }
          >
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-sm text-muted-foreground">
                  No clients match this search.
                </td>
              </tr>
            ) : (
              rows.map((client) => (
                <tr key={client.id} className="transition-colors hover:bg-secondary">
                  <Td>
                    <Link
                      to={`/admin/clients/${client.id}`}
                      className="font-medium text-foreground underline-offset-4 hover:underline"
                    >
                      {client.name}
                    </Link>
                  </Td>
                  <Td className="text-muted-foreground">{client.domain}</Td>
                  <Td>
                    <span className="rounded bg-secondary px-2 py-0.5 text-[11px] font-medium text-muted-foreground capitalize">
                      {client.business_type}
                    </span>
                  </Td>
                  <Td>
                    <StatusPill status={client.status === 'active' ? 'Active' : client.status === 'paused' ? 'Paused' : 'Churned'} />
                  </Td>
                  <Td align="right">
                    <div className="flex justify-end gap-2">
                      <Link
                        to={`/admin/clients/${client.id}`}
                        className="rounded-full bg-brand px-3 py-1 text-[11px] font-semibold text-ink"
                      >
                        Dashboard
                      </Link>
                      {isAgencyAdmin && (
                        <button
                          onClick={() => handleOpenModal(client)}
                          className="rounded-full border border-border px-3 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
                        >
                          Edit
                        </button>
                      )}
                    </div>
                  </Td>
                </tr>
              ))
            )}
          </TablePanel>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-[0_12px_24px_-4px_rgba(0,0,0,0.15)]">
            <h2 className="mb-5 font-serif text-xl font-semibold leading-none text-foreground">
              {editingClient ? 'Edit Client' : 'Add Client'}
            </h2>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Name</label>
                <input
                  type="text"
                  required value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  className={inputCls}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Domain</label>
                <input
                  type="text"
                  required value={formData.domain}
                  onChange={e => setFormData({ ...formData, domain: e.target.value })}
                  className={inputCls}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Logo URL (Optional)</label>
                <input
                  type="url"
                  value={formData.logo_url}
                  onChange={e => setFormData({ ...formData, logo_url: e.target.value })}
                  className={inputCls}
                />
              </div>
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Business Type</label>
                  <select
                    value={formData.business_type}
                    onChange={e => setFormData({ ...formData, business_type: e.target.value })}
                    className={inputCls}
                  >
                    <option value="ecommerce">Ecommerce</option>
                    <option value="leadgen">Leadgen</option>
                    <option value="local">Local</option>
                    <option value="saas">SaaS</option>
                  </select>
                </div>
                <div className="flex-1">
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Status</label>
                  <select
                    value={formData.status}
                    onChange={e => setFormData({ ...formData, status: e.target.value })}
                    className={inputCls}
                  >
                    <option value="active">Active</option>
                    <option value="paused">Paused</option>
                    <option value="churned">Churned</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Locale</label>
                  <input
                    type="text"
                    required value={formData.locale}
                    onChange={e => setFormData({ ...formData, locale: e.target.value })}
                    className={inputCls}
                  />
                </div>
                <div className="flex-1">
                  <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Package Keywords</label>
                  <input
                    type="number"
                    required value={formData.package_keywords}
                    onChange={e => setFormData({ ...formData, package_keywords: parseInt(e.target.value, 10) })}
                    className={inputCls}
                  />
                </div>
              </div>

              <div className="mt-2 flex justify-end gap-2">
                <button type="button" onClick={() => setShowModal(false)} className={btnGhost}>Cancel</button>
                <button type="submit" className={btnPrimary}>
                  {editingClient ? 'Save Changes' : 'Create Client'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AdminShell>
  );
};

export default Clients;
