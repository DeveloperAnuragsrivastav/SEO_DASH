import { useState, useEffect } from 'react';
import { usePermissions } from '../../hooks/usePermissions';
import api from '../../api/client';
import { Navigate, Link } from 'react-router-dom';
import { toast } from 'sonner';

import PageHeader from '../../components/ui/PageHeader';
import PageSkeleton from '../../components/ui/PageSkeleton';

interface AssignedClient {
  id: string;
  name: string;
  domain: string;
}

interface User {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
  assigned_clients?: AssignedClient[];
}

interface Client {
  id: string;
  name: string;
}

export default function ManagerDashboard() {
  const { isManager } = usePermissions();
  const [users, setUsers] = useState<User[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [stats, setStats] = useState({ total_users: 0, total_projects: 0 });
  const [loading, setLoading] = useState(true);
  
  // Wizard Modal state
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [newUser, setNewUser] = useState({ email: '', password: '', role: 'user' });
  const [createdUserId, setCreatedUserId] = useState('');
  const [newProject, setNewProject] = useState({ name: '', domain: '', business_type: 'ecommerce', locale: 'en-GB', package_keywords: '10' });
  const [existingProjectId, setExistingProjectId] = useState('');
  const [wizardSubmitting, setWizardSubmitting] = useState(false);

  const loadDashboard = async () => {
    try {
      const resStats = await api.get('/managers/me/dashboard');
      setStats(resStats.data);
      
      const [resClients, resUsers] = await Promise.all([
        api.get('/clients'),
        api.get('/managers/me/users')
      ]);
      setClients(resClients.data);
      setUsers(resUsers.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isManager) {
      loadDashboard();
    }
  }, [isManager]);

  if (!isManager) {
    return <Navigate to="/" replace />;
  }

  const openWizard = () => {
    setWizardStep(1);
    setNewUser({ email: '', password: '', role: 'user' });
    setCreatedUserId('');
    setNewProject({ name: '', domain: '', business_type: 'ecommerce', locale: 'en-GB', package_keywords: '10' });
    setShowWizard(true);
  };

  const closeWizard = () => {
    setShowWizard(false);
    setWizardStep(1);
    setCreatedUserId('');
    setNewUser({ email: '', password: '', role: 'user' });
    setNewProject({ name: '', domain: '', business_type: 'ecommerce', locale: 'en-GB', package_keywords: '10' });
    setExistingProjectId('');
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setWizardSubmitting(true);
    try {
      const res = await api.post('/managers/me/users', newUser);
      toast.success('User created successfully');
      setCreatedUserId(res.data.id);
      loadDashboard();
      setWizardStep(2); // Move to assignment step
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create user');
    } finally {
      setWizardSubmitting(false);
    }
  };

  const handleCreateAndAssignProject = async (e: React.FormEvent) => {
    e.preventDefault();
    setWizardSubmitting(true);
    try {
      // 1. Create the project
      const res = await api.post('/clients', {
        ...newProject,
        package_keywords: parseInt(newProject.package_keywords, 10),
        status: 'active',
        onboarded_at: new Date().toISOString().slice(0, 10),
      });
      
      // 2. Assign the project to the created user
      if (createdUserId && res.data.id) {
        await api.post('/managers/me/assignments', { user_id: createdUserId, client_id: res.data.id });
      }
      
      toast.success('Project created and assigned successfully');
      loadDashboard();
      closeWizard();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create project');
    } finally {
      setWizardSubmitting(false);
    }
  };

  const handleAssignExisting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!existingProjectId) return;
    setWizardSubmitting(true);
    try {
      if (createdUserId) {
        await api.post('/managers/me/assignments', { user_id: createdUserId, client_id: existingProjectId });
      }
      toast.success('Project assigned successfully');
      loadDashboard();
      closeWizard();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to assign project');
    } finally {
      setWizardSubmitting(false);
    }
  };

  if (loading) return <PageSkeleton stats={2} />;

  return (
    <>
      <PageHeader 
        title="Manager Tools" 
        subtitle="Manage your team and project assignments."
        breadcrumbs={[{ label: 'Home', href: '/' }, { label: 'Team & Assignments' }]}
        actions={
          <button className="btn btn-primary" onClick={openWizard}>
            Create Team Member
          </button>
        }
      />

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Your Team Members</div>
          <div className="stat-value">{stats.total_users}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Your Projects</div>
          <div className="stat-value">{stats.total_projects}</div>
        </div>
      </div>

      <div style={{ marginTop: '40px', display: 'grid', gap: '16px' }}>
        <h3 className="h2" style={{ fontSize: '18px', marginBottom: 4 }}>Users & Assignments</h3>
        {users.length === 0 ? (
          <div className="page-card" style={{ textAlign: 'center', padding: '48px' }}>
            <p className="text-subtle">You haven't created any users yet.</p>
          </div>
        ) : (
          users.map(u => (
            <div key={u.id} className="page-card-flush">
              <div style={{ padding: '24px', borderBottom: u.assigned_clients?.length ? '1px solid var(--border-subtle)' : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <h3 className="h2" style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
                      {u.email}
                      {u.is_active ? (
                        <span className="badge badge-success">ACTIVE</span>
                      ) : (
                        <span className="badge badge-neutral">INACTIVE</span>
                      )}
                    </h3>
                    <div className="text-subtle text-xs mono">
                      Last Login: {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : 'Never'}
                    </div>
                  </div>
                  <div className="text-sm text-subtle">
                    <strong>{u.assigned_clients?.length || 0}</strong> Assigned Projects
                  </div>
                </div>
              </div>
              
              {u.assigned_clients && u.assigned_clients.length > 0 && (
                <div style={{ padding: '16px 24px' }}>
                  <div style={{ display: 'grid', gap: '8px' }}>
                    {u.assigned_clients.map(c => (
                      <div key={c.id} style={{ padding: '12px 16px', background: 'var(--neutral-bg)', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div>
                          <div style={{ fontWeight: 600, marginBottom: 2 }}>{c.name}</div>
                          <div className="text-subtle text-xs">{c.domain}</div>
                        </div>
                        <Link to={`/admin/clients/${c.id}`} className="btn btn-secondary btn-sm">
                          Dashboard
                        </Link>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {showWizard && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3 className="h2" style={{ marginBottom: 20 }}>
              {wizardStep === 1 ? 'Create Team Member' : 'Up next: Create Project'}
            </h3>
            
            <div className="wizard-steps">
              <div className={`wizard-step ${wizardStep >= 1 ? (wizardStep > 1 ? 'done' : 'active') : ''}`} />
              <div className={`wizard-step ${wizardStep >= 2 ? 'active' : ''}`} />
            </div>

            {wizardStep === 1 ? (
              <form onSubmit={handleCreateUser} style={{ display: 'grid', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">Email Address</label>
                  <input 
                    type="email" 
                    required 
                    value={newUser.email}
                    onChange={e => setNewUser({...newUser, email: e.target.value})}
                    className="form-input"
                    placeholder="user@client.com"
                    autoFocus
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Temporary Password</label>
                  <input 
                    type="text" 
                    required 
                    value={newUser.password}
                    onChange={e => setNewUser({...newUser, password: e.target.value})}
                    className="form-input"
                    placeholder="••••••••"
                  />
                </div>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
                  <button type="button" onClick={closeWizard} className="btn btn-secondary" disabled={wizardSubmitting}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={wizardSubmitting}>
                    {wizardSubmitting ? 'Creating...' : 'Create User →'}
                  </button>
                </div>
              </form>
            ) : wizardStep === 2 ? (
              <>
                <p className="text-subtle" style={{ marginBottom: 20, fontSize: '14px' }}>Create and assign a new SEO project to this team member.</p>
                <form onSubmit={handleCreateAndAssignProject} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
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
                    <button type="button" onClick={closeWizard} className="btn btn-secondary" disabled={wizardSubmitting}>Skip for now</button>
                    <button type="button" onClick={() => setWizardStep(3)} className="btn btn-secondary" disabled={wizardSubmitting}>Assign Existing Project</button>
                    <button type="submit" className="btn btn-primary" disabled={wizardSubmitting}>
                      {wizardSubmitting ? 'Creating...' : 'Create & Assign'}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <form onSubmit={handleAssignExisting} style={{ display: 'grid', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">Select Existing Project</label>
                  <select className="form-input" value={existingProjectId} onChange={e => setExistingProjectId(e.target.value)} required>
                    <option value="" disabled>Select a project</option>
                    {clients.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
                  <button type="button" onClick={() => setWizardStep(2)} className="btn btn-secondary" disabled={wizardSubmitting}>Back</button>
                  <button type="button" onClick={closeWizard} className="btn btn-secondary" disabled={wizardSubmitting}>Skip</button>
                  <button type="submit" className="btn btn-primary" disabled={wizardSubmitting}>
                    {wizardSubmitting ? 'Assigning...' : 'Assign Project'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
