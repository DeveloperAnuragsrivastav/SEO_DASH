import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import Page from '../../components/ui/Page';
import PageSkeleton from '../../components/ui/PageSkeleton';
import { confirmDialog } from '../../components/ui/ConfirmDialog';

interface Member { id: string; email: string }
interface Project { id: string; name: string; domain: string; user_id: string | null }
interface Options { users: Member[]; projects: Project[] }

export default function TeamAssignments() {
  const { user } = useAuth();
  const [options, setOptions] = useState<Options>({ users: [], projects: [] });
  const [projectId, setProjectId] = useState('');
  const [userId, setUserId] = useState(user?.id || '');
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const emptyProject = { name: '', domain: '', business_type: 'ecommerce', locale: 'en-GB', package_keywords: '10' };
  const [newProject, setNewProject] = useState(emptyProject);

  const createProject = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saving || !userId) return;
    setSaving(true);
    try {
      const response = await api.post('/team/projects', {
        ...newProject, name: newProject.name.trim(), domain: newProject.domain.trim(),
        package_keywords: Number(newProject.package_keywords), user_id: userId,
      });
      toast.success('Project created and assigned successfully');
      setProjectId(response.data.id);
      setCreating(false);
      setNewProject(emptyProject);
      await load();
    } catch {
      // Preserve the form for correction or retry; the API displays the reason.
    } finally {
      setSaving(false);
    }
  };

  const load = async () => {
    setLoading(true);
    setFailed(false);
    try {
      const response = await api.get<Options>('/team/assignments');
      setOptions(response.data);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const project = options.projects.find(p => p.id === projectId);
  const assignee = options.users.find(u => u.id === project?.user_id);
  const alreadyAssigned = !!project?.user_id;

  const unassign = async () => {
    if (!project?.user_id || saving) return;
    if (!(await confirmDialog({
      title: 'Unassign project?',
      message: `Remove ${assignee?.email || 'the current user'}’s access to ${project.name}? The project and its data will be kept.`,
      confirmText: 'Unassign',
    }))) return;
    setSaving(true);
    try {
      const response = await api.delete(`/team/assignments/${project.id}/${project.user_id}`);
      toast.success(response.data.message);
      await load();
    } catch {
      // The API interceptor displays the error.
    } finally {
      setSaving(false);
    }
  };

  const assign = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!projectId || !userId || saving || alreadyAssigned) return;
    setSaving(true);
    try {
      const response = await api.post('/team/assignments', { client_id: projectId, user_id: userId });
      toast.success(response.data.message);
      setProjectId('');
      await load();
    } catch {
      // The API interceptor displays the error and the selection stays available to retry.
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <PageSkeleton cards={1} stats={0} />;

  return (
    <Page screen="team-assignments" actions={!failed && !creating ? (
      <button className="btn btn-primary" disabled={saving} onClick={() => { setCreating(true); setUserId(user?.id || ''); }}>Create Project</button>
    ) : undefined}>
      <section className="page-card">
        {failed ? (
          <div role="alert">
            <p>Unable to load your team’s assignments. Your account needs an active manager.</p>
            <button className="btn btn-secondary" onClick={() => void load()}>Try again</button>
          </div>
        ) : creating ? (
          <form onSubmit={createProject}>
            <h2 className="h2">Create Project</h2>
            <p>The project will belong to your manager and be assigned to the team member you choose.</p>
            <div className="form-group">
              <label className="form-label" htmlFor="new-project-name">Project name</label>
              <input id="new-project-name" className="form-input" required maxLength={255} disabled={saving}
                value={newProject.name} onChange={e => setNewProject({ ...newProject, name: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="new-project-domain">Domain</label>
              <input id="new-project-domain" className="form-input" required maxLength={255} placeholder="example.com" disabled={saving}
                value={newProject.domain} onChange={e => setNewProject({ ...newProject, domain: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="new-project-type">Business type</label>
              <input id="new-project-type" className="form-input" required maxLength={100} disabled={saving}
                value={newProject.business_type} onChange={e => setNewProject({ ...newProject, business_type: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="new-project-locale">Locale</label>
              <input id="new-project-locale" className="form-input" required maxLength={35} disabled={saving}
                value={newProject.locale} onChange={e => setNewProject({ ...newProject, locale: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="new-project-keywords">Tracked keywords</label>
              <input id="new-project-keywords" className="form-input" type="number" min="0" step="1" required disabled={saving}
                value={newProject.package_keywords} onChange={e => setNewProject({ ...newProject, package_keywords: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="new-project-user">Assign to</label>
              <select id="new-project-user" className="form-input" required value={userId} disabled={saving}
                onChange={e => setUserId(e.target.value)}>
                <option value="">Choose a team member</option>
                {options.users.map(u => <option key={u.id} value={u.id}>{u.email}{u.id === user?.id ? ' (you)' : ''}</option>)}
              </select>
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" type="button" disabled={saving} onClick={() => setCreating(false)}>Cancel</button>
              <button className="btn btn-primary" type="submit" disabled={saving || !userId || !newProject.name.trim() || !newProject.domain.trim()}>
                {saving ? 'Creating…' : 'Create & Assign'}
              </button>
            </div>
          </form>
        ) : options.projects.length === 0 ? (
          <p>No projects yet. Choose Create Project to add your first project and assign it to yourself or a teammate.</p>
        ) : (
          <form onSubmit={assign}>
            <div className="form-group">
              <label className="form-label" htmlFor="assignment-project">Project</label>
              <select id="assignment-project" className="form-input" required value={projectId}
                disabled={saving} onChange={e => setProjectId(e.target.value)}>
                <option value="">Choose a project</option>
                {options.projects.map(p => <option key={p.id} value={p.id}>{p.name} — {p.domain}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="assignment-user">Assign to</label>
              <select id="assignment-user" className="form-input" required value={userId}
                disabled={saving} onChange={e => setUserId(e.target.value)}>
                <option value="">Choose a team member</option>
                {options.users.map(u => <option key={u.id} value={u.id}>{u.email}{u.id === user?.id ? ' (you)' : ''}</option>)}
              </select>
            </div>
            {project && (
              <p role="status">
                {alreadyAssigned
                  ? `Currently assigned to ${assignee?.email || 'another user'}. Unassign the current user before assigning this project again.`
                  : 'This project is currently unassigned.'}
              </p>
            )}
            <div className="modal-actions">
              <Link className="btn btn-secondary" to="/admin/clients">My assigned projects</Link>
              {alreadyAssigned && (
                <button className="btn btn-secondary" type="button" disabled={saving} onClick={() => void unassign()}>
                  Unassign
                </button>
              )}
              <button className="btn btn-primary" type="submit" disabled={saving || !projectId || !userId || alreadyAssigned}>
                {saving ? 'Saving…' : 'Assign Project'}
              </button>
            </div>
          </form>
        )}
      </section>
    </Page>
  );
}
