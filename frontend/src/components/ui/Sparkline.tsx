import React, { useId } from 'react';

interface Props {
  /** Ordered values, oldest first. Fewer than two points renders nothing. */
  values: number[];
  /** Any CSS colour; defaults to the brand gold. */
  color?: string;
  width?: number;
  height?: number;
  /** Draw as bars instead of a line — better for sparse, counted data. */
  variant?: 'line' | 'bar';
  label?: string;
}

/**
 * A tiny trend chart drawn inline, with no charting library.
 *
 * It deliberately renders nothing when there is not enough real data: an
 * invented trend on a client-facing dashboard is worse than no trend.
 */
const Sparkline: React.FC<Props> = ({
  values,
  color = 'var(--brand-500)',
  width = 96,
  height = 34,
  variant = 'line',
  label,
}) => {
  const gradientId = useId();

  const clean = (values || []).filter(v => typeof v === 'number' && !Number.isNaN(v));
  if (clean.length < 2) return null;

  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min || 1;
  const pad = 3;
  const usableH = height - pad * 2;

  const x = (i: number) => (i / (clean.length - 1)) * width;
  const y = (v: number) => pad + (1 - (v - min) / span) * usableH;

  if (variant === 'bar') {
    const gap = clean.length > 24 ? 1 : 2;
    const barW = Math.max(1.5, width / clean.length - gap);
    return (
      <svg className="sparkline" width={width} height={height} role="img" aria-label={label || 'trend'}>
        {clean.map((v, i) => {
          const h = Math.max(2, ((v - min) / span) * usableH);
          return (
            <rect
              key={i}
              x={i * (barW + gap)}
              y={height - pad - h}
              width={barW}
              height={h}
              rx={1}
              fill={color}
              opacity={0.25 + 0.75 * (i / (clean.length - 1))}
            />
          );
        })}
      </svg>
    );
  }

  const line = clean.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const area = `${line} L${width},${height} L0,${height} Z`;

  return (
    <svg className="sparkline" width={width} height={height} role="img" aria-label={label || 'trend'}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.26" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={x(clean.length - 1)} cy={y(clean[clean.length - 1])} r="2.4" fill={color} />
    </svg>
  );
};

export default Sparkline;
