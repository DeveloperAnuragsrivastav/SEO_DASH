import { useState, useEffect } from 'react';
import { usePermissions } from '../../hooks/usePermissions';
import api from '../../api/client';
import { Navigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { UserPlus, Users as UsersIcon, FolderOpen, Search, ExternalLink, ChevronDown, Plus } from 'lucide-react';

import Page from '../../components/ui/Page';
import PageSkeleton from '../../components/ui/PageSkeleton';
import { confirmDialog } from '../../components/ui/ConfirmDialog';

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
  // Members whose project list is folded away.
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const toggle = (id: string) => setCollapsed(cur => {
    const next = new Set(cur);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
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
  const [userQuery, setUserQuery] = useState('');
  const [unassigning, setUnassigning] = useState(false);

  const handleUnassign = async (client: AssignedClient, member: User) => {
    if (unassigning || !(await confirmDialog({
      title: 'Unassign project?',
      message: `Remove ${member.email}’s access to ${client.name}? The project and its data will be kept.`,
      confirmText: 'Unassign',
    }))) return;
    setUnassigning(true);
    try {
      const response = await api.delete(`/managers/me/assignments/${client.id}/${member.id}`);
      toast.success(response.data.message);
      await loadDashboard();
    } catch {
      // The API interceptor displays the error.
    } finally {
      setUnassigning(false);
    }
  };

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

  const openAssignWizard = (userId: string) => {
    setCreatedUserId(userId);
    setNewProject({ name: '', domain: '', business_type: 'ecommerce', locale: 'en-GB', package_keywords: '10' });
    setExistingProjectId('');
    setWizardStep(2);
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
      // Handled by global interceptor
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
      // Handled by global interceptor
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
      // Handled by global interceptor
    } finally {
      setWizardSubmitting(false);
    }
  };

  const visibleUsers = users.filter(u =>
    !userQuery.trim() || u.email.toLowerCase().includes(userQuery.trim().toLowerCase())
  );

  if (loading) return <PageSkeleton stats={2} />;

  return (
      <Page
        screen="team"
        actions={
          <button className="btn btn-primary" onClick={openWizard}>
            Create Team Member
          </button>
        }
      >

      <div className="stat-duo">
        <div className="stat">
          <div className="stat-top">
            <span className="stat-chip lg tone-amber"><UsersIcon size={20} /></span>
            <div>
              <div className="stat-label">Your Team Members</div>
              <div className="stat-value">{stats.total_users}</div>
              <div className="stat-note plain">Active team members in your agency</div>
            </div>
          </div>
        </div>
        <div className="stat">
          <div className="stat-top">
            <span className="stat-chip lg tone-orange"><FolderOpen size={20} /></span>
            <div>
              <div className="stat-label">Your Projects</div>
              <div className="stat-value">{stats.total_projects}</div>
              <div className="stat-note plain">Total projects across your team</div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: '40px', display: 'grid', gap: '16px' }}>
        <div className="section-title">
          <div>
            <h3 className="h2">Users &amp; Assignments</h3>
            <p className="section-sub">Team members and their assigned projects.</p>
          </div>
          {users.length > 0 && (
            <div className="toolbar-search sm">
              <Search size={14} />
              <input
                value={userQuery}
                onChange={e => setUserQuery(e.target.value)}
                placeholder="Search team members…"
                aria-label="Search team members"
              />
            </div>
          )}
        </div>
        {users.length === 0 ? (
          <div className="page-card">
            <div className="empty-state">
              <span className="empty-state-icon"><UserPlus size={22} /></span>
              <h3>No team members yet</h3>
              <p>Create a team member to give them access to the projects you manage.</p>
            </div>
          </div>
        ) : (
          visibleUsers.map(u => (
            <div key={u.id} className="page-card-flush">
              <div className="member-row">
                <span className="avatar avatar-lg member-avatar">{u.email.slice(0, 2)}</span>

                <div className="member-identity">
                  <span className="member-email">
                    {u.email}
                    <span className={`status-pill ${u.is_active ? 'on' : ''}`}>
                      {u.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </span>
                  <span className="text-subtle text-xs">
                    Last Login: {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : 'Never'}
                  </span>
                </div>

                <span className="member-count hide-s">
                  <strong>{u.assigned_clients?.length || 0}</strong> Assigned Projects
                </span>

                <button className="btn btn-secondary btn-sm" onClick={() => openAssignWizard(u.id)}>
                  <Plus size={13} /> Assign Project
                </button>

                <button
                  type="button"
                  className="icon-btn member-toggle"
                  aria-expanded={!collapsed.has(u.id)}
                  aria-label={collapsed.has(u.id) ? `Show ${u.email}'s projects` : `Hide ${u.email}'s projects`}
                  title={collapsed.has(u.id) ? 'Show projects' : 'Hide projects'}
                  disabled={!u.assigned_clients?.length}
                  onClick={() => toggle(u.id)}
                >
                  <ChevronDown size={16} className={`member-chevron ${collapsed.has(u.id) ? '' : 'open'}`} />
                </button>
              </div>
              
              {!collapsed.has(u.id) && u.assigned_clients && u.assigned_clients.length > 0 && (
                <div className="member-projects">
                  <div className="member-projects-head">Assigned Projects ({u.assigned_clients.length})</div>
                  <div className="stack">
                    {u.assigned_clients.map(c => (
                      <div key={c.id} className="project-row">
                        <span className="stat-chip sm tone-amber"><FolderOpen size={14} /></span>
                        <div className="project-row-text">
                          <strong>{c.name}</strong>
                          <small>{c.domain}</small>
                        </div>
                        <Link to={`/admin/clients/${c.id}`} className="btn btn-secondary btn-sm">
                          <ExternalLink size={13} /> Dashboard
                        </Link>
                        <button className="btn btn-secondary btn-sm" disabled={unassigning} onClick={() => void handleUnassign(c, u)}>
                          Unassign
                        </button>
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
          <div className={`modal ${wizardStep === 2 ? 'modal-lg' : ''}`}>
            <h2 className="modal-title">
              {wizardStep === 1 ? 'Create Team Member' : 'Create Project'}
            </h2>
            <p className="modal-desc">
              {wizardStep === 1
                ? 'Step 1 of 2 · account credentials'
                : wizardStep === 2
                  ? 'Step 2 of 2 · create and assign a new SEO project to this team member.'
                  : 'Assign an existing project to this team member.'}
            </p>
            
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
                <div className="modal-actions">
                  <button type="button" onClick={closeWizard} className="btn btn-secondary" disabled={wizardSubmitting}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={wizardSubmitting}>
                    {wizardSubmitting ? 'Creating...' : 'Create User →'}
                  </button>
                </div>
              </form>
            ) : wizardStep === 2 ? (
              <>
                <form onSubmit={handleCreateAndAssignProject} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
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
                    <button type="button" onClick={closeWizard} className="btn ghost" disabled={wizardSubmitting}>Skip for now</button>
                    <span className="spacer" />
                    <button type="button" onClick={() => setWizardStep(3)} className="btn btn-secondary" disabled={wizardSubmitting}>Assign Existing</button>
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
                    {clients.filter(c => {
                      return !users.some(u => u.assigned_clients?.some(ac => ac.id === c.id));
                    }).map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div className="modal-actions">
                  <button type="button" onClick={() => setWizardStep(2)} className="btn ghost" disabled={wizardSubmitting}>Back</button>
                  <span className="spacer" />
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
    </Page>
  );
}
