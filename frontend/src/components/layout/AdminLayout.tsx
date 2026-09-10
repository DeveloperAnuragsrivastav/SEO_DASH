import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Menu, Moon, Sun } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { applyTheme, resolvedTheme, type Theme } from '../../lib/theme';

/** Slim label for the top bar, derived from the route — no extra fetches. */
function sectionLabel(pathname: string): string {
  if (pathname.startsWith('/admin/users')) return 'Manager Directory';
  if (pathname.startsWith('/admin/manager-tools')) return 'Team & Assignments';
  if (pathname.includes('/connections')) return 'Connections';
  if (pathname.includes('/manual-entry') || pathname.includes('/manual-metrics')) return 'Data Ingestion';
  if (pathname.includes('/keywords')) return 'Keyword Performance';
  if (pathname.includes('/ai-mentions-data')) return 'AI Prompts Tracking';
  if (pathname.includes('/ai-prompts')) return 'AI Prompts';
  if (pathname.includes('/gbp')) return 'GBP Data';
  if (pathname.includes('/google-analytics')) return 'Google Analytics';
  if (pathname.includes('/search-console')) return 'Search Console';
  if (pathname.includes('/links')) return 'Backlinks Activities';
  if (pathname.includes('/work')) return 'On-Site SEO Activities';
  if (pathname.includes('/screenshots')) return 'Screenshots';
  if (/^\/admin\/clients\/[^/]+$/.test(pathname)) return 'Client Overview';
  if (pathname.startsWith('/admin/clients')) return 'Clients';
  return 'Dashboard';
}

export function AdminLayout() {
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);
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
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />

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
            <div className="topbar-context">
              <strong>{sectionLabel(location.pathname)}</strong>
            </div>
          </div>

          <div className="topbar-right">
            <button
              className="icon-btn"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            >
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
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
