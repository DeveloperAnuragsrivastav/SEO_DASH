import { useState, useEffect } from 'react';
import { usePermissions } from '../../hooks/usePermissions';
import api from '../../api/client';
import { Navigate, Link } from 'react-router-dom';
import { toast } from 'sonner';

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
      toast.error(err.response?.data?.detail || 'Failed to create manager');
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
      toast.error(err.response?.data?.detail || 'Failed to create project');
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
      toast.error(err.response?.data?.detail || 'Failed to delete client.');
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
            Add Manager
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
          <div className="page-card" style={{ textAlign: 'center', padding: '48px' }}>
            <p className="text-subtle">No managers found. Create one to get started.</p>
          </div>
        ) : (
          managers.map(manager => (
            <div key={manager.id} className="page-card-flush">
              <div 
                style={{ padding: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                onClick={() => setExpandedId(expandedId === manager.id ? null : manager.id)}
              >
                <div>
                  <h3 className="h2" style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
                    {manager.email}
                    {manager.is_active ? (
                      <span className="badge badge-success">ACTIVE</span>
                    ) : (
                      <span className="badge badge-neutral">INACTIVE</span>
                    )}
                  </h3>
                  <div className="text-subtle text-xs mono">
                    Last Login: {manager.last_login_at ? new Date(manager.last_login_at).toLocaleDateString() : 'Never'}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '24px', color: 'var(--text-tertiary)' }}>
                  <div className="text-sm">
                    <strong>{manager.managed_users?.length || 0}</strong> Users
                  </div>
                  <div className="text-sm">
                    <strong>{manager.managed_clients?.length || 0}</strong> Projects
                  </div>
                  <div style={{ transform: expandedId === manager.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', width: 24, height: 24, display: 'grid', placeItems: 'center', background: 'var(--bg-app)', borderRadius: '50%' }}>
                    ↓
                  </div>
                </div>
              </div>
              
              {expandedId === manager.id && (
                <div style={{ borderTop: '1px solid var(--border-subtle)', padding: '24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                  
                  {/* Assigned Users */}
                  <div>
                    <h4 className="h2" style={{ fontSize: '15px', marginBottom: '16px' }}>Assigned Users</h4>
                    {manager.managed_users?.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {manager.managed_users.map(u => (
                          <div key={u.id} style={{ padding: '12px 16px', background: 'var(--neutral-bg)', borderRadius: 'var(--radius-sm)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 500 }}>{u.email}</span>
                            <span className={`badge ${u.is_active ? 'badge-success' : 'badge-neutral'}`}>{u.is_active ? 'Active' : 'Inactive'}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-subtle text-sm italic">No users assigned.</div>
                    )}
                  </div>
                  
                  {/* Assigned Clients */}
                  <div>
                    <h4 className="h2" style={{ fontSize: '15px', marginBottom: '16px' }}>Assigned Projects</h4>
                    {manager.managed_clients?.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {manager.managed_clients.map(c => (
                          <div key={c.id} style={{ padding: '12px 16px', background: 'var(--neutral-bg)', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div>
                              <div style={{ fontWeight: 600, marginBottom: 2 }}>{c.name}</div>
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
                                className="btn btn-secondary btn-sm"
                                style={{ color: 'var(--down)' }}
                              >
                                Delete
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-subtle text-sm italic">No projects assigned.</div>
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
                <h3 className="h2" style={{ marginBottom: 20 }}>Create New Manager</h3>
                <form onSubmit={handleAddManager} style={{ display: 'grid', gap: 16 }}>
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
                  <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
                    <button type="button" onClick={closeModal} className="btn btn-secondary" disabled={creating}>Cancel</button>
                    <button type="submit" className="btn btn-primary" disabled={creating}>
                      {creating ? 'Creating...' : 'Next: Assign Project'}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <>
                <h3 className="h2" style={{ marginBottom: 4 }}>Up next: Create Project</h3>
                <p className="text-subtle" style={{ marginBottom: 20, fontSize: '14px' }}>Assign an initial SEO project to this new manager.</p>
                <form onSubmit={handleAddProject} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
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
                  <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '16px' }}>
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
            <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 16, marginBottom: 20 }}>
              <h3 className="h2" style={{ color: 'var(--down)' }}>Delete {deletingClient.name}?</h3>
            </div>
            <p style={{ marginBottom: '16px', lineHeight: 1.5, color: 'var(--text-secondary)' }}>
              This action <strong>cannot be undone</strong>. This will permanently delete the <strong>{deletingClient.name}</strong> project, including all keyword rankings, metrics, backlink data, and user assignments.
            </p>
            <div className="form-group" style={{ marginBottom: '24px' }}>
              <label className="form-label" style={{ fontWeight: 500 }}>
                Please type <strong>{deletingClient.name}</strong> to confirm.
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
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setDeletingClient(null)}>
                Cancel
              </button>
              <button 
                className="btn btn-primary"
                style={{ background: 'var(--down)', borderColor: 'var(--down)' }}
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
