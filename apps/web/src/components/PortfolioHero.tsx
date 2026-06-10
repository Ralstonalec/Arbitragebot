'use client';

import { useState } from 'react';
import type { FundOverview, EquityPoint, Period } from '@/lib/fund-api';
import { filterByPeriod, fmtUsd, fmtPct } from '@/lib/fund-api';
import { EquitySparkline } from './EquitySparkline';

const PERIODS: { label: string; value: Period }[] = [
  { label: '1D',  value: 'day'   },
  { label: '1W',  value: 'week'  },
  { label: '1M',  value: 'month' },
  { label: '3M',  value: '3m'    },
  { label: '1Y',  value: 'year'  },
  { label: 'YTD', value: 'ytd'   },
  { label: 'All', value: 'all'   },
];

interface Props {
  overview: FundOverview | null;
  history: EquityPoint[];
  period: Period;
  onPeriod: (p: Period) => void;
  loading: boolean;
}

export function PortfolioHero({ overview, history, period, onPeriod, loading }: Props) {
  const filtered = filterByPeriod(history, period);
  const startEq = filtered.length > 0 ? filtered[0].total : (overview?.equity ?? 0);
  const curEq = overview?.equity ?? (filtered.length > 0 ? filtered[filtered.length - 1].total : 0);
  const change = curEq - startEq;
  const changePct = startEq > 0 ? change / startEq : 0;
  const isPositive = change >= 0;
  const halt = overview?.risk?.hard_halt ?? overview?.risk?.daily_halt;

  return (
    <div className="card" style={{ padding: '1.75rem 1.5rem 1.25rem', marginBottom: '1.5rem' }}>
      {/* top row: equity + period toggles */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                    flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.08em',
                        color: 'var(--muted)', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
            Total Portfolio Value
          </div>
          <div style={{ fontSize: 'clamp(2rem, 5vw, 3.25rem)', fontWeight: 700,
                        letterSpacing: '-0.02em', lineHeight: 1, color: 'var(--text)' }}>
            {loading ? '—' : fmtUsd(curEq)}
          </div>
          {!loading && (
            <div style={{ marginTop: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '1rem', fontWeight: 600,
                             color: isPositive ? 'var(--positive)' : 'var(--danger)' }}>
                {isPositive ? '▲' : '▼'} {fmtUsd(Math.abs(change))}
              </span>
              <span style={{ fontSize: '0.9rem', fontWeight: 500,
                             color: isPositive ? 'var(--positive)' : 'var(--danger)' }}>
                ({fmtPct(changePct)})
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                {PERIODS.find(p => p.value === period)?.label ?? ''}
              </span>
            </div>
          )}
        </div>

        {/* period pills */}
        <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
          {PERIODS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => onPeriod(value)}
              style={{
                padding: '0.3rem 0.65rem',
                fontSize: '0.78rem',
                fontWeight: 600,
                borderRadius: '999px',
                cursor: 'pointer',
                border: value === period ? '1px solid var(--accent)' : '1px solid var(--border)',
                background: value === period ? 'rgba(61,158,255,0.15)' : 'transparent',
                color: value === period ? 'var(--accent)' : 'var(--muted)',
                transition: 'all 0.12s ease',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* halt banner */}
      {halt && (
        <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', borderRadius: 8,
                      background: 'rgba(240,113,120,0.12)', border: '1px solid rgba(240,113,120,0.3)',
                      color: 'var(--danger)', fontSize: '0.82rem' }}>
          ⛔ {halt}
        </div>
      )}

      {/* sparkline */}
      <div style={{ marginTop: '1.25rem' }}>
        <EquitySparkline
          points={filtered.length >= 2 ? filtered : history}
          height={140}
          color={isPositive ? '#3ecf8e' : '#f07178'}
        />
      </div>

      {/* sleeve sub-numbers */}
      {overview && (
        <div style={{ marginTop: '1rem', display: 'flex', gap: '1.5rem', flexWrap: 'wrap',
                      borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
          {overview.sim_broker && (
            <SubStat label="Markets / Insiders" value={overview.sim_broker.equity ?? 0} />
          )}
          <SubStat label="Polymarket" value={(overview.cash?.polymarket ?? 0) +
            Object.entries(overview.cash ?? {}).filter(([k]) => k !== 'polymarket' && k !== 'sportsbook')
              .reduce((s, [,v]) => s + v, 0)} />
          <SubStat label="Sportsbook" value={overview.cash?.sportsbook ?? 0} />
          <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Open positions
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 600 }}>{overview.open_positions}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function SubStat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div style={{ fontSize: '0.7rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: '1.15rem', fontWeight: 600 }}>{fmtUsd(value)}</div>
    </div>
  );
}
