'use client';

import { useCallback, useEffect, useState } from 'react';
import type { FundOverview, EquityPoint, FundTrade, Period } from '@/lib/fund-api';
import { fetchFundOverview, fetchEquityHistory, fetchFundTrades } from '@/lib/fund-api';
import { PortfolioHero } from '@/components/PortfolioHero';
import { TradeHighlights } from '@/components/TradeHighlights';
import { LearningPanel } from '@/components/LearningPanel';
import { OpenPositions } from '@/components/OpenPositions';

export default function HomePage() {
  const [period, setPeriod] = useState<Period>('all');
  const [overview, setOverview] = useState<FundOverview | null>(null);
  const [history, setHistory] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<FundTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [ov, hist, tr] = await Promise.all([
        fetchFundOverview(),
        fetchEquityHistory(),
        fetchFundTrades(),
      ]);
      setOverview(ov);
      setHistory(hist);
      setTrades(tr);
      setLastRefresh(new Date());
    } catch {
      setError(
        'Could not reach the API. Start the backend with `npm run dev:api` in apps/api.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div className="container" style={{ maxWidth: 1100 }}>
      {/* header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    marginBottom: '1.25rem', paddingTop: '0.5rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>Fund Overview</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {lastRefresh && (
            <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button onClick={load} disabled={loading}
            style={{ padding: '0.3rem 0.75rem', fontSize: '0.8rem' }}>
            {loading ? '↻ Loading…' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', borderRadius: 8, marginBottom: '1rem',
                      background: 'rgba(240,113,120,0.08)', border: '1px solid rgba(240,113,120,0.25)',
                      color: 'var(--danger)', fontSize: '0.875rem' }}>
          {error}
        </div>
      )}

      {/* big equity hero + sparkline + period toggle */}
      <PortfolioHero
        overview={overview}
        history={history}
        period={period}
        onPeriod={setPeriod}
        loading={loading}
      />

      {/* wins / losses */}
      {!loading && (
        <TradeHighlights trades={trades} period={period} />
      )}

      {/* attribution bars */}
      {!loading && (
        <LearningPanel trades={trades} period={period} />
      )}

      {/* open positions */}
      {!loading && (
        <>
          <SectionHeader title="Open Positions" count={overview?.open_positions} />
          <OpenPositions trades={trades} />
        </>
      )}

      {/* recent activity feed */}
      {!loading && trades.length > 0 && (
        <>
          <SectionHeader title="Recent Activity" />
          <RecentTrades trades={trades.slice(0, 20)} />
        </>
      )}
    </div>
  );
}

function SectionHeader({ title, count }: { title: string; count?: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
                  margin: '1.5rem 0 0.6rem' }}>
      <h2 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase',
                   letterSpacing: '0.06em', color: 'var(--muted)' }}>
        {title}
      </h2>
      {count !== undefined && (
        <span style={{ fontSize: '0.75rem', padding: '0.1rem 0.45rem', borderRadius: 999,
                       background: 'var(--border)', color: 'var(--muted)' }}>
          {count}
        </span>
      )}
    </div>
  );
}

const ACTION_STYLES: Record<string, { color: string; bg: string }> = {
  BUY:    { color: '#34d399', bg: 'rgba(52,211,153,0.12)' },
  BET:    { color: '#60a5fa', bg: 'rgba(96,165,250,0.12)' },
  SELL:   { color: '#f07178', bg: 'rgba(240,113,120,0.12)' },
  STOP:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
  SETTLE: { color: '#a78bfa', bg: 'rgba(167,139,250,0.12)' },
};

function RecentTrades({ trades }: { trades: FundTrade[] }) {
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: '2rem' }}>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Action</th>
            <th>Sleeve</th>
            <th>Description</th>
            <th style={{ textAlign: 'right' }}>P&L</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => {
            const s = ACTION_STYLES[t.action] ?? { color: 'var(--muted)', bg: 'transparent' };
            return (
              <tr key={i}>
                <td style={{ color: 'var(--muted)', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                  {fmtTs(t.ts)}
                </td>
                <td>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, padding: '0.1rem 0.4rem',
                                  borderRadius: 999, background: s.bg, color: s.color }}>
                    {t.action}
                  </span>
                </td>
                <td style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>{t.sleeve}</td>
                <td style={{ fontSize: '0.82rem', maxWidth: 340, overflow: 'hidden',
                              textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {t.description}
                </td>
                <td style={{ textAlign: 'right', fontWeight: t.pnl !== null ? 600 : 400,
                              color: t.pnl === null ? 'var(--muted)'
                                    : t.pnl >= 0 ? 'var(--positive)' : 'var(--danger)',
                              fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
                  {t.pnl !== null
                    ? (t.pnl >= 0 ? '+' : '') + t.pnl.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
                    : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function fmtTs(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}
