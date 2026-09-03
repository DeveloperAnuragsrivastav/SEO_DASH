import React from 'react';
import { fmt, deltaEl } from './ReportUtils';

interface TrafficSectionProps {
  gsc: any;
  ga4: any;
  gbp: any;
  deltas: any;
}

const TrafficSection: React.FC<TrafficSectionProps> = ({ gsc, ga4, gbp, deltas }) => {
  const topPages = Array.isArray(gsc.top_pages) ? gsc.top_pages : [];
  
  const ga4Sources = Array.isArray(ga4.traffic_sources) ? ga4.traffic_sources : [];
  const ga4Pages = Array.isArray(ga4.top_pages) ? ga4.top_pages : [];
  const ga4Devices = Array.isArray(ga4.devices) ? ga4.devices : [];
  const totalGa4DeviceSessions = ga4Devices.reduce((sum: number, d: any) => sum + (d.sessions || 0), 0);

  const formatDuration = (seconds: number) => {
    if (!seconds) return '0m 0s';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
  };

  const gscClicks = gsc.clicks || 0;
  const gscImpressions = gsc.impressions || 0;
  const gscCtr = gsc.ctr || 0;
  const gscPosition = gsc.position || 0;

  return (
    <>
      {/* ── GSC Section ── */}
      <section id="search" className="report-section">
        <div className="head">
          <div>
            <div className="eyebrow">Search Performance</div>
            <h2>Google Search Console</h2>
          </div>
          <span className="spacer" />
          <span className="src">GSC · auto</span>
        </div>
        
        <div className="grid g4">
          <div className="kpi">
            <div className="lab">Search Clicks</div>
            <div className="val">{fmt(gscClicks)}</div>
            <div className="sub">{deltaEl(gscClicks, gscClicks - (deltas.gsc?.clicks || 0))} vs prev</div>
          </div>
          <div className="kpi">
            <div className="lab">Impressions</div>
            <div className="val">{fmt(gscImpressions)}</div>
            <div className="sub">{deltaEl(gscImpressions, gscImpressions - (deltas.gsc?.impressions || 0))} vs prev</div>
          </div>
          <div className="kpi">
            <div className="lab">Avg CTR</div>
            <div className="val">{(gscCtr ? (gscCtr * 100).toFixed(1) : 0)}%</div>
            <div className="sub">click-through rate</div>
          </div>
          <div className="kpi">
            <div className="lab">Avg Position</div>
            <div className="val">{(gscPosition ? gscPosition.toFixed(1) : 0)}</div>
            <div className="sub">search ranking</div>
          </div>
        </div>

        {/* ── Top Pages (GSC) ── */}
        <div style={{ marginTop: 'var(--space-lg, 32px)' }}>
          <div className="head" style={{ marginBottom: '12px' }}>
            <div><h3 className="h2">Top Pages</h3></div>
          </div>
          <div className="card table-wrapper">
            <table>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Page URL</th>
                  <th style={{ textAlign: 'right' }}>Clicks</th>
                  <th style={{ textAlign: 'right' }}>Impressions</th>
                  <th style={{ textAlign: 'right' }}>CTR</th>
                  <th style={{ textAlign: 'right' }}>Position</th>
                </tr>
              </thead>
              <tbody>
                {topPages.length > 0 ? topPages.map((p: any, i: number) => (
                  <tr key={i}>
                    <td style={{ maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <a href={p.page} target="_blank" rel="noreferrer" style={{ color: 'var(--brand, #2563eb)', textDecoration: 'none' }}>
                        {(p.page || '').replace(/^https?:\/\//, '').replace(/\/$/, '')}
                      </a>
                    </td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(p.clicks)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(p.impressions)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{typeof p.ctr === 'number' ? p.ctr.toFixed(1) : p.ctr}%</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{p.position}</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-subtle)', padding: '24px 0' }}>No search console data available</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── GA4 Section ── */}
      <section id="traffic" className="report-section">
        <div className="head">
          <div>
            <div className="eyebrow">Website Traffic</div>
            <h2>Google Analytics 4</h2>
          </div>
          <span className="spacer" />
          <span className="src">GA4 · auto</span>
        </div>

        <div className="grid g3">
          <div className="kpi">
            <div className="lab">Total Sessions</div>
            <div className="val">{fmt(ga4.sessions || 0)}</div>
            <div className="sub">{fmt(ga4.users || 0)} total users</div>
          </div>
          <div className="kpi">
            <div className="lab">Organic Sessions</div>
            <div className="val">{fmt(ga4.organic_sessions || 0)}</div>
            <div className="sub">from search engines</div>
          </div>
          {(ga4.conversions || 0) > 0 && (
            <div className="kpi">
              <div className="lab">Conversions</div>
              <div className="val">{fmt(ga4.conversions)}</div>
              <div className="sub">key events</div>
            </div>
          )}
          {(ga4.add_to_carts || 0) > 0 && (
            <div className="kpi">
              <div className="lab">Add to Carts</div>
              <div className="val">{fmt(ga4.add_to_carts)}</div>
              <div className="sub">ecommerce events</div>
            </div>
          )}
          {(ga4.avg_session_duration || 0) > 0 && (
            <div className="kpi" style={{ gridColumn: 'span 2' }}>
              <div className="lab">Avg Session Duration</div>
              <div className="val">{formatDuration(ga4.avg_session_duration)}</div>
              <div className="sub">time on site</div>
            </div>
          )}
        </div>

        {/* ── GA4 Top Traffic Sources ── */}
        <div style={{ marginTop: 'var(--space-lg, 32px)' }}>
          <div className="head" style={{ marginBottom: '12px' }}>
            <div><h3 className="h2">Top Traffic Sources</h3></div>
          </div>
          <div className="card table-wrapper">
            <table>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Source / Medium</th>
                  <th style={{ textAlign: 'right' }}>Sessions</th>
                  <th style={{ textAlign: 'right' }}>Users</th>
                  <th style={{ textAlign: 'right' }}>Conversions</th>
                </tr>
              </thead>
              <tbody>
                {ga4Sources.length > 0 ? ga4Sources.map((s: any, i: number) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{s.source}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(s.sessions)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(s.users)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(s.conversions)}</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-subtle)', padding: '24px 0' }}>No traffic sources available</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── GA4 Top Pages ── */}
        <div style={{ marginTop: 'var(--space-lg, 32px)' }}>
          <div className="head" style={{ marginBottom: '12px' }}>
            <div><h3 className="h2">Top Landing Pages</h3></div>
          </div>
          <div className="card table-wrapper">
            <table>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Page Path</th>
                  <th style={{ textAlign: 'right' }}>Sessions</th>
                  <th style={{ textAlign: 'right' }}>Users</th>
                  <th style={{ textAlign: 'right' }}>Conversions</th>
                </tr>
              </thead>
              <tbody>
                {ga4Pages.length > 0 ? ga4Pages.map((p: any, i: number) => (
                  <tr key={i}>
                    <td style={{ maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <span style={{ color: 'var(--brand, #2563eb)' }}>{p.page}</span>
                    </td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(p.sessions)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(p.users)}</td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(p.conversions)}</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-subtle)', padding: '24px 0' }}>No landing pages available</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── GA4 Device Breakdown ── */}
        <div style={{ marginTop: 'var(--space-lg, 32px)' }}>
          <div className="head" style={{ marginBottom: '12px' }}>
            <div><h3 className="h2">Audience Devices</h3></div>
          </div>
          <div className="grid g3" style={{ gap: '16px' }}>
            {ga4Devices.length > 0 ? ga4Devices.map((d: any, i: number) => {
              const pct = totalGa4DeviceSessions > 0 ? Math.round((d.sessions / totalGa4DeviceSessions) * 100) : 0;
              const deviceName = d.device || 'Unknown';
              const icon = deviceName.toLowerCase().includes('desktop') ? '🖥️' : deviceName.toLowerCase().includes('mobile') ? '📱' : '📟';
              return (
                <div key={i} className="kpi" style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', marginBottom: '4px' }}>{icon}</div>
                  <div className="lab">{deviceName}</div>
                  <div className="val" style={{ fontSize: '28px' }}>{pct}%</div>
                  <div className="sub" style={{ fontFamily: 'var(--mono)' }}>{fmt(d.sessions)} sessions · {fmt(d.users)} users</div>
                </div>
              );
            }) : (
              <div className="kpi" style={{ gridColumn: 'span 3', textAlign: 'center', color: 'var(--text-subtle)' }}>
                No device data available
              </div>
            )}
          </div>
        </div>
      {/* ── GA4 Countries ── */}
      <div style={{ marginTop: 'var(--space-lg, 32px)' }}>
        <div className="head" style={{ marginBottom: '12px' }}>
          <div><h3 className="h2">Top Countries</h3></div>
        </div>
        <div className="card table-wrapper">
          <table>
            <thead>
              <tr>
                  <th style={{ textAlign: 'left' }}>Country</th>
                  <th style={{ textAlign: 'right' }}>Sessions</th>
                  <th style={{ textAlign: 'right' }}>Users</th>
                </tr>
              </thead>
              <tbody>
                {Array.isArray(ga4.countries) && ga4.countries.length > 0 ? (
                  ga4.countries.map((c: any, i: number) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 500 }}>{c.country}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(c.sessions)}</td>
                        <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(c.users)}</td>
                      </tr>
                    ))
                ) : (
                <tr>
                  <td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-subtle)', padding: '24px 0' }}>No country data available</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    {/* Google Business Profile Section - Only show if has data */}
    {((gbp.calls || 0) > 0 || (gbp.direction_requests || 0) > 0 || (gbp.website_clicks || 0) > 0 || (gbp.searches || 0) > 0) && (
    <section id="gbp" className="report-section">
        <div className="head" style={{ marginBottom: '12px' }}>
          <div>
            <div className="eyebrow">Local Search</div>
            <h3 className="h2">Google Business Profile</h3>
          </div>
          <span className="spacer" />
          <span className="src man">Manual entry</span>
        </div>
        <div className="card pad" style={{ borderLeft: '3px solid var(--amber)' }}>
          {(() => {
            const metrics = [
              { label: 'Calls', value: gbp.calls || 0 },
              { label: 'Direction requests', value: gbp.direction_requests || 0 },
              { label: 'Website clicks', value: gbp.website_clicks || 0 },
              { label: 'Local searches', value: gbp.searches || 0 }
            ].filter(m => m.value > 0);
            return (
              <div className={`grid g${Math.max(1, metrics.length)}`}>
                {metrics.map((m, i) => (
                  <div key={i} className="kpi" style={{ border: 'none', padding: 0 }}>
                    <div className="lab">{m.label}</div>
                    <div className="val" style={{ fontSize: '28px' }}>{fmt(m.value)}</div>
                  </div>
                ))}
              </div>
            );
          })()}
        </div>
      </section>
    )}
    </>
  );
};

export default TrafficSection;
