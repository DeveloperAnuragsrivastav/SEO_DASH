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
  ChevronLeft,
  KeyRound,
  LogOut,
  X,
} from 'lucide-react';

interface SidebarProps {
  /** Mobile drawer visibility — desktop ignores this. */
  open?: boolean;
  onClose?: () => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}

export function Sidebar({ open = false, onClose, collapsed = false, onToggleCollapsed }: SidebarProps) {
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

      <aside className={`app-sidebar ${open ? 'open' : ''} ${collapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <img src="/logo6.png" alt="EZ Insights" className="sidebar-logo" />
          <button
            className="sidebar-collapse hide-s"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            <ChevronLeft size={15} />
          </button>
          <button className="icon-btn sidebar-close" onClick={closeDrawer} aria-label="Close navigation">
            <X size={17} />
          </button>
        </div>

        <nav className="sidebar-nav">
          {/* Global Navigation */}
          <div className="nav-section-title">Agency</div>
          {!isSuperAdmin && (
            <NavLink to="/admin/clients" end className={navCls} onClick={closeDrawer}>
              <span className="nav-ico"><Building2 size={15} /></span> <span className="nav-text">{isManager ? 'My Clients' : 'Assigned Clients'}</span>
            </NavLink>
          )}
          {canViewAdminTools && (
            <NavLink to="/admin/users" className={navCls} onClick={closeDrawer}>
              <span className="nav-ico"><Users size={15} /></span> <span className="nav-text">Managers</span>
            </NavLink>
          )}
          {isManager && (
            <NavLink to="/admin/manager-tools" className={navCls} onClick={closeDrawer}>
              <span className="nav-ico"><Kanban size={15} /></span> <span className="nav-text">Team &amp; Assignments</span>
            </NavLink>
          )}

          {/* Client Contextual Navigation */}
          {clientId && (
            <>
              <div className="nav-section-title" title={clientName || undefined}>
                {clientName || 'Loading Client…'}
              </div>

              <NavLink to={`/admin/clients/${clientId}`} end className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><LayoutDashboard size={15} /></span> <span className="nav-text">Overview</span>
              </NavLink>

              <NavLink to={`/admin/clients/${clientId}/manual-entry`} className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><Inbox size={15} /></span> <span className="nav-text">Data Ingestion</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/keywords`} className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><Crosshair size={15} /></span> <span className="nav-text">Keyword Performance</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/ai-mentions-data`} className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><BarChart2 size={15} /></span> <span className="nav-text">Target AI Prompts Tracking &amp; Performance</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/gbp`} className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><MapPin size={15} /></span> <span className="nav-text">GBP Data</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/google-analytics`} className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><TrendingUp size={15} /></span> <span className="nav-text">Google Analytics</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/search-console`} className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><Search size={15} /></span> <span className="nav-text">Search Console</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/links`} className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><LinkIcon size={15} /></span> <span className="nav-text">Performed Backlinks Activities</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/work`} className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><CheckSquare size={15} /></span> <span className="nav-text">On-Site SEO Activities Performed</span>
              </NavLink>
              <NavLink to={`/clients/${clientId}/screenshots`} className={navCls} onClick={closeDrawer}>
                <span className="nav-ico"><ImageIcon size={15} /></span> <span className="nav-text">Screenshots</span>
              </NavLink>
              {user?.role !== 'user' && (
                <NavLink to={`/admin/clients/${clientId}/connections`} className={navCls} onClick={closeDrawer}>
                  <span className="nav-ico"><Plug size={15} /></span> <span className="nav-text">Connections</span>
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
