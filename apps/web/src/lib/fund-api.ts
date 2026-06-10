const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

export interface FundOverview {
  equity: number;
  ledger_equity: number;
  sim_equity: number | null;
  cash: Record<string, number>;
  realized_pnl: Record<string, number>;
  open_positions: number;
  last_updated: string | null;
  risk: {
    peak_equity: number;
    day_start_equity: number;
    hard_halt: string | null;
    daily_halt: string | null;
  };
  sim_broker: { cash: number; position_count: number; equity: number | null } | null;
}

export interface EquityPoint {
  ts: string;
  total: number;
  markets?: number;
  polymarket?: number;
  sportsbook?: number;
}

export interface FundTrade {
  ts: string;
  sleeve: string;
  action: string;
  description: string;
  qty: number;
  price: number;
  pnl: number | null;
  note: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchFundOverview = () => get<FundOverview>('/fund/overview');

export const fetchEquityHistory = () =>
  get<{ points: EquityPoint[] }>('/fund/equity-history').then((d) => d.points);

export const fetchFundTrades = () =>
  get<{ trades: FundTrade[] }>('/fund/trades').then((d) => d.trades);

// ----------------------------------------------------------------- helpers
export type Period = 'day' | 'week' | 'month' | '3m' | 'year' | 'ytd' | 'all';

export function filterByPeriod<T extends { ts: string }>(items: T[], period: Period): T[] {
  if (period === 'all') return items;
  const now = Date.now();
  const cutoffs: Record<string, number> = {
    day:   now - 86_400_000,
    week:  now - 7  * 86_400_000,
    month: now - 30 * 86_400_000,
    '3m':  now - 90 * 86_400_000,
    year:  now - 365 * 86_400_000,
    ytd:   new Date(new Date().getFullYear(), 0, 1).getTime(),
  };
  const cutoff = cutoffs[period] ?? 0;
  return items.filter((i) => new Date(i.ts).getTime() >= cutoff);
}

export function fmtUsd(n: number, compact = false): string {
  if (compact && Math.abs(n) >= 1000) {
    return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
  }
  return n.toLocaleString('en-US', {
    style: 'currency', currency: 'USD',
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
}

export function fmtPct(n: number): string {
  return (n >= 0 ? '+' : '') + (n * 100).toFixed(2) + '%';
}
