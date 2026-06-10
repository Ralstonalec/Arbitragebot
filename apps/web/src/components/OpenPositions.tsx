'use client';

import type { FundTrade } from '@/lib/fund-api';
import { fmtUsd } from '@/lib/fund-api';

const SLEEVE_COLORS: Record<string, string> = {
  polymarket: '#a78bfa',
  sportsbook: '#60a5fa',
  markets:    '#34d399',
  insiders:   '#f59e0b',
};

interface Props {
  trades: FundTrade[];
}

// Infer open positions: BUY / BET actions without a corresponding SELL / SETTLE
export function OpenPositions({ trades: allTrades }: Props) {
  // Build a simple open-set from the trades list: add on BUY/BET, remove on SELL/STOP/SETTLE
  const buys = allTrades.filter((t) => t.action === 'BUY' || t.action === 'BET');
  const exits = new Set(
    allTrades
      .filter((t) => ['SELL', 'STOP', 'SETTLE'].includes(t.action))
      .map((t) => `${t.sleeve}|${t.description}`)
  );
  const open = buys.filter((t) => !exits.has(`${t.sleeve}|${t.description}`));

  if (open.length === 0) {
    return (
      <div className="card" style={{ color: 'var(--muted)', fontSize: '0.875rem', padding: '1rem 1.25rem' }}>
        No open positions
      </div>
    );
  }

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <table>
        <thead>
          <tr>
            <th>Sleeve</th>
            <th>Position</th>
            <th>Entry</th>
            <th>Stake / Qty</th>
            <th>Opened</th>
          </tr>
        </thead>
        <tbody>
          {open.map((t, i) => {
            const sleeveColor = SLEEVE_COLORS[t.sleeve] ?? 'var(--muted)';
            return (
              <tr key={i}>
                <td>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.15rem 0.4rem',
                                  borderRadius: 999, background: `${sleeveColor}22`, color: sleeveColor }}>
                    {t.sleeve}
                  </span>
                </td>
                <td style={{ maxWidth: 340, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {t.description}
                </td>
                <td>{fmtUsd(t.price)}</td>
                <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                  {t.action === 'BET' ? fmtUsd(t.qty) : t.qty.toFixed(4)}
                </td>
                <td style={{ color: 'var(--muted)', fontSize: '0.82rem' }}>
                  {fmtDate(t.ts)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}
