import { NavLink as RouterNavLink, Link, useLocation } from "react-router-dom";
import {
  Store,
  Users,
  BarChart3,
  TrendingUp,
  Search,
  Sparkles,
  Link2,
  Gauge,
  Plug,
  Settings,
  Bot,
  LogOut,
} from "lucide-react";
import type { ReactNode } from "react";
import { useAuth } from "../../context/AuthContext";

import { useEffect, useState } from "react";
import api from "../../api/client";

function SectionLabel({ children }: { children: string }) {
  return (
    <h3 className="mb-3 px-3 font-mono text-[10px] uppercase tracking-[0.12em] sidebar-text-subtle">
      {children}
    </h3>
  );
}

function NavLink({ to, icon, label }: { to: string; icon: ReactNode; label: string }) {
  return (
    <RouterNavLink
      to={to}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors ${isActive ? "sidebar-nav-link-active" : "sidebar-nav-link"
        }`
      }
    >
      <span className="shrink-0 opacity-80 [&_svg]:size-4">{icon}</span>
      <span className="truncate">{label}</span>
    </RouterNavLink>
  );
}

export function AdminSidebar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const pathname = location.pathname;
  const match = pathname.match(/clients\/([^/]+)/);
  const clientId = match?.[1];

  const [clients, setClients] = useState<any[]>([]);
  const [client, setClient] = useState<any>(null);

  useEffect(() => {
    api.get("/clients").then((res) => {
      setClients(res.data || []);
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (clientId) {
      api.get(`/clients/${clientId}`).then((res) => setClient(res.data)).catch(console.error);
    } else {
      setClient(null);
    }
  }, [clientId]);

  const currentMonth = new Date().toISOString().slice(0, 7);
  const formattedMonth = new Date(currentMonth + '-01').toLocaleString('default', { month: 'long', year: 'numeric' });

  return (
    <aside className="sticky top-0 flex h-screen w-[252px] shrink-0 flex-col border-r border-white/[0.06] bg-sidebar text-sidebar-foreground">
      <div className="p-6">
        <Link to="/" className="flex items-center gap-3">
          <span className="flex size-8 items-center justify-center rounded-full bg-brand font-serif text-lg italic leading-none text-ink">
            EZ
          </span>
          <span className="text-[17px] font-extrabold tracking-[-0.03em] text-sidebar-foreground">
            EZ Rankings
          </span>
        </Link>
      </div>

      <nav className="flex-1 space-y-7 overflow-y-auto px-3 pb-6">
        {client ? (
          <>
            <div className="rounded-lg bg-white/[0.05] p-3">
              <p className="truncate text-sm font-bold text-sidebar-foreground">{client.name}</p>
              <p className="truncate text-[11px] sidebar-text-faint">{client.domain}</p>
              <span className="mt-2 inline-flex rounded-full bg-brand/20 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.06em] text-brand">
                {client.status}
              </span>
            </div>

            <section>
              <SectionLabel>Reports</SectionLabel>
              <div className="space-y-0.5">
                <NavLink
                  to={`/clients/${client.id}/reports/${currentMonth}/overview`}
                  icon={<BarChart3 />}
                  label="Overview"
                />
                <NavLink
                  to={`/clients/${client.id}/reports/${currentMonth}/rankings`}
                  icon={<TrendingUp />}
                  label="Rankings"
                />
                <NavLink
                  to={`/clients/${client.id}/reports/${currentMonth}/search`}
                  icon={<Search />}
                  label="Search Performance"
                />
                <NavLink
                  to={`/clients/${client.id}/reports/${currentMonth}/audience`}
                  icon={<Users />}
                  label="Audience"
                />
                <NavLink
                  to={`/clients/${client.id}/reports/${currentMonth}/ai-visibility`}
                  icon={<Sparkles />}
                  label="AI Visibility"
                />
                <NavLink
                  to={`/clients/${client.id}/reports/${currentMonth}/links`}
                  icon={<Link2 />}
                  label="Links"
                />
                <NavLink
                  to={`/clients/${client.id}/reports/${currentMonth}/work`}
                  icon={<Gauge />}
                  label="Work Done"
                />
              </div>
            </section>

            <div className="mx-3 h-px bg-white/[0.08]" />

            <section>
              <SectionLabel>Configuration</SectionLabel>
              <div className="space-y-0.5">
                <NavLink
                  to={`/admin/clients/${client.id}/connections`}
                  icon={<Plug />}
                  label="Connections"
                />
                <NavLink
                  to={`/clients/${client.id}/keywords`}
                  icon={<Settings />}
                  label="Keywords"
                />
                <NavLink
                  to={`/clients/${client.id}/ai-prompts`}
                  icon={<Bot />}
                  label="AI Prompts"
                />
              </div>
            </section>
          </>
        ) : (
          <>
            <section>
              <SectionLabel>Agency</SectionLabel>
              <div className="space-y-0.5">
                <NavLink to="/admin/clients" icon={<Store />} label="All Clients" />
                {user?.role === 'agency_admin' && (
                  <NavLink to="/admin/users" icon={<Users />} label="Users" />
                )}
              </div>
            </section>

            <section>
              <SectionLabel>Jump to client</SectionLabel>
              <div className="space-y-0.5">
                {clients.map((c: any) => (
                  <Link
                    key={c.id}
                    to={`/admin/clients/${c.id}`}
                    className="sidebar-nav-link flex items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors"
                  >
                    <span
                      aria-hidden
                      className={`size-1.5 shrink-0 rounded-full ${c.status?.toLowerCase() === "active"
                          ? "bg-brand"
                          : c.status?.toLowerCase() === "paused"
                            ? "bg-sidebar-foreground opacity-40"
                            : "bg-sidebar-foreground opacity-20"
                        }`}
                    />
                    <span className="min-w-0 flex-1 truncate font-medium text-sidebar-foreground opacity-80">{c.name}</span>
                    <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.06em] text-white opacity-80">
                      {c.package_keywords || 0}
                    </span>
                  </Link>
                ))}
              </div>
            </section>

            <section className="rounded-lg bg-white/[0.05] p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] sidebar-text-subtle">
                Report period
              </p>
              <p className="mt-2 font-serif text-2xl leading-none text-sidebar-foreground">
                {formattedMonth}
              </p>
              <dl className="mt-4 space-y-3 border-t border-white/[0.08] pt-3">
                <div className="flex items-center justify-between text-xs sidebar-text-muted">
                  <span>Active Clients</span>
                  <span className="font-mono font-medium sidebar-text-strong">
                    {clients.filter((c: any) => c.status?.toLowerCase() === "active").length}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs sidebar-text-muted">
                  <span>Total Keywords</span>
                  <span className="font-mono font-medium sidebar-text-strong">
                    {clients.reduce((sum: number, c: any) => sum + (c.package_keywords || 0), 0)}
                  </span>
                </div>
              </dl>
            </section>
          </>
        )}
      </nav>


      <div className="mt-auto border-t border-white/[0.08] p-5">
        <div className="flex items-end justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-xs sidebar-text-muted">{user?.email || "Loading..."}</p>
            <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.08em] text-brand">
              {user?.role?.replace('_', ' ') || "Agency Staff"}
            </p>
          </div>
          <button
            onClick={logout}
            aria-label="Log out"
            className="rounded p-1.5 sidebar-nav-link transition-colors"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
