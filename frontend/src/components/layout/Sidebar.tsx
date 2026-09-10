import { NavLink, useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { usePermissions } from '../../hooks/usePermissions';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import api from '../../api/client';
import {
  Building2,
  Users,
  Kanban,
  LayoutDashboard,
  Inbox,
  Crosshair,
  BarChart2,
  MapPin,
  TrendingUp,
  Search,
  Link as LinkIcon,
  CheckSquare,
  Image as ImageIcon,
  Plug,
  MoreHorizontal,
  KeyRound,
  LogOut,
  X,
} from 'lucide-react';

interface SidebarProps {
  /** Mobile drawer visibility — desktop ignores this. */
  open?: boolean;
  onClose?: () => void;
}

export function Sidebar({ open = false, onClose }: SidebarProps) {
  const { user, logout } = useAuth();
  const { canViewAdminTools, isSuperAdmin, isManager } = usePermissions();
  const { clientId } = useParams();
  const [clientName, setClientName] = useState<string | null>(null);

  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ current_password: '', new_password: '', confirm_password: '' });

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error('New passwords do not match');
      return;
    }
    try {
      await api.put('/auth/change-password', {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password
      });
      toast.success('Password updated successfully');
      setShowPasswordModal(false);
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update password');
    }
  };

  useEffect(() => {
    if (clientId) {
      api.get(`/clients/${clientId}`).then((res) => {
        setClientName(res.data.name);
      }).catch(() => setClientName(null));
    } else {
      setClientName(null);
    }
  }, [clientId]);

  // Close the account menu on outside click / Escape
  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const displayName = user?.email ? user.email.split('@')[0] : '';
  const initials = displayName.slice(0, 2);
  const navCls = ({ isActive }: { isActive: boolean }) => `nav-item ${isActive ? 'active' : ''}`;
  const closeDrawer = () => onClose?.();

  return (
    <>
      {/* Scrim — mobile drawer only */}
      <div
        className={`sidebar-scrim ${open ? 'open' : ''}`}
        onClick={closeDrawer}
        aria-hidden="true"
      />

      <aside className={`app-sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-header">
          <img src="/logo6.png" alt="EZ Insights" className="sidebar-logo" />
          <button className="icon-btn sidebar-close" onClick={closeDrawer} aria-label="Close navigation">
            <X size={17} />
          </button>
        </div>

        <nav className="sidebar-nav">
          {/* Global Navigation */}
          <div className="nav-section-title">Agency</div>
          {!isSuperAdmin && (
            <NavLink to="/admin/clients" end className={navCls} onClick={closeDrawer}>
              <Building2 size={16} /> <span>{isManager ? 'My Clients' : 'Assigned Clients'}</span>
            </NavLink>
          )}
          {canViewAdminTools && (
            <NavLink to="/admin/users" className={navCls} onClick={closeDrawer}>
              <Users size={16} /> <span>Managers</span>
            </NavLink>
          )}
          {isManager && (
            <NavLink to="/admin/manager-tools" className={navCls} onClick={closeDrawer}>
              <Kanban size={16} /> <span>Team &amp; Assignments</span>
            </NavLink>
          )}

          {/* Client Contextual Navigation */}
          {clientId && (
            <>
              <div className="nav-section-title" title={clientName || undefined}>
                {clientName || 'Loading Client…'}
              </div>

              <NavLink to={`/admin/clients/${clientId}`} end className={navCls} onClick={closeDrawer}>
                <LayoutDashboard size={16} /> <span>Overview</span>
              </NavLink>

              <NavLink to={`/admin/clients/${clientId}/manual-entry`} className={navCls} onClick={closeDrawer}>
                <Inbox size={16} /> <span>Data Ingestion</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/keywords`} className={navCls} onClick={closeDrawer}>
                <Crosshair size={16} /> <span>Keyword Performance</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/ai-mentions-data`} className={navCls} onClick={closeDrawer}>
                <BarChart2 size={16} /> <span>Target AI Prompts Tracking &amp; Performance</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/gbp`} className={navCls} onClick={closeDrawer}>
                <MapPin size={16} /> <span>GBP Data</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/google-analytics`} className={navCls} onClick={closeDrawer}>
                <TrendingUp size={16} /> <span>Google Analytics</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/search-console`} className={navCls} onClick={closeDrawer}>
                <Search size={16} /> <span>Search Console</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/links`} className={navCls} onClick={closeDrawer}>
                <LinkIcon size={16} /> <span>Performed Backlinks Activities</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/work`} className={navCls} onClick={closeDrawer}>
                <CheckSquare size={16} /> <span>On-Site SEO Activities Performed</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/screenshots`} className={navCls} onClick={closeDrawer}>
                <ImageIcon size={16} /> <span>Screenshots</span>
              </NavLink>
              {user?.role !== 'user' && (
                <NavLink to={`/admin/clients/${clientId}/connections`} className={navCls} onClick={closeDrawer}>
                  <Plug size={16} /> <span>Connections</span>
                </NavLink>
              )}
            </>
          )}
        </nav>

        {/* Account */}
        <div className="sidebar-footer" ref={menuRef}>
          {menuOpen && (
            <div className="account-menu" role="menu">
              <button
                className="account-menu-item"
                role="menuitem"
                onClick={() => { setMenuOpen(false); setShowPasswordModal(true); }}
              >
                <KeyRound size={15} /> Change Password
              </button>
              <button
                className="account-menu-item danger"
                role="menuitem"
                onClick={logout}
              >
                <LogOut size={15} /> Sign Out
              </button>
            </div>
          )}

          <button
            className={`account-trigger ${menuOpen ? 'on' : ''}`}
            onClick={() => setMenuOpen(v => !v)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <span className="avatar avatar-dark">{initials}</span>
            <span className="account-meta">
              <span className="account-name">{displayName}</span>
              <span className="account-role">{user?.role.replace('_', ' ').toUpperCase()}</span>
            </span>
            <MoreHorizontal size={16} className="account-caret" />
          </button>
        </div>
      </aside>

      {showPasswordModal && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowPasswordModal(false); }}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Change Password">
            <h2 className="modal-title">Change Password</h2>
            <p className="modal-desc">Use at least 8 characters. You'll stay signed in on this device.</p>
            <form onSubmit={handlePasswordSubmit}>
              <div className="form-group">
                <label className="form-label">Current Password</label>
                <input
                  type="password"
                  required
                  value={passwordForm.current_password}
                  onChange={e => setPasswordForm({...passwordForm, current_password: e.target.value})}
                  className="form-input"
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label className="form-label">New Password</label>
                <input
                  type="password"
                  required
                  value={passwordForm.new_password}
                  onChange={e => setPasswordForm({...passwordForm, new_password: e.target.value})}
                  className="form-input"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Confirm New Password</label>
                <input
                  type="password"
                  required
                  value={passwordForm.confirm_password}
                  onChange={e => setPasswordForm({...passwordForm, confirm_password: e.target.value})}
                  className="form-input"
                />
              </div>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowPasswordModal(false)} className="btn btn-secondary">Cancel</button>
                <button type="submit" className="btn btn-primary">Update Password</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
