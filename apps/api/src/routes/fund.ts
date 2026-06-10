/**
 * Fund data routes — serves the Python fund's persisted files as JSON so
 * the Next.js dashboard can render them without any Python process dependency.
 *
 * GET /fund/overview      ledger snapshot: equity, cash, P&L, risk, sleeve totals
 * GET /fund/equity-history  equity.csv as [{ts, total, ...sleeves}]
 * GET /fund/trades          trades.csv as [{ts, sleeve, action, description,
 *                             qty, price, pnl, note}], newest first
 *
 * All endpoints return empty / zero state if the data files haven't been
 * written yet (the fund hasn't run a single cycle).
 */

import type { FastifyInstance } from 'fastify';
import { existsSync, readFileSync } from 'fs';
import path from 'path';

// Default: sibling directory within the monorepo.
// Override with FUND_DATA_DIR when deployed elsewhere.
const DATA_DIR =
  process.env.FUND_DATA_DIR ??
  path.resolve(process.cwd(), '../fund/data');

function dataPath(file: string) {
  return path.join(DATA_DIR, file);
}

function safeReadJson(file: string): unknown {
  const p = dataPath(file);
  if (!existsSync(p)) return null;
  try {
    return JSON.parse(readFileSync(p, 'utf8'));
  } catch {
    return null;
  }
}

// Minimal quoted CSV parser — handles the description column which can
// contain commas inside double-quotes.
function parseCsv(raw: string): Record<string, string>[] {
  const lines = raw.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = splitCsvRow(lines[0]);
  return lines.slice(1).map((line) => {
    const vals = splitCsvRow(line);
    const row: Record<string, string> = {};
    headers.forEach((h, i) => { row[h.trim()] = (vals[i] ?? '').trim(); });
    return row;
  });
}

function splitCsvRow(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let inQuote = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') { inQuote = !inQuote; continue; }
    if (c === ',' && !inQuote) { out.push(cur); cur = ''; continue; }
    cur += c;
  }
  out.push(cur);
  return out;
}

function safeReadCsv(file: string): Record<string, string>[] {
  const p = dataPath(file);
  if (!existsSync(p)) return [];
  try {
    return parseCsv(readFileSync(p, 'utf8'));
  } catch {
    return [];
  }
}

// Compute SimBroker equity from the raw positions stored in ledger.json
function simBrokerEquity(sim: Record<string, unknown> | null): number | null {
  if (!sim) return null;
  const cash = Number(sim.cash ?? 0);
  const positions = (sim.positions ?? {}) as Record<string, Record<string, number>>;
  let posValue = 0;
  for (const pos of Object.values(positions)) {
    posValue += (pos.qty ?? 0) * (pos.last ?? pos.avg_entry_price ?? 0);
  }
  return cash + posValue;
}

export async function fundRoutes(app: FastifyInstance) {
  // ---------------------------------------------------------------- overview
  app.get('/fund/overview', async () => {
    const ledger = safeReadJson('ledger.json') as Record<string, unknown> | null;

    if (!ledger) {
      return {
        equity: 0,
        ledger_equity: 0,
        sim_equity: null,
        cash: { polymarket: 0, sportsbook: 0 },
        realized_pnl: { polymarket: 0, sportsbook: 0 },
        open_positions: 0,
        last_updated: null,
        risk: { peak_equity: 0, day_start_equity: 0, hard_halt: null, daily_halt: null },
        sim_broker: null,
      };
    }

    const cash = (ledger.cash ?? {}) as Record<string, number>;
    const realized = (ledger.realized_pnl ?? {}) as Record<string, number>;
    const risk = (ledger.risk ?? {}) as Record<string, unknown>;
    const positions = ((ledger.positions ?? []) as unknown[]).filter(
      (p) => (p as Record<string, string>).status === 'open',
    );
    const sim = (ledger.sim_broker ?? null) as Record<string, unknown> | null;
    const simEq = simBrokerEquity(sim);

    // Ledger equity: cash + open ledger positions marked at current price
    let ledgerEq = Object.values(cash).reduce((s, v) => s + Number(v), 0);
    for (const p of positions) {
      const pos = p as Record<string, unknown>;
      if ((pos.kind as string) === 'shares') {
        ledgerEq += (Number(pos.qty ?? 0)) * Number(pos.mark ?? pos.entry_price ?? 0);
      } else {
        ledgerEq += Number(pos.stake ?? 0);
      }
    }

    const totalEquity = ledgerEq + (simEq ?? 0);

    return {
      equity: totalEquity,
      ledger_equity: ledgerEq,
      sim_equity: simEq,
      cash,
      realized_pnl: realized,
      open_positions: positions.length + (sim ? Object.keys((sim.positions ?? {}) as object).length : 0),
      last_updated: (ledger.created as string | null) ?? null,
      risk: {
        peak_equity: Number(risk.peak_equity ?? 0),
        day_start_equity: Number(risk.day_start_equity ?? 0),
        hard_halt: (risk.hard_halt as string | null) ?? null,
        daily_halt: (risk.daily_halt as string | null) ?? null,
      },
      sim_broker: sim
        ? {
            cash: Number(sim.cash ?? 0),
            position_count: Object.keys((sim.positions ?? {}) as object).length,
            equity: simEq,
          }
        : null,
    };
  });

  // --------------------------------------------------------- equity history
  app.get('/fund/equity-history', async () => {
    const rows = safeReadCsv('equity.csv');
    return {
      points: rows.map((r) => ({
        ts: r.timestamp ?? '',
        total: Number(r.total ?? 0),
        markets: r.markets != null ? Number(r.markets) : undefined,
        polymarket: r.polymarket != null ? Number(r.polymarket) : undefined,
        sportsbook: r.sportsbook != null ? Number(r.sportsbook) : undefined,
      })),
    };
  });

  // --------------------------------------------------------------- trades
  app.get('/fund/trades', async () => {
    const rows = safeReadCsv('trades.csv');
    // newest first
    const trades = rows
      .slice()
      .reverse()
      .map((r) => ({
        ts: r.timestamp ?? '',
        sleeve: r.sleeve ?? '',
        action: r.action ?? '',
        description: r.description ?? '',
        qty: Number(r.qty ?? 0),
        price: Number(r.price ?? 0),
        pnl: r.pnl !== '' && r.pnl != null ? Number(r.pnl) : null,
        note: r.note ?? '',
      }));
    return { trades };
  });
}
