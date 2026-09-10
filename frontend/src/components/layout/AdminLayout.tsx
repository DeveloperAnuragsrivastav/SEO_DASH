import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Menu, Moon, Sun } from 'lucide-react';
import GlobalSearch from './GlobalSearch';
import { useAuth } from '../../context/AuthContext';
import { Sidebar } from './Sidebar';
import { applyTheme, resolvedTheme, type Theme } from '../../lib/theme';

/** Page identity for the top bar, derived from the route — no extra fetches. */
function pageIdentity(pathname: string): { title: string; subtitle: string } {
  const p = (title: string, subtitle: string) => ({ title, subtitle });

  if (pathname.startsWith('/admin/users')) return p('Manager Directory', 'Create and oversee isolated manager accounts.');
  if (pathname.startsWith('/admin/manager-tools')) return p('Team & Assignments', 'Manage your team and who works on what.');
  if (pathname.includes('/reports/')) return p('Client Report', 'Review and publish what the client will see.');
  if (pathname.includes('/connections')) return p('Connections', 'Link Google properties to pull data automatically.');
  if (pathname.includes('/manual-entry') || pathname.includes('/manual-metrics')) return p('Add Data', 'Everything this month’s report is built from.');
  if (pathname.includes('/keywords')) return p('Keyword Performance', 'Track how target keywords are moving.');
  if (pathname.includes('/ai-mentions-data')) return p('AI Prompts Tracking', 'See where AI tools mention this brand.');
  if (pathname.includes('/ai-prompts')) return p('AI Prompts', 'Prompts monitored for brand mentions.');
  if (pathname.includes('/gbp')) return p('GBP Data', 'Google Business Profile calls, directions and clicks.');
  if (pathname.includes('/google-analytics')) return p('Google Analytics', 'Sessions, users and conversions over time.');
  if (pathname.includes('/search-console')) return p('Search Console', 'Clicks, impressions and average position.');
  if (pathname.includes('/links')) return p('Backlinks', 'Links built for this client.');
  if (pathname.includes('/work')) return p('On-Site SEO Activities', 'Work delivered on the site.');
  if (pathname.includes('/screenshots')) return p('Screenshots', 'Evidence attached to the report.');
  if (/^\/admin\/clients\/[^/]+$/.test(pathname)) return p('Client Overview', 'Track performance, monitor progress, and grow together.');
  if (pathname.startsWith('/admin/clients')) return p('Clients', 'Every project you are responsible for.');
  return p('Dashboard', 'Your agency at a glance.');
}

export function AdminLayout() {
  const location = useLocation();
  const { user } = useAuth();
  const page = pageIdentity(location.pathname);
  const [navOpen, setNavOpen] = useState(false);
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

  // Never leave the mobile drawer hanging open across navigations.
  useEffect(() => { setNavOpen(false); }, [location.pathname]);

  const toggleTheme = () => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    applyTheme(next);
  };

  return (
    <div className="app-layout">
      <Sidebar
        open={navOpen}
        onClose={() => setNavOpen(false)}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
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
            <div className="topbar-identity">
              <strong>{page.title}</strong>
              <span className="hide-s">{page.subtitle}</span>
            </div>
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
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
