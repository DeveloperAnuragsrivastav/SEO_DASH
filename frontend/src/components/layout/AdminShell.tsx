import { Link } from "react-router-dom";
import type { ReactNode } from "react";

import { AdminSidebar } from "./AdminSidebar";

export function AdminShell({
  breadcrumb,
  title,
  subtitle,
  actions,
  backLink,
  children,
}: {
  breadcrumb: ReactNode;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  backLink?: { to: string; label: string };
  children: ReactNode;
}) {
  return (
    <>
      <header className="sticky top-0 z-20 flex h-[52px] items-center gap-2 border-b border-border bg-background/85 px-8 backdrop-blur">
        <Link to="/admin/clients" className="text-sm text-muted-foreground hover:text-foreground">
          Admin Panel
        </Link>
        <span className="text-xs text-muted-foreground">/</span>
        <span className="truncate text-sm font-semibold">{breadcrumb}</span>
      </header>

      <div className="mx-auto w-full max-w-[1240px] px-8 py-7">
        {backLink && (
          <Link
            to={backLink.to}
            className="mb-5 inline-block font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground transition-colors hover:text-foreground"
          >
            ← {backLink.label}
          </Link>
        )}

        <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-border pb-6">
          <div className="min-w-0">
            <h1 className="text-balance font-serif text-4xl leading-[1.05] tracking-tight">
              {title}
            </h1>
            {subtitle && <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>

        <div className="space-y-8 pb-16">{children}</div>
      </div>
    </>
  );
}
