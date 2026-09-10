import React from 'react';
import { Bot } from 'lucide-react';

interface AIVisibilitySectionProps {
  aiVisibility: any[];
  totalKeywords: number;
  aiMentioned: number;
  aiTotal: number;
  months?: string[];
}

const BarSparkline: React.FC<{ data: number[] }> = ({ data }) => {
  if (!data || data.length < 2) return <span style={{ color: 'var(--ink-3)', fontSize: '12px' }}>Insufficient data</span>;
  
  const width = 80;
  const height = 24;
  const padding = 2;
  const barGap = 2;
  
  const maxVal = Math.max(...data, 1); // Avoid div by 0
  
  const barWidth = (width - padding * 2 - (data.length - 1) * barGap) / data.length;
  
  return (
    <svg width={width} height={height} style={{ overflow: 'visible' }}>
      {data.map((val, i) => {
        const x = padding + i * (barWidth + barGap);
        const barHeight = (val / maxVal) * (height - padding * 2);
        const y = height - padding - barHeight;
        return (
          <rect 
            key={i}
            x={x}
            y={y}
            width={barWidth}
            height={barHeight}
            fill="var(--brand)"
            rx="1"
          />
        );
      })}
    </svg>
  );
};

const AIVisibilitySection: React.FC<AIVisibilitySectionProps> = ({ aiVisibility, aiMentioned, aiTotal, months = [] }) => {
  const platformStats: Record<string, any> = {};
  aiVisibility.forEach((m: any) => {
    const p = m.platform || 'Unknown';
    if (!platformStats[p]) {
      platformStats[p] = { totalMentions: 0 };
      months.forEach(month => platformStats[p][month] = 0);
    }
    if (m.mentioned) {
      platformStats[p].totalMentions++;
      if (m._month) {
        platformStats[p][m._month] = (platformStats[p][m._month] || 0) + 1;
      }
    }
  });
  return (
    <section id="ai" className="report-section" data-section-id="ai_visibility">
      <div className="head">
        <div>
          <div className="eyebrow">Search Generative Experience</div>
          <h2>AI Visibility</h2>
        </div>
        <span className="spacer" />
        <span className="src man">Manual entry</span>
      </div>
      
      <div className="grid g4">
        <div className="kpi">
          <div className="lab">Brand Mentions</div>
          <div className="val">{aiMentioned}</div>
          <div className="sub">across all platforms</div>
        </div>
        <div className="kpi">
          <div className="lab">Total Prompts</div>
          <div className="val">{aiTotal}</div>
          <div className="sub">monitored this month</div>
        </div>
        <div className="kpi">
          <div className="lab">Mention Rate</div>
          <div className="val">{aiTotal > 0 ? Math.round((aiMentioned / aiTotal) * 100) : 0}%</div>
          <div className="sub">of prompts mention brand</div>
        </div>
        <div className="kpi">
          <div className="lab">AI Engines</div>
          <div className="val">{new Set(aiVisibility.map((m: any) => m.platform)).size}</div>
          <div className="sub">platforms tracked</div>
        </div>
      </div>
      
      {aiVisibility.length === 0 ? (
        <div className="card pad" style={{ textAlign: 'center', marginTop: 'var(--space-md)', padding: '48px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
            <Bot size={32} color="var(--ink-3)" />
          </div>
          <p className="text-subtle" style={{ margin: 0 }}>No AI visibility data recorded for this month.</p>
        </div>
      ) : (
        <div className="card table-wrapper" style={{ marginTop: 'var(--space-md)' }}>
          <div className="card-header" style={{ paddingBottom: '12px' }}>
            <h3 className="h2" style={{ fontSize: '16px' }}>Mentions by platform</h3>
          </div>
          <table>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Platform</th>
                <th style={{ textAlign: 'center' }}>Trend (Mentions)</th>
                <th className="num" style={{ textAlign: 'right' }}>Total Mentions</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(platformStats).map(([platform, data]: [string, any]) => (
                <tr key={platform}>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: '13px', textTransform: 'capitalize' }}>{platform}</td>
                  <td style={{ textAlign: 'center' }}>
                    <BarSparkline data={months.map(m => data[m] || 0)} />
                  </td>
                  <td className="num" style={{ fontWeight: 600, textAlign: 'right' }}>{data.totalMentions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

export default AIVisibilitySection;
