import React from 'react';
import { screen as lookupScreen } from '../../lib/nav';

/** The one page shell.
 *
 * Every screen is: heading → (one supporting sentence) → (a figure strip) →
 * working surfaces. Nothing above the heading — the trail lives in the top
 * bar, so a screen never announces itself three times over.
 *
 * Pass `screen` and the heading and its sentence come from lib/nav, the same
 * place the sidebar and the trail read. Pass `title` only for a screen whose
 * name is data rather than a fixed route, such as one client's overview.
 */

interface PageProps {
  /** Key into lib/nav. Supplies the heading and the supporting sentence. */
  screen?: string;
  /** Overrides the manifest name — for headings built from data. */
  title?: string;
  /** Overrides the manifest sentence. `null` drops it entirely. */
  lede?: string | null;
  /** Status chip rendered beside the heading. */
  badge?: React.ReactNode;
  /** Page-level actions, right-aligned beside the heading. */
  actions?: React.ReactNode;
  /** Compact supporting figures. The working surface still leads. */
  summary?: React.ReactNode;
  children: React.ReactNode;
}

export const Page: React.FC<PageProps> = ({
  screen, title, lede, badge, actions, summary, children,
}) => {
  const meta = screen ? lookupScreen(screen) : undefined;
  const heading = title ?? meta?.name ?? '';
  const sentence = lede === null ? undefined : (lede ?? meta?.lede);

  return (
    <div className="page">
      <header className="page-head">
        <div className="page-head-text">
          <h1 className="page-name">
            {heading}
            {badge}
          </h1>
          {sentence && <p className="page-lede">{sentence}</p>}
        </div>
        {actions && <div className="page-acts">{actions}</div>}
      </header>

      {summary}

      <div className="page-body">{children}</div>
    </div>
  );
};

interface SectionProps {
  /** What this surface is. Omit for a surface that needs no heading. */
  title?: string;
  /** One line of context, only where the title cannot carry it alone. */
  note?: string;
  /** Controls that belong to this surface — search, filters, add. */
  tools?: React.ReactNode;
  /** Table surfaces bleed to the section edge; forms and prose keep padding. */
  flush?: boolean;
  children: React.ReactNode;
}

export const Section: React.FC<SectionProps> = ({ title, note, tools, flush, children }) => (
  <section className="surface">
    {(title || tools) && (
      <div className="surface-head">
        {title && (
          <div className="surface-head-text">
            <h2 className="surface-name">{title}</h2>
            {note && <p className="surface-note">{note}</p>}
          </div>
        )}
        {tools && <div className="surface-tools">{tools}</div>}
      </div>
    )}
    <div className={flush ? 'surface-body flush' : 'surface-body'}>{children}</div>
  </section>
);

interface EmptyProps {
  icon: React.ReactNode;
  /** What is missing, in the product's own words. */
  title: string;
  /** How to get data here — an empty state teaches the screen. */
  hint: string;
  action?: React.ReactNode;
}

/** The one empty state. Says what is missing and what to do about it. */
export const Empty: React.FC<EmptyProps> = ({ icon, title, hint, action }) => (
  <div className="empty-state">
    <span className="empty-state-icon">{icon}</span>
    <h3>{title}</h3>
    <p>{hint}</p>
    {action && <div className="empty-state-action">{action}</div>}
  </div>
);

export interface Figure {
  label: string;
  value: React.ReactNode;
  /** Where the number came from — §15 keeps provenance next to every figure. */
  note?: string;
  /** Signed change, rendered as movement rather than decoration. */
  delta?: { value: string; direction: 'up' | 'down' | 'flat' };
}

/** Supporting figures as one strip, not a row of competing cards. */
export const Summary: React.FC<{ figures: Figure[] }> = ({ figures }) => {
  if (!figures.length) return null;
  return (
    <div className="figures" role="group" aria-label="Summary figures">
      {figures.map(f => (
        <div className="figure" key={f.label}>
          <span className="figure-label">{f.label}</span>
          <span className="figure-value">
            {f.value}
            {f.delta && (
              <span className={`figure-delta ${f.delta.direction}`}>{f.delta.value}</span>
            )}
          </span>
          {f.note && <span className="figure-note">{f.note}</span>}
        </div>
      ))}
    </div>
  );
};

export default Page;
