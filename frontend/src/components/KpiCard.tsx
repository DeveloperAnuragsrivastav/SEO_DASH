import React from 'react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';
import ProvenanceBadge from './ProvenanceBadge';
import { 
  HiOutlineCursorArrowRays, 
  HiOutlineGlobeAlt, 
  HiOutlineTrophy, 
  HiOutlineSparkles, 
  HiOutlineChatBubbleLeftRight, 
  HiOutlineCpuChip, 
  HiOutlineMagnifyingGlass, 
  HiOutlineLink 
} from 'react-icons/hi2';

interface KpiCardProps {
  title: string;
  value: string | number;
  delta?: number;
  sourceLabel: string;
  isManual: boolean;
}

const getMetricIcon = (title: string) => {
  const t = title.toLowerCase();
  if (t.includes('click')) return HiOutlineCursorArrowRays;
  if (t.includes('session')) return HiOutlineGlobeAlt;
  if (t.includes('ranking') || t.includes('improved')) return HiOutlineTrophy;
  if (t.includes('chatgpt')) return HiOutlineChatBubbleLeftRight;
  if (t.includes('claude')) return HiOutlineCpuChip;
  if (t.includes('gemini') || t.includes('ai')) return HiOutlineSparkles;
  if (t.includes('perplexity')) return HiOutlineMagnifyingGlass;
  if (t.includes('link') || t.includes('domain')) return HiOutlineLink;
  return HiOutlineSparkles;
};

const KpiCard: React.FC<KpiCardProps> = ({ title, value, delta, sourceLabel, isManual }) => {
  const IconComp = getMetricIcon(title);

  return (
    <div
      className="kpi"
      style={{
        gap: '12px',
        marginBottom: 0
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '13px', color: 'var(--ink-2)', fontWeight: 600, fontFamily: 'var(--font-body)', letterSpacing: '0.01em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <IconComp size={16} style={{ color: 'var(--ink-3)' }} />
          {title}
        </h3>
        
        {delta !== undefined && (
          <div 
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 8px',
              borderRadius: '9999px',
              fontSize: '12px',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              background: delta >= 0 ? 'var(--up-soft)' : 'var(--down-soft)',
              color: delta >= 0 ? 'var(--up)' : 'var(--down)',
            }}
          >
            {delta >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
            {Math.abs(delta)}
          </div>
        )}
      </div>

      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '32px', fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
        {value}
      </div>

      <div style={{ marginTop: 'auto', paddingTop: '8px', display: 'flex', alignItems: 'center' }}>
        <ProvenanceBadge label={sourceLabel} isManual={isManual} />
      </div>
    </div>
  );
};

export default KpiCard;
