import React from 'react';
import { Link as LinkIcon } from 'lucide-react';

interface LinksSectionProps {
  links: any[];
  months?: string[];
}

const LinksSection: React.FC<LinksSectionProps> = ({ links }) => {
  let totalLinks = 0;
  const uniqueDomains = new Set(links.filter((l: any) => l.domain).map((l: any) => l.domain)).size;
  const linkTypes: Record<string, number> = {};
  links.forEach((l: any) => { 
    const c = l.count || 1;
    totalLinks += c;
    linkTypes[l.activity_type] = (linkTypes[l.activity_type] || 0) + c; 
  });

  return (
    <section id="links" className="report-section">
      <div className="head">
        <div>
          <div className="eyebrow">Off-Page SEO</div>
          <h2>Links Built</h2>
        </div>
        <span className="spacer" />
        <span className="src man">Manual entry</span>
      </div>
      
      <div className="grid g3">
        <div className="kpi">
          <div className="lab">Links Created</div>
          <div className="val">{totalLinks}</div>
          <div className="sub">across selected months</div>
        </div>
        <div className="kpi">
          <div className="lab">Unique Domains</div>
          <div className="val">{uniqueDomains}</div>
          <div className="sub">no repeats</div>
        </div>
        <div className="kpi">
          <div className="lab">Activity Types</div>
          <div className="val">{Object.keys(linkTypes).length}</div>
          <div className="sub">categories</div>
        </div>
      </div>
      
      {links.length === 0 ? (
        <div className="card pad" style={{ textAlign: 'center', marginTop: 'var(--space-md)', padding: '48px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
            <LinkIcon size={32} color="var(--ink-3)" />
          </div>
          <p className="text-subtle" style={{ margin: 0 }}>No link building data recorded for this month.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2" style={{ marginTop: 'var(--space-md)' }}>
          <div className="card table-wrapper">
            <div className="card-header" style={{ paddingBottom: '12px' }}>
              <h3 className="h2" style={{ fontSize: '16px' }}>Live Links</h3>
            </div>
            <div style={{ maxHeight: '420px', overflow: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 40, textAlign: 'center' }}>#</th>
                    <th>Month</th>
                    <th className="hide-s">Activity</th>
                    <th>URL</th>
                    <th style={{ textAlign: 'center' }}>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {links.map((l: any, i: number) => (
                    <tr key={l.id || i}>
                      <td className="mono" style={{ color: 'var(--text-tertiary)', fontSize: 12, textAlign: 'center' }}>{i + 1}</td>
                      <td style={{ color: 'var(--text-subtle)', fontSize: '12px' }}>{l._month}</td>
                      <td className="hide-s" style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>{l.activity_type}</td>
                      <td>
                        {l.url ? (
                          <a href={l.url} target="_blank" rel="noopener noreferrer" style={{ fontFamily: 'var(--mono)', fontSize: '12.5px', textDecoration: 'none', borderBottom: '1px solid var(--line)', color: 'var(--text-primary)' }}>
                            {l.domain || 'Link'}
                          </a>
                        ) : (
                          <span style={{ color: 'var(--text-tertiary)' }}>—</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'center', fontWeight: 500 }}>{l.count || 1}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          
          <div className="card pad">
            <h3 className="h2" style={{ fontSize: '16px', marginBottom: '10px' }}>By Activity Type</h3>
            {(() => {
              const rows = Object.entries(linkTypes) as [string, number][];
              const top = Math.max(1, ...rows.map(([, v]) => v));
              return rows.map(([k, v]) => (
                <div className="activity-row" key={k}>
                  <span>{k}</span>
                  <div className="track">
                    <div className="fill gold" style={{ width: `${Math.round((v / top) * 100)}%` }} />
                  </div>
                  <b>{v}</b>
                </div>
              ));
            })()}
          </div>
        </div>
      )}
    </section>
  );
};

export default LinksSection;
