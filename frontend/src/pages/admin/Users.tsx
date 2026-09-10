import { useState, useEffect } from 'react';
import { usePermissions } from '../../hooks/usePermissions';
import api from '../../api/client';
import { Navigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { ChevronDown, UserPlus, Users as UsersIcon } from 'lucide-react';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';

interface NestedUser {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
}

interface NestedClient {
  id: string;
  name: string;
  domain: string;
}

interface Manager {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
  managed_users: NestedUser[];
  managed_clients: NestedClient[];
}

export default function Users() {
  const { isSuperAdmin } = usePermissions();
  const [managers, setManagers] = useState<Manager[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  
  // Modals state
  const [showAdd, setShowAdd] = useState(false);
  const [modalStep, setModalStep] = useState<'manager' | 'project'>('manager');
  const [newManagerId, setNewManagerId] = useState<string | null>(null);
  const [newManager, setNewManager] = useState({ email: '', password: '', role: 'manager' });
  const [newProject, setNewProject] = useState({ name: '', domain: '', business_type: 'ecommerce', locale: 'en-GB', package_keywords: '10' });
  const [creating, setCreating] = useState(false);
  
  // Client deletion state
  const [deletingClient, setDeletingClient] = useState<NestedClient | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');

  const loadManagers = async () => {
    try {
      const res = await api.get('/admin/managers');
      setManagers(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isSuperAdmin) {
      loadManagers();
    }
  }, [isSuperAdmin]);

  if (!isSuperAdmin) {
    return <Navigate to="/" replace />;
  }

  const handleAddManager = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await api.post('/admin/managers', newManager);
      setNewManagerId(res.data.id);
      setModalStep('project');
      toast.success('Manager created successfully');
      loadManagers();
    } catch (err: any) {
      // Handled by global interceptor
    } finally {
      setCreating(false);
    }
  };

  const handleAddProject = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      // 1. Create Project
      const res = await api.post('/clients', {
        ...newProject,
        package_keywords: parseInt(newProject.package_keywords, 10),
        status: 'active',
        onboarded_at: new Date().toISOString().slice(0, 10),
      });
      
      // 2. Assign to Manager
      if (newManagerId) {
        await api.put(`/admin/clients/${res.data.id}/reassign`, {
          manager_id: newManagerId
        });
      }

      toast.success('Project created and assigned successfully');
      closeModal();
      loadManagers();
    } catch (err: any) {
      // Handled by global interceptor
    } finally {
      setCreating(false);
    }
  };

  const closeModal = () => {
    setShowAdd(false);
    setModalStep('manager');
    setNewManagerId(null);
    setNewManager({ email: '', password: '', role: 'manager' });
    setNewProject({ name: '', domain: '', business_type: 'ecommerce', locale: 'en-GB', package_keywords: '10' });
  };

  const handleDeleteClient = async () => {
    if (!deletingClient) return;
    try {
      await api.delete(`/clients/${deletingClient.id}`);
      toast.success('Client completely deleted.');
      setDeletingClient(null);
      setDeleteConfirmation('');
      loadManagers();
    } catch (err: any) {
      // Handled by global interceptor
    }
  };

  const activeCount = managers.filter((m) => m.is_active).length;

  if (loading) return <PageSkeleton stats={3} />;

  return (
    <>
      <PageHeader 
        title="Manager Directory" 
        subtitle="Super Admins can create isolated Manager accounts here."
        breadcrumbs={[{ label: 'Home', href: '/' }, { label: 'Manager Directory' }]}
        actions={
          <button className="btn btn-primary" onClick={() => setShowAdd(true)}>
            <UserPlus size={15} /> Add Manager
          </button>
        }
      />

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Total Managers</div>
          <div className="stat-value">{managers.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Active</div>
          <div className="stat-value" style={{ color: 'var(--up)' }}>{activeCount}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Deactivated</div>
          <div className="stat-value">{managers.length - activeCount}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '16px' }}>
        {managers.length === 0 ? (
          <div className="page-card">
            <div className="empty-state">
              <span className="empty-state-icon"><UsersIcon size={22} /></span>
              <h3>No managers yet</h3>
              <p>Create an isolated manager account to start delegating projects.</p>
              <button className="btn btn-primary" onClick={() => setShowAdd(true)}><UserPlus size={15} /> Add Manager</button>
            </div>
          </div>
        ) : (
          managers.map(manager => (
            <div key={manager.id} className="page-card-flush">
              <button
                type="button"
                className="manager-row"
                aria-expanded={expandedId === manager.id}
                onClick={() => setExpandedId(expandedId === manager.id ? null : manager.id)}
              >
                <span className="avatar avatar-lg">{manager.email.slice(0, 2)}</span>

                <span className="manager-identity">
                  <span className="manager-email">
                    {manager.email}
                    {manager.is_active ? (
                      <span className="badge badge-success">ACTIVE</span>
                    ) : (
                      <span className="badge badge-neutral">INACTIVE</span>
                    )}
                  </span>
                  <span className="text-subtle text-xs">
                    Last login {manager.last_login_at ? new Date(manager.last_login_at).toLocaleDateString() : 'never'}
                  </span>
                </span>

                <span className="manager-counts hide-s">
                  <span className="manager-count">
                    <span className="manager-count-value mono">{manager.managed_users?.length || 0}</span>
                    <span className="overline">Users</span>
                  </span>
                  <span className="manager-count">
                    <span className="manager-count-value mono">{manager.managed_clients?.length || 0}</span>
                    <span className="overline">Projects</span>
                  </span>
                </span>

                <ChevronDown size={17} className={`manager-chevron ${expandedId === manager.id ? 'open' : ''}`} />
              </button>
              
              {expandedId === manager.id && (
                <div className="manager-detail">
                  
                  {/* Assigned Users */}
                  <div>
                    <div className="overline" style={{ marginBottom: 12 }}>Assigned Users</div>
                    {manager.managed_users?.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {manager.managed_users.map(u => (
                          <div key={u.id} className="list-row">
                            <span style={{ fontWeight: 500, fontSize: 13.5, overflowWrap: 'anywhere' }}>{u.email}</span>
                            <span className={`badge ${u.is_active ? 'badge-success' : 'badge-neutral'}`}>{u.is_active ? 'Active' : 'Inactive'}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-subtle text-sm">No users assigned.</div>
                    )}
                  </div>
                  
                  {/* Assigned Clients */}
                  <div>
                    <div className="overline" style={{ marginBottom: 12 }}>Assigned Projects</div>
                    {manager.managed_clients?.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {manager.managed_clients.map(c => (
                          <div key={c.id} className="list-row">
                            <div style={{ minWidth: 0 }}>
                              <div style={{ fontWeight: 600, marginBottom: 2, fontSize: 13.5 }}>{c.name}</div>
                              <div className="text-subtle text-xs">{c.domain}</div>
                            </div>
                            <div style={{ display: 'flex', gap: '8px' }}>
                              <Link to={`/admin/clients/${c.id}`} className="btn btn-secondary btn-sm">
                                Dashboard
                              </Link>
                              <button 
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setDeletingClient(c);
                                  setDeleteConfirmation('');
                                }}
                                className="btn btn-danger-ghost btn-sm"
                              >
                                Delete
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-subtle text-sm">No projects assigned.</div>
                    )}
                  </div>

                </div>
              )}
            </div>
          ))
        )}
      </div>

      {showAdd && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: modalStep === 'project' ? '500px' : '400px' }}>
            {modalStep === 'manager' ? (
              <>
                <h2 className="modal-title">Create New Manager</h2>
                <p className="modal-desc">Step 1 of 2 · account credentials</p>
                <div className="wizard-steps"><span className="wizard-step active" /><span className="wizard-step" /></div>
                <form onSubmit={handleAddManager}>
                  <div className="form-group">
                    <label className="form-label">Email Address</label>
                    <input 
                      type="email" 
                      required 
                      value={newManager.email}
                      onChange={e => setNewManager({...newManager, email: e.target.value})}
                      className="form-input"
                      placeholder="manager@agency.com"
                      autoFocus
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Temporary Password</label>
                    <input 
                      type="text" 
                      required 
                      value={newManager.password}
                      onChange={e => setNewManager({...newManager, password: e.target.value})}
                      className="form-input"
                      placeholder="••••••••"
                    />
                  </div>
                  <div className="modal-actions">
                    <button type="button" onClick={closeModal} className="btn btn-secondary" disabled={creating}>Cancel</button>
                    <button type="submit" className="btn btn-primary" disabled={creating}>
                      {creating ? 'Creating...' : 'Next: Assign Project'}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <>
                <h2 className="modal-title">Create Project</h2>
                <p className="modal-desc">Step 2 of 2 · assign an initial SEO project to this new manager.</p>
                <div className="wizard-steps"><span className="wizard-step done" /><span className="wizard-step active" /></div>
                <form onSubmit={handleAddProject} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                  <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                    <label className="form-label">Client Name</label>
                    <input className="form-input" value={newProject.name} onChange={e => setNewProject({...newProject, name: e.target.value})} required placeholder="Acme Corp" autoFocus />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                    <label className="form-label">Primary Domain</label>
                    <input className="form-input" value={newProject.domain} onChange={e => setNewProject({...newProject, domain: e.target.value})} required placeholder="acme.com" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Business Type</label>
                    <input className="form-input" type="text" value={newProject.business_type} onChange={e => setNewProject({...newProject, business_type: e.target.value})} required placeholder="E-commerce, SaaS..." />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Tracked Keywords</label>
                    <input className="form-input" type="number" min="0" value={newProject.package_keywords} onChange={e => setNewProject({...newProject, package_keywords: e.target.value})} />
                  </div>
                  <div className="modal-actions" style={{ gridColumn: '1 / -1' }}>
                    <button type="button" onClick={closeModal} className="btn btn-secondary" disabled={creating}>Skip for now</button>
                    <button type="submit" className="btn btn-primary" disabled={creating}>
                      {creating ? 'Creating...' : 'Create & Assign'}
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      )}

      {deletingClient && (
        <div className="modal-backdrop">
          <div className="modal">
            <h2 className="modal-title" style={{ color: 'var(--down)' }}>Delete {deletingClient.name}?</h2>
            <p className="modal-desc" style={{ marginBottom: 16 }}>
              This action <strong>cannot be undone</strong>. This will permanently delete the <strong>{deletingClient.name}</strong> project, including all keyword rankings, metrics, backlink data, and user assignments.
            </p>
            <div className="form-group">
              <label className="form-label">
                Type <strong>{deletingClient.name}</strong> to confirm
              </label>
              <input 
                type="text" 
                className="form-input" 
                value={deleteConfirmation}
                onChange={e => setDeleteConfirmation(e.target.value)}
                placeholder={deletingClient.name}
                autoFocus
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setDeletingClient(null)}>
                Cancel
              </button>
              <button
                className="btn btn-danger"
                disabled={deleteConfirmation !== deletingClient.name}
                onClick={handleDeleteClient}
              >
                Permanently Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
