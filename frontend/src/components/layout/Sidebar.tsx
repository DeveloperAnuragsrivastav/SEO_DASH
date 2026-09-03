import { NavLink, useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { usePermissions } from '../../hooks/usePermissions';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import api from '../../api/client';
import { 
  Building2, 
  Users, 
  Kanban, 
  LayoutDashboard, 
  Inbox, 
  Crosshair, 
  Bot, 
  BarChart2, 
  MapPin, 
  TrendingUp, 
  Search, 
  Link as LinkIcon, 
  CheckSquare, 
  Image as ImageIcon, 
  Plug,
  Zap
} from 'lucide-react';

export function Sidebar() {
  const { user, logout } = useAuth();
  const { canViewAdminTools, isSuperAdmin, isManager } = usePermissions();
  const { clientId } = useParams();
  const [clientName, setClientName] = useState<string | null>(null);
  
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  
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

  return (
    <aside className="app-sidebar">
      <div className="sidebar-header" style={{ padding: '24px 20px' }}>
        <img src="/logo6.png" alt="EZ Insights" style={{ width: '160px', height: 'auto', objectFit: 'contain' }} />
      </div>

      <nav className="sidebar-nav">
        {/* Global Navigation */}
        <div className="nav-section-title">Agency</div>
        {!isSuperAdmin && (
          <NavLink to="/admin/clients" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Building2 size={16} color="#3b82f6" /> {isManager ? 'My Clients' : 'Assigned Clients'}
          </NavLink>
        )}
        {canViewAdminTools && (
          <NavLink to="/admin/users" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Users size={16} color="#6366f1" /> Managers
          </NavLink>
        )}
        {isManager && (
          <NavLink to="/admin/manager-tools" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Kanban size={16} color="#8b5cf6" /> Team & Assignments
          </NavLink>
        )}

        {/* Client Contextual Navigation */}
        {clientId && (
          <>
            <div className="nav-section-title" style={{ marginTop: '32px' }}>
              {clientName || 'Loading Client...'}
            </div>
            
            <NavLink to={`/admin/clients/${clientId}`} end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <LayoutDashboard size={16} color="#14b8a6" /> Overview
            </NavLink>

            <NavLink to={`/admin/clients/${clientId}/manual-entry`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Inbox size={16} color="#6b7280" /> Data Ingestion
            </NavLink>
            <NavLink to={`/clients/${clientId}/keywords`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Crosshair size={16} color="#eab308" /> Keyword Performance
            </NavLink>
            <NavLink to={`/clients/${clientId}/ai-mentions-data`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <BarChart2 size={16} color="#8b5cf6" /> Target AI Prompts Tracking & Performance
            </NavLink>
            <NavLink to={`/clients/${clientId}/gbp`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <MapPin size={16} color="#ef4444" /> GBP Data
            </NavLink>
            <NavLink to={`/clients/${clientId}/google-analytics`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <TrendingUp size={16} color="#f97316" /> Google Analytics
            </NavLink>
            <NavLink to={`/clients/${clientId}/search-console`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Search size={16} color="#10b981" /> Search Console
            </NavLink>
            <NavLink to={`/clients/${clientId}/links`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <LinkIcon size={16} color="#06b6d4" /> Performed Backlinks Activities
            </NavLink>
            <NavLink to={`/clients/${clientId}/work`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <CheckSquare size={16} color="#22c55e" /> On-Site SEO Activities Performed
            </NavLink>
            <NavLink to={`/clients/${clientId}/screenshots`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <ImageIcon size={16} color="#ec4899" /> Screenshots
            </NavLink>
            {user?.role !== 'user' && (
              <NavLink to={`/admin/clients/${clientId}/connections`} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                <Plug size={16} color="#94a3b8" /> Connections
              </NavLink>
            )}

          </>
        )}
      </nav>

      <div style={{ padding: '20px 16px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
        <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '2px', color: '#fff', textTransform: 'capitalize' }}>
          {user?.email ? user.email.split('@')[0] : ''}
        </div>
        <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)', marginBottom: '16px', letterSpacing: '0.05em' }}>
          {user?.role.replace('_', ' ').toUpperCase()}
        </div>
        <button className="btn sidebar-btn" style={{ width: '100%', marginBottom: '8px' }} onClick={() => setShowPasswordModal(true)}>Change Password</button>
        <button className="btn sidebar-btn-danger" style={{ width: '100%' }} onClick={logout}>Sign Out</button>
      </div>

      {showPasswordModal && (
        <div className="overlay on" style={{ display: 'grid', placeItems: 'center', zIndex: 1000 }}>
          <div className="card" style={{ width: '100%', maxWidth: 400 }}>
            <div className="card-body">
              <h3 style={{ fontSize: 18, marginBottom: 16 }}>Change Password</h3>
              <form onSubmit={handlePasswordSubmit} style={{ display: 'grid', gap: 12 }}>
                <div className="form-group">
                  <label className="form-label">Current Password</label>
                  <input 
                    type="password" 
                    required 
                    value={passwordForm.current_password}
                    onChange={e => setPasswordForm({...passwordForm, current_password: e.target.value})}
                    className="form-input"
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
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
                  <button type="button" onClick={() => setShowPasswordModal(false)} className="btn btn-secondary">Cancel</button>
                  <button type="submit" className="btn btn-primary">Update Password</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
