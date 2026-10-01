import { useEffect, useState } from 'react';
import { Outlet, useLocation, useParams, Link } from 'react-router-dom';
import { ErrorBoundary } from '../ErrorBoundary';
import { Menu, Moon, Sun } from 'lucide-react';
import GlobalSearch from './GlobalSearch';
import { useAuth } from '../../context/AuthContext';
import { Sidebar } from './Sidebar';
import { applyTheme, resolvedTheme, type Theme } from '../../lib/theme';
import api from '../../api/client';
import { screen, screenForPath } from '../../lib/nav';

interface Crumb {
  label: string;
  href?: string;
}

/** Where you are, from the nav manifest — the same names the sidebar and the
 *  page heading use, so the trail can never call a screen something else. */
function trailFor(pathname: string, clientId?: string, clientName?: string | null): Crumb[] {
  const here = screenForPath(pathname, clientId);
  const crumbs: Crumb[] = [{ label: 'Clients', href: '/admin/clients' }];

  if (clientId) {
    crumbs.push({
      label: clientName || 'Client',
      href: screen('overview')!.path(clientId),
    });
  }

  if (!here) return crumbs;

  // A screen that sits under another shows its parent first.
  if (here.parent) {
    const parent = screen(here.parent);
    if (parent && parent.key !== 'overview') {
      crumbs.push({ label: parent.name, href: parent.path(clientId) });
    }
  }

  // The client's own overview is already named by the client crumb.
  if (!(clientId && here.key === 'overview') && here.key !== 'clients') {
    crumbs.push({ label: here.name });
  }

  return crumbs;
}

export function AdminLayout() {
  const location = useLocation();
  const { clientId } = useParams();
  const { user } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  const [clientName, setClientName] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('ez-nav-collapsed') === '1'; } catch { return false; }
  });

  const toggleCollapsed = () => {
    setCollapsed(c => {
      const next = !c;
      try { localStorage.setItem('ez-nav-collapsed', next ? '1' : '0'); } catch { /* storage unavailable */ }
      return next;
    });
  };
  const [theme, setTheme] = useState<Theme>(() => resolvedTheme());

  // Fetched once here and handed to both the trail and the sidebar.
  useEffect(() => {
    if (!clientId) { setClientName(null); return; }
    let live = true;
    api.get(`/clients/${clientId}`, { skipErrorToast: true } as never)
      .then(res => { if (live) setClientName(res.data.name); })
      .catch(() => { if (live) setClientName(null); });
    return () => { live = false; };
  }, [clientId]);

  // Never leave the mobile drawer hanging open across navigations.
  useEffect(() => { setNavOpen(false); }, [location.pathname]);

  const toggleTheme = () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    applyTheme(next);
  };

  const crumbs = trailFor(location.pathname, clientId, clientName);

  return (
    <div className="app-layout">
      <Sidebar
        open={navOpen}
        onClose={() => setNavOpen(false)}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
        clientName={clientName}
      />

      <div className="app-main">
        <header className="app-header">
          <div className="topbar-left">
            <button
              className="icon-btn nav-toggle"
              onClick={() => setNavOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={18} />
            </button>
            <nav className="trail" aria-label="Breadcrumb">
              {crumbs.map((c, i) => (
                <span key={`${c.label}-${i}`} className="trail-item">
                  {i > 0 && <span className="trail-sep" aria-hidden="true">/</span>}
                  {c.href && i < crumbs.length - 1 ? (
                    <Link to={c.href} className="trail-link">{c.label}</Link>
                  ) : (
                    <span className="trail-current" aria-current="page">{c.label}</span>
                  )}
                </span>
              ))}
            </nav>
          </div>

          <div className="topbar-right">
            <GlobalSearch />
            <button
              className="icon-btn"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            >
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <span className="avatar" title={user?.email}>
              {(user?.email || '?').slice(0, 2)}
            </span>
          </div>
        </header>

        <main className="app-content">
          <div className="content-max-width">
            <ErrorBoundary variant="page" resetKey={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}
