'use client';

import type { FundTrade, Period } from '@/lib/fund-api';
import { filterByPeriod, fmtUsd } from '@/lib/fund-api';

interface Props {
  trades: FundTrade[];
  period: Period;
}

interface SourceStats {
  sleeve: string;
  source: string;
  pnl: number;
  wins: number;
  total: number;
}

// Summarise by sleeve + "source" (note field prefix or description for markets)
export function LearningPanel({ trades, period }: Props) {
  const settled = filterByPeriod(trades, period).filter((t) => t.pnl !== null);
  if (settled.length === 0) return null;

  const map = new Map<string, SourceStats>();
  for (const t of settled) {
    // extract the source from the note (e.g. "copy Ace" -> "Ace")
    const raw = t.note.replace(/^copy /, '').split(':')[0] || t.description.slice(0, 28);
    const key = `${t.sleeve}|${raw}`;
    const existing = map.get(key) ?? { sleeve: t.sleeve, source: raw, pnl: 0, wins: 0, total: 0 };
    existing.pnl += t.pnl ?? 0;
    existing.wins += (t.pnl ?? 0) > 0 ? 1 : 0;
    existing.total += 1;
    map.set(key, existing);
  }

  const rows = [...map.values()]
    .filter((r) => r.total >= 2)
    .sort((a, b) => b.pnl - a.pnl);

  if (rows.length === 0) return null;

  const SLEEVE_COLORS: Record<string, string> = {
    polymarket: '#a78bfa', sportsbook: '#60a5fa', markets: '#34d399', insiders: '#f59e0b',
  };

  return (
    <div className="card" style={{ padding: '1rem 1.25rem', marginBottom: '1.5rem' }}>
      <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase',
                    letterSpacing: '0.07em', color: 'var(--muted)', marginBottom: '0.75rem' }}>
        Attribution — what's actually working
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        {rows.slice(0, 10).map((r, i) => {
          const sleeveColor = SLEEVE_COLORS[r.sleeve] ?? 'var(--muted)';
          const wr = r.total > 0 ? (r.wins / r.total) * 100 : 0;
          const barPct = Math.min(100, Math.abs(r.pnl) / Math.max(...rows.map((x) => Math.abs(x.pnl))) * 100);
          const isPos = r.pnl >= 0;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ width: 80, flexShrink: 0, fontSize: '0.65rem', fontWeight: 700,
                             padding: '0.1rem 0.35rem', borderRadius: 999,
                             background: `${sleeveColor}22`, color: sleeveColor, textAlign: 'center' }}>
                {r.sleeve}
              </span>
              <span style={{ minWidth: 160, fontSize: '0.8rem', overflow: 'hidden',
                             textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {r.source}
              </span>
              <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--border)',
                             overflow: 'hidden' }}>
                <div style={{ width: `${barPct}%`, height: '100%', borderRadius: 3,
                               background: isPos ? 'var(--positive)' : 'var(--danger)',
                               transition: 'width 0.4s ease' }} />
              </div>
              <span style={{ width: 80, textAlign: 'right', fontWeight: 700, fontSize: '0.85rem',
                             color: isPos ? 'var(--positive)' : 'var(--danger)' }}>
                {isPos ? '+' : ''}{fmtUsd(r.pnl, true)}
              </span>
              <span style={{ width: 48, textAlign: 'right', fontSize: '0.75rem', color: 'var(--muted)' }}>
                {wr.toFixed(0)}% wr
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
