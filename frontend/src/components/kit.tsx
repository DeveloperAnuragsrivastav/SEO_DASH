import { Pencil, Upload, Plus } from "lucide-react";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

export const btnPrimary =
  "inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2 text-sm font-medium text-ink transition-all hover:brightness-95 active:translate-y-px";
export const btnGhost =
  "inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-secondary active:translate-y-px";
export const btnDanger =
  "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-status-churned-text transition-colors hover:bg-status-churned";
export const inputCls =
  "w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground outline-none transition-shadow placeholder:text-muted-foreground focus:border-ink focus:shadow-[0_0_0_3px_rgba(245,196,0,0.35)]";

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
      {children}
    </span>
  );
}

export function Panel({
  title,
  action,
  children,
  className = "",
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-border bg-card ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-4 border-b border-border px-6 py-4">
          <div className="min-w-0">
            {typeof title === "string" ? (
              <h2 className="truncate font-serif text-xl leading-none">{title}</h2>
            ) : (
              title
            )}
          </div>
          {action}
        </header>
      )}
      <div className="p-6">{children}</div>
    </section>
  );
}

export function SourcePill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded border border-border bg-secondary px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.06em] text-muted-foreground">
      {children}
    </span>
  );
}

export function ManualEntryBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-[#E4CE9A] bg-[#FCEFD2] px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.06em] text-[#7A5B14]">
      <Pencil className="size-2.5" />
      Agency: manual entry
    </span>
  );
}

const STATUS_STYLES: Record<string, string> = {
  Active: "bg-status-active text-status-active-text ring-status-active-text/15",
  Paused: "bg-status-paused text-status-paused-text ring-status-paused-text/15",
  Churned: "bg-status-churned text-status-churned-text ring-status-churned-text/15",
  Deactivated: "bg-status-churned text-status-churned-text ring-status-churned-text/15",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium ring-1 ${
        STATUS_STYLES[status] ?? "bg-secondary text-muted-foreground ring-border"
      }`}
    >
      {status}
    </span>
  );
}

export function StatCard({
  label,
  value,
  source,
  hint,
}: {
  label: string;
  value: ReactNode;
  source?: string;
  hint?: ReactNode;
}) {
  return (
    <div className="flex min-h-[140px] flex-col justify-between bg-card p-6">
      <SectionLabel>{label}</SectionLabel>
      <div className="flex items-baseline gap-2">
        <span className="font-serif text-5xl leading-none">{value}</span>
        {hint}
      </div>
      {source ? <SourcePill>{source}</SourcePill> : <span />}
    </div>
  );
}

import React from "react";

export function Bento({ children }: { children: ReactNode }) {
  const count = React.Children.count(children);
  const mdCols = count === 3 ? "md:grid-cols-3" : "md:grid-cols-4";
  return (
    <div className={`grid grid-cols-2 gap-px overflow-hidden rounded-lg bg-border ring-1 ring-border ${mdCols}`}>
      {children}
    </div>
  );
}

export function Th({
  children,
  align = "left",
}: {
  children?: ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className={`px-6 py-3 font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  align = "left",
  className = "",
}: {
  children?: ReactNode;
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <td
      className={`px-6 py-4 align-middle text-sm ${align === "right" ? "text-right" : ""} ${className}`}
    >
      {children}
    </td>
  );
}

export function DataTable({ head, children }: { head: ReactNode; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-border bg-secondary">{head}</tr>
        </thead>
        <tbody className="divide-y divide-border/60">{children}</tbody>
      </table>
    </div>
  );
}

export function TablePanel({
  title,
  action,
  head,
  children,
  footer,
}: {
  title?: ReactNode;
  action?: ReactNode;
  head: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card">
      {(title || action) && (
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-6 py-4">
          {typeof title === "string" ? (
            <h2 className="font-serif text-xl leading-none">{title}</h2>
          ) : (
            title
          )}
          {action}
        </header>
      )}
      <DataTable head={head}>{children}</DataTable>
      {footer && (
        <div className="flex items-center justify-between border-t border-border px-6 py-3">
          {footer}
        </div>
      )}
    </section>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <div className="size-8 rounded-full border border-dashed border-brand" />
      <p className="text-sm text-muted-foreground">{children}</p>
    </div>
  );
}

