'use client';

import type { EquityPoint } from '@/lib/fund-api';

interface Props {
  points: EquityPoint[];
  height?: number;
  color?: string;
  showAxes?: boolean;
}

export function EquitySparkline({ points, height = 120, color = '#3d9eff', showAxes = true }: Props) {
  if (points.length < 2) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--muted)', fontSize: '0.85rem' }}>
        No equity history yet — starts recording on first cycle
      </div>
    );
  }

  const W = 1000;
  const H = height;
  const padX = showAxes ? 64 : 8;
  const padY = showAxes ? 16 : 4;
  const chartW = W - padX * 2;
  const chartH = H - padY * 2;

  const values = points.map((p) => p.total);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;

  const xs = points.map((_, i) => padX + (i / (points.length - 1)) * chartW);
  const ys = values.map((v) => padY + chartH - ((v - minV) / range) * chartH);

  const polylinePoints = xs.map((x, i) => `${x},${ys[i]}`).join(' ');
  const areaPoints = [
    `${xs[0]},${padY + chartH}`,
    ...xs.map((x, i) => `${x},${ys[i]}`),
    `${xs[xs.length - 1]},${padY + chartH}`,
  ].join(' ');

  const isFlat = maxV === minV;
  const gradId = `sparkGrad_${color.replace('#', '')}`;

  // Y-axis ticks
  const yTicks = [minV, (minV + maxV) / 2, maxV];

  // X-axis ticks: first and last dates
  const xLabels = [
    { x: padX, label: fmtDate(points[0].ts) },
    { x: W - padX, label: fmtDate(points[points.length - 1].ts) },
  ];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      style={{ width: '100%', height, display: 'block' }}
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* filled area */}
      {!isFlat && (
        <polygon points={areaPoints} fill={`url(#${gradId})`} />
      )}

      {/* horizontal grid lines */}
      {showAxes && yTicks.map((v, i) => {
        const y = padY + chartH - ((v - minV) / range) * chartH;
        return (
          <g key={i}>
            <line x1={padX} y1={y} x2={W - padX} y2={y}
              stroke="#243044" strokeWidth="1" strokeDasharray="4 4" />
            <text x={padX - 8} y={y + 4} textAnchor="end"
              fill="#8fa3bc" fontSize="22" fontFamily="system-ui">
              {fmtShort(v)}
            </text>
          </g>
        );
      })}

      {/* x-axis labels */}
      {showAxes && xLabels.map(({ x, label }, i) => (
        <text key={i} x={x} y={H} textAnchor={i === 0 ? 'start' : 'end'}
          fill="#8fa3bc" fontSize="20" fontFamily="system-ui">
          {label}
        </text>
      ))}

      {/* line */}
      <polyline
        points={polylinePoints}
        fill="none"
        stroke={color}
        strokeWidth="3"
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {/* last value dot */}
      <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="6"
        fill={color} stroke="var(--surface)" strokeWidth="2" />
    </svg>
  );
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

function fmtShort(n: number): string {
  if (Math.abs(n) >= 1000) return '$' + (n / 1000).toFixed(0) + 'k';
  return '$' + n.toFixed(0);
}
