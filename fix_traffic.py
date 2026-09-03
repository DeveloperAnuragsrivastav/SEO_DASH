content = """import React from 'react';
import { fmt, deltaEl } from './ReportUtils';

interface TrafficSectionProps {
  gsc: any;
  ga4: any;
  gbp: any;
  deltas: any;
}

const TrafficSection: React.FC<TrafficSectionProps> = ({ gsc, ga4, gbp, deltas }) => {
  const topPages = gsc.top_pages || [];
  
  const ga4Sources = ga4.traffic_sources || [];
  const ga4Pages = ga4.top_pages || [];
  const ga4Devices = ga4.devices || [];
  const totalGa4DeviceSessions = ga4Devices.reduce((sum: number, d: any) => sum + (d.sessions || 0), 0);

  return (
    <section id="search" className="report-section">
      <div className="head">
        <div>
          <div className="eyebrow">Traffic & Conversions</div>
          <h2>Search Performance</h2>
        </div>
        <span className="spacer" />
        <span className="src">GSC & GA4 · auto</span>
      </div>
      
      <div className="grid g3">
        <div className="kpi">
          <div className="lab">Search Clicks (GSC)</div>
          <div className="val">{fmt(gsc.clicks)}</div>
          <div className="sub">{deltaEl(gsc.clicks, gsc.clicks - (deltas.gsc?.clicks || 0))} vs prev</div>
        </div>
        <div className="kpi">
          <div className="lab">Impressions (GSC)</div>
          <div className="val">{fmt(gsc.impressions)}</div>
          <div className="sub">{deltaEl(gsc.impressions, gsc.impressions - (deltas.gsc?.impressions || 0))} vs prev</div>
        </div>
        <div className="kpi">
          <div className="lab">Avg CTR (GSC)</div>
          <div className="val">{(gsc.ctr ? (gsc.ctr * 100).toFixed(2) : 0)}%</div>
          <div className="sub">click-through rate</div>
        </div>
        <div className="kpi">
          <div className="lab">Avg Position (GSC)</div>
          <div className="val">{(gsc.position ? gsc.position.toFixed(1) : 0)}</div>
          <div className="sub">search ranking</div>
        </div>
        <div className="kpi">
          <div className="lab">Website Sessions (GA4)</div>
          <div className="val">{fmt(ga4.sessions)}</div>
          <div className="sub">{fmt(ga4.users)} total users</div>
        </div>
        <div className="kpi">
          <div className="lab">Conversions (GA4)</div>
          <div className="val">{fmt(ga4.conversions)}</div>
          <div className="sub">key events</div>
        </div>
      </div>

      {/* ── Top Pages ── */}
      <div style={{ marginTop: 'var(--space-lg, 32px)' }}>
        <div className="head" style={{ marginBottom: '12px' }}>
          <div><h3 className="h2">Top Pages</h3></div>
          <span className="spacer" />
          <span className="src">GSC · auto</span>
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
              {topPages.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-subtle, #6b7280)' }}>No data available for this period</td>
                </tr>
              )}
              {topPages.map((p: any, i: number) => (
                <tr key={i}>
                  <td style={{ maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <a href={p.page} target="_blank" rel="noreferrer" style={{ color: 'var(--brand, #2563eb)', textDecoration: 'none' }}>
                      {(p.page || '').replace(/^https?:\\/\\//, '').replace(/\\/$/, '')}
                    </a>
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(p.clicks)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(p.impressions)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{p.ctr}%</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{p.position}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── GA4 Top Traffic Sources ── */}
      <div style={{ marginTop: 'var(--space-lg, 32px)' }}>
        <div className="head" style={{ marginBottom: '12px' }}>
          <div><h3 className="h2">Top Traffic Sources</h3></div>
          <span className="spacer" />
          <span className="src">GA4 · auto</span>
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
              {ga4Sources.length === 0 && (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-subtle, #6b7280)' }}>No data available for this period</td>
                </tr>
              )}
              {ga4Sources.map((s: any, i: number) => (
                <tr key={i}>
                  <td style={{ fontWeight: 500 }}>{s.source}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(s.sessions)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(s.users)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(s.conversions)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── GA4 Top Pages ── */}
      <div style={{ marginTop: 'var(--space-lg, 32px)' }}>
        <div className="head" style={{ marginBottom: '12px' }}>
          <div><h3 className="h2">Top Landing Pages</h3></div>
          <span className="spacer" />
          <span className="src">GA4 · auto</span>
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
              {ga4Pages.length === 0 && (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '24px', color: 'var(--text-subtle, #6b7280)' }}>No data available for this period</td>
                </tr>
              )}
              {ga4Pages.map((p: any, i: number) => (
                <tr key={i}>
                  <td style={{ maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.page}
                  </td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 500 }}>{fmt(p.sessions)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(p.users)}</td>
                  <td style={{ textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(p.conversions)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── GA4 Device Breakdown ── */}
      <div style={{ marginTop: 'var(--space-lg, 32px)' }}>
        <div className="head" style={{ marginBottom: '12px' }}>
          <div><h3 className="h2">Audience Devices</h3></div>
          <span className="spacer" />
          <span className="src">GA4 · auto</span>
        </div>
        <div className="grid g3" style={{ gap: '16px' }}>
          {ga4Devices.length === 0 && (
            <div className="kpi" style={{ textAlign: 'center', gridColumn: '1 / -1', color: 'var(--text-subtle, #6b7280)', padding: '24px' }}>
              No device data available for this period
            </div>
          )}
          {ga4Devices.map((d: any, i: number) => {
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
          })}
        </div>
      </div>

      {/* Google Business Profile Section - Clearly Demarcated */}
      {(gbp.calls || gbp.direction_requests || gbp.website_clicks) && (
        <div style={{ marginTop: 'var(--space-lg)' }}>
          <div className="head" style={{ marginBottom: '12px' }}>
            <div>
              <h3 className="h2">Google Business Profile</h3>
            </div>
            <span className="spacer" />
            <span className="src man">Manual entry</span>
          </div>
          <div className="card pad" style={{ borderLeft: '3px solid var(--amber)' }}>
            <div className="grid g4">
              <div className="kpi" style={{ border: 'none', padding: 0 }}>
                <div className="lab">Calls</div>
                <div className="val" style={{ fontSize: '28px' }}>{fmt(gbp.calls)}</div>
              </div>
              <div className="kpi" style={{ border: 'none', padding: 0 }}>
                <div className="lab">Direction requests</div>
                <div className="val" style={{ fontSize: '28px' }}>{fmt(gbp.direction_requests)}</div>
              </div>
              <div className="kpi" style={{ border: 'none', padding: 0 }}>
                <div className="lab">Website clicks</div>
                <div className="val" style={{ fontSize: '28px' }}>{fmt(gbp.website_clicks)}</div>
              </div>
              <div className="kpi" style={{ border: 'none', padding: 0 }}>
                <div className="lab">Local searches</div>
                <div className="val" style={{ fontSize: '28px' }}>{fmt(gbp.searches)}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default TrafficSection;
"""
with open("frontend/src/components/report/TrafficSection.tsx", "w") as f:
    f.write(content)