export function FilterChips({
  items,
  value,
  onChange,
}: {
  items: string[];
  value?: string;
  onChange?: (item: string) => void;
}) {
  const [internal, setInternal] = useState(items[0] ?? "");
  const active = value ?? internal;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <button
          key={item}
          type="button"
          onClick={() => {
            setInternal(item);
            onChange?.(item);
          }}
          className={
            item === active
              ? "rounded-full bg-brand px-3 py-1 text-[11px] font-medium text-ink"
              : "rounded-full border border-border px-3 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          }
        >
          {item}
        </button>
      ))}
    </div>
  );
}

export function BarRow({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-4">
      <span className="w-20 shrink-0 font-mono text-[11px] uppercase tracking-[0.06em] text-muted-foreground">
        {label}
      </span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 shrink-0 text-right font-serif text-lg leading-none">{value}</span>
    </div>
  );
}

export type FieldSpec = {
  label: string;
  type?: string;
  placeholder?: string;
  defaultValue?: string;
  options?: string[];
  checkbox?: boolean;
};

export function Field({ spec }: { spec: FieldSpec }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-muted-foreground">{spec.label}</span>
      {spec.checkbox ? (
        <input type="checkbox" name={spec.label} defaultChecked className="size-4 accent-[var(--brand)]" />
      ) : spec.options ? (
        <select name={spec.label} className={inputCls} defaultValue={spec.defaultValue ?? spec.options[0]}>
          {spec.options.map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
      ) : (
        <input
          name={spec.label}
          type={spec.type ?? "text"}
          placeholder={spec.placeholder}
          defaultValue={spec.defaultValue}
          className={inputCls}
        />
      )}
    </label>
  );
}

export function UploadCsvCard({
  requirement,
  onUpload,
}: {
  requirement: string;
  onUpload?: (fileName: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState("");

  return (
    <Panel
      title={
        <h2 className="flex items-center gap-2 font-serif text-xl leading-none">
          <Upload className="size-4 text-brand" />
          Upload CSV
        </h2>
      }
    >
      <p className="rounded-md border border-dashed border-border bg-secondary px-3 py-2 font-mono text-[11px] leading-relaxed text-muted-foreground">
        {requirement}
      </p>
      <div className="mt-4 flex items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          onChange={(e) => setFileName(e.target.files?.[0]?.name ?? "")}
          className="flex-1 text-xs text-muted-foreground"
        />
        <button
          type="button"
          className={btnPrimary}
          onClick={() => {
            if (!fileName) {
              toast.error("Choose a CSV file first.");
              return;
            }
            toast.success(`Queued ${fileName} for import.`);
            onUpload?.(fileName);
            setFileName("");
            if (inputRef.current) inputRef.current.value = "";
          }}
        >
          Upload
        </button>
      </div>
    </Panel>
  );
}

export function ManualEntryCard({
  title,
  fields,
  submitLabel,
  onSubmit,
}: {
  title: string;
  fields: FieldSpec[];
  submitLabel: string;
  onSubmit?: (values: Record<string, string>) => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(
      Array.from(new FormData(form).entries()).map(([k, v]) => [k, String(v)]),
    );
    const firstEmpty = fields.find(
      (f) => !f.checkbox && !f.label.toLowerCase().includes("optional") && !values[f.label]?.trim(),
    );
    if (firstEmpty) {
      toast.error(`${firstEmpty.label} is required.`);
      return;
    }
    onSubmit?.(values);
    toast.success(`${submitLabel.replace(/^Save /, "")} saved as a manual entry.`);
    form.reset();
  }

  return (
    <Panel
      title={
        <h2 className="flex items-center gap-2 font-serif text-xl leading-none">
          <Plus className="size-4 text-brand" />
          {title}
        </h2>
      }
    >
      <form ref={formRef} onSubmit={handleSubmit}>
        <div className="grid grid-cols-2 gap-4">
          {fields.map((f) => (
            <Field key={f.label} spec={f} />
          ))}
        </div>
        <div className="mt-5 flex justify-end">
          <button type="submit" className={btnPrimary}>
            {submitLabel}
          </button>
        </div>
      </form>
    </Panel>
  );
}
