'use client';

import type { FundTrade, Period } from '@/lib/fund-api';
import { filterByPeriod, fmtUsd } from '@/lib/fund-api';

const SLEEVE_COLORS: Record<string, string> = {
  polymarket: '#a78bfa',
  sportsbook: '#60a5fa',
  markets:    '#34d399',
  insiders:   '#f59e0b',
};

interface Props {
  trades: FundTrade[];
  period: Period;
}

export function TradeHighlights({ trades, period }: Props) {
  const settled = filterByPeriod(trades, period)
    .filter((t) => t.pnl !== null);

  const wins = settled.filter((t) => (t.pnl ?? 0) > 0)
    .sort((a, b) => (b.pnl ?? 0) - (a.pnl ?? 0))
    .slice(0, 7);

  const losses = settled.filter((t) => (t.pnl ?? 0) < 0)
    .sort((a, b) => (a.pnl ?? 0) - (b.pnl ?? 0))
    .slice(0, 7);

  const totalWins  = settled.filter((t) => (t.pnl ?? 0) > 0).reduce((s, t) => s + (t.pnl ?? 0), 0);
  const totalLoss  = settled.filter((t) => (t.pnl ?? 0) < 0).reduce((s, t) => s + (t.pnl ?? 0), 0);
  const totalPnl   = totalWins + totalLoss;

  if (settled.length === 0) {
    return (
      <div className="card" style={{ color: 'var(--muted)', fontSize: '0.875rem',
                                     padding: '1.25rem', marginBottom: '1.5rem' }}>
        No settled trades for this period yet — wins & losses will appear here as trades close.
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
      {/* wins */}
      <div className="card" style={{ padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                      marginBottom: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase',
                         letterSpacing: '0.07em', color: 'var(--positive)' }}>
            ▲ Biggest Wins
          </span>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--positive)' }}>
            {fmtUsd(totalWins)} total
          </span>
        </div>
        {wins.length === 0
          ? <p style={{ color: 'var(--muted)', fontSize: '0.82rem', margin: 0 }}>No wins this period</p>
          : wins.map((t, i) => <TradeRow key={i} trade={t} positive />)
        }
      </div>

      {/* losses */}
      <div className="card" style={{ padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                      marginBottom: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase',
                         letterSpacing: '0.07em', color: 'var(--danger)' }}>
            ▼ Biggest Losses
          </span>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--danger)' }}>
            {fmtUsd(totalLoss)} total
          </span>
        </div>
        {losses.length === 0
          ? <p style={{ color: 'var(--muted)', fontSize: '0.82rem', margin: 0 }}>No losses this period</p>
          : losses.map((t, i) => <TradeRow key={i} trade={t} positive={false} />)
        }
      </div>

      {/* summary bar spans both cols */}
      <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '1.5rem', flexWrap: 'wrap',
                    padding: '0.6rem 1rem', borderRadius: 8,
                    background: totalPnl >= 0 ? 'rgba(62,207,142,0.07)' : 'rgba(240,113,120,0.07)',
                    border: `1px solid ${totalPnl >= 0 ? 'rgba(62,207,142,0.2)' : 'rgba(240,113,120,0.2)'}` }}>
        <SummaryPill label="Net P&L" value={fmtUsd(totalPnl)}
          color={totalPnl >= 0 ? 'var(--positive)' : 'var(--danger)'} />
        <SummaryPill label="Wins" value={String(settled.filter((t) => (t.pnl ?? 0) > 0).length)} color="var(--positive)" />
        <SummaryPill label="Losses" value={String(settled.filter((t) => (t.pnl ?? 0) < 0).length)} color="var(--danger)" />
        <SummaryPill label="Win rate"
          value={(settled.length > 0
            ? (settled.filter((t) => (t.pnl ?? 0) > 0).length / settled.length * 100).toFixed(0)
            : '0') + '%'}
          color="var(--text)" />
      </div>
    </div>
  );
}

function TradeRow({ trade, positive }: { trade: FundTrade; positive: boolean }) {
  const sleeveColor = SLEEVE_COLORS[trade.sleeve] ?? 'var(--muted)';
  const pnl = trade.pnl ?? 0;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                  padding: '0.45rem 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ minWidth: 0, paddingRight: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.1rem' }}>
          <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '0.1rem 0.35rem',
                         borderRadius: 999, background: `${sleeveColor}22`, color: sleeveColor }}>
            {trade.sleeve}
          </span>
          <span style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>{fmtDate(trade.ts)}</span>
        </div>
        <div style={{ fontSize: '0.82rem', overflow: 'hidden', textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap', maxWidth: 260 }}>
          {trade.description}
        </div>
      </div>
      <span style={{ flexShrink: 0, fontWeight: 700, fontSize: '0.9rem',
                     color: positive ? 'var(--positive)' : 'var(--danger)' }}>
        {pnl >= 0 ? '+' : ''}{fmtUsd(pnl)}
      </span>
    </div>
  );
}

function SummaryPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
      <span style={{ fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
      <span style={{ fontSize: '0.9rem', fontWeight: 700, color }}>{value}</span>
    </div>
  );
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return ''; }
}
