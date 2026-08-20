import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import api from '../../api/client';
import LoadingSpinner from '../../components/LoadingSpinner';
import { Navigate } from 'react-router-dom';
import { toast } from 'sonner';
import { AdminShell } from '../../components/layout/AdminShell';
import {
  Bento,
  StatCard,
  StatusPill,
  TablePanel,
  Td,
  Th,
  btnPrimary,
  btnGhost,
  inputCls
} from '../../components/kit';

interface User {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  last_login_at: string | null;
}

export default function Users() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Modals state
  const [showAdd, setShowAdd] = useState(false);
  const [newUser, setNewUser] = useState({ email: '', password: '', role: 'agency_staff' });
  const [error, setError] = useState('');
  const [userToDeactivate, setUserToDeactivate] = useState<string | null>(null);

  const loadUsers = async () => {
    try {
      const res = await api.get('/users');
      setUsers(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.role === 'agency_admin') {
      loadUsers();
    }
  }, [user]);

  if (user?.role !== 'agency_admin') {
    return <Navigate to="/" replace />;
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/users', newUser);
      setShowAdd(false);
      setNewUser({ email: '', password: '', role: 'agency_staff' });
      setError('');
      toast.success('User created successfully');
      loadUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleToggleRole = async (userId: string, currentRole: string) => {
    const newRole = currentRole === 'agency_admin' ? 'agency_staff' : 'agency_admin';
    try {
      await api.put(`/users/${userId}/role`, { role: newRole });
      toast.success(`Role updated`);
      loadUsers();
    } catch (err) {
      toast.error('Failed to update role');
      console.error(err);
    }
  };

  const confirmDeactivate = async () => {
    if (!userToDeactivate) return;
    try {
      await api.put(`/users/${userToDeactivate}/deactivate`);
      setUserToDeactivate(null);
      toast.success('User deactivated');
      loadUsers();
    } catch (err) {
      toast.error('Failed to deactivate user');
      console.error(err);
    }
  };

  const active = users.filter((u) => u.is_active).length;

  if (loading) return <AdminShell breadcrumb="Loading..." title="Loading..."><div className="flex h-64 items-center justify-center"><LoadingSpinner label="Loading users…" /></div></AdminShell>;

  return (
    <AdminShell
      breadcrumb="Users"
      title="User Management"
      subtitle="Agency admins and staff with access to client accounts and monthly reports."
      actions={
        <button
          type="button"
          className={btnPrimary}
          onClick={() => setShowAdd(true)}
        >
          Add User
        </button>
      }
    >
      <Bento>
        <StatCard label="Total Users" value={users.length} source="Agency · live" />
        <StatCard label="Active" value={active} source="Agency · live" />
        <StatCard label="Deactivated" value={users.length - active} source="Agency · live" />
        <StatCard
          label="Agency Admins"
          value={users.filter((u) => u.role === "agency_admin").length}
          source="Agency · live"
        />
      </Bento>

      <TablePanel
        title="Agency Users"
        head={
          <>
            <Th>Email</Th>
            <Th>Role</Th>
            <Th>Status</Th>
            <Th>Last Login</Th>
            <Th align="right">Actions</Th>
          </>
        }
      >
        {users.map((u) => (
          <tr key={u.id} className="transition-colors hover:bg-secondary">
            <Td>
              <span className="font-medium">{u.email}</span>
            </Td>
            <Td>
              <span
                className={
                  u.role === "agency_admin"
                    ? "rounded-full bg-brand px-2.5 py-0.5 text-[11px] font-semibold text-ink uppercase"
                    : "rounded-full bg-secondary px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground uppercase"
                }
              >
                {u.role.replace('_', ' ')}
              </span>
            </Td>
            <Td>
              <StatusPill status={u.is_active ? "Active" : "Deactivated"} />
            </Td>
            <Td className="font-mono text-xs text-muted-foreground">
              {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Never'}
            </Td>
            <Td align="right">
              <div className="flex justify-end gap-2">
                {u.is_active && user?.id !== u.id && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleToggleRole(u.id, u.role)}
                      className="rounded-full border border-border px-3 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {u.role === "agency_admin" ? "Make Staff" : "Make Admin"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setUserToDeactivate(u.id)}
                      className="px-2 py-1 text-[11px] font-medium text-status-churned-text hover:underline"
                    >
                      Deactivate
                    </button>
                  </>
                )}
              </div>
            </Td>
          </tr>
        ))}
      </TablePanel>

      {showAdd && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-[0_12px_24px_-4px_rgba(0,0,0,0.15)]">
            <h2 className="mb-4 font-serif text-xl">Add New User</h2>
            {error && <div className="mb-4 rounded border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">{error}</div>}
            <form onSubmit={handleAdd} className="flex flex-col gap-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Email</label>
                <input 
                  type="email" 
                  required 
                  value={newUser.email}
                  onChange={e => setNewUser({...newUser, email: e.target.value})}
                  className={inputCls}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Temporary Password</label>
                <input 
                  type="text" 
                  required 
                  value={newUser.password}
                  onChange={e => setNewUser({...newUser, password: e.target.value})}
                  className={inputCls}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Role</label>
                <select 
                  value={newUser.role}
                  onChange={e => setNewUser({...newUser, role: e.target.value})}
                  className={inputCls}
                >
                  <option value="agency_staff">Agency Staff</option>
                  <option value="agency_admin">Agency Admin</option>
                </select>
              </div>
              <div className="mt-2 flex justify-end gap-2">
                <button type="button" onClick={() => setShowAdd(false)} className={btnGhost}>Cancel</button>
                <button type="submit" className={btnPrimary}>Create User</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {userToDeactivate && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-[0_12px_24px_-4px_rgba(0,0,0,0.15)]">
            <h2 className="mb-4 font-serif text-xl text-status-churned-text">Deactivate User</h2>
            <p className="mb-6 text-sm text-muted-foreground">
              Are you sure you want to deactivate this user? They will immediately lose access and be logged out.
            </p>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setUserToDeactivate(null)} className={btnGhost}>Cancel</button>
              <button type="button" onClick={confirmDeactivate} className="inline-flex items-center gap-2 rounded-md bg-status-churned-text px-4 py-2 text-sm font-medium text-white transition-all hover:brightness-95">
                Yes, Deactivate
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminShell>
  );
}
