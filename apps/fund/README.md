# The Fund — multi-sleeve trading & betting bot

One bankroll, one risk manager, three independent profit engines
("sleeves"). The goal is to scan **every** market the fund can reach for
positive expected value and put capital only where an edge is measurable.

| Sleeve | Where the edge comes from | Execution |
|---|---|---|
| **markets** | Multi-strategy Alpaca bot: mean reversion (SPY/QQQ), momentum breakout (BTC), trend following (GLD/USO). ATR sizing, hard 1% stops, correlation filter. | Real orders to Alpaca **paper** account |
| **polymarket** | **Copy-trading consistent winners**: follows wallets that rank in the top-50 PnL on Polymarket on *both* the 1-week and 1-month leaderboards, and mirrors their entries/exits scaled to our bankroll. | Internal paper ledger at live CLOB prices |
| **sportsbook** | **Piggybacking the sharps**: de-vigs Pinnacle's line into fair probabilities and bets soft books priced ≥3% above fair (+EV), plus cross-book arbitrage when best prices imply <100%. | Internal paper ledger, auto-settled from real scores |

## ⚠️ Read this first

- **No bot guarantees profit, including this one.** Every sleeve here has
  real, known failure modes (below). The paper ledger exists to measure
  whether the edges are real for *you* before any real dollar moves.
- **Everything starts in PAPER mode.** Run it for **at least 2–3 months**
  and judge the trades.csv record like an auditor, not a fan.
- **Copy-trading lag is real**: you enter *after* the leader moved the
  price (the bot skips copies that slipped >5¢, but you still pay the lag).
  Leaderboard winners can also mean-revert, get lucky, or be farming volume.
- **Sportsbooks have no execution API** — the sportsbook sleeve is
  structurally paper-only. Its value is telling you (with settled, honest
  numbers) whether the +EV/arb opportunities the platform surfaces would
  have made money. Real betting means a human placing those bets, and books
  limit winners fast.
- Nothing here is financial advice. Never fund this with money you can't
  afford to lose entirely.

## Quick start

```bash
cd apps/fund
pip install -r requirements.txt

# minimum config — every key is optional, sleeves disable themselves gracefully
export ALPACA_API_KEY="..."        # markets sleeve (free paper keys: alpaca.markets)
export ALPACA_SECRET_KEY="..."
export THE_ODDS_API_KEY="..."      # sportsbook sleeve (same key as the TS platform)
                                   # polymarket sleeve needs NO key (public APIs)

python run.py --once     # one scan cycle + status
python run.py            # the loop (every 5 min)
python run.py --status   # equity, open positions, halts
python run.py --resume   # clear a risk halt after reviewing why it fired
```

All state lives in `apps/fund/data/` (gitignored): `ledger.json` (positions,
cash, risk marks), `trades.csv` (every fill/settle with P&L), `fund.log`.

## Fund-level risk (applies to all sleeves)

| Control | Default | Meaning |
|---|---|---|
| Kelly fraction | 0.25 | Stakes are quarter-Kelly — edge estimates are noisy and full Kelly on a wrong edge is ruin |
| Max stake | 2% of equity | Hard cap per bet/copy regardless of Kelly |
| Daily loss limit | 3% | No new entries for the rest of the day; exits/stops still run |
| Max drawdown | 15% off peak | **Kill switch** — fund halts new entries until you run `--resume` |

## Configuration

Everything is env-driven (see `.env.example`). Highlights:

```bash
FUND_BANKROLL=10000           # logical bankroll for the ledger sleeves
SLEEVES=markets,polymarket,sportsbook
ALLOC_POLYMARKET=0.30         # bankroll split
ALLOC_SPORTSBOOK=0.20
PM_FOLLOW_WALLETS=0xabc...    # pin wallets you trust (comma-separated)
PM_MIN_PNL=25000              # min leaderboard PnL per window to auto-follow
SB_MIN_EV=0.03                # min edge vs de-vigged Pinnacle line
SB_SPORTS=basketball_nba,baseball_mlb,icehockey_nhl,soccer_epl
```

## How "piggybacking winners" actually works here

**Polymarket** — wallet activity is public (on-chain + data API). The sleeve:
1. Daily, pulls the PnL leaderboard for 1-week and 1-month windows and
   follows only wallets in the top-N of **both** with PnL above the floor —
   sustained profit, not one lucky bet. Cap: 8 wallets.
2. Mirrors their meaningful buys (≥$500) at the live midpoint, skipping
   near-resolved prices, 15-minute crypto up/down noise markets, and
   anything that already slipped >5¢ past their fill.
3. Exits when they exit — plus its own seatbelts: 50% stop, take-profit
   near $0.98, and automatic settlement at resolution.

**Sports betting** — individual sharp bettors aren't publicly trackable, so
the sleeve piggybacks the next best thing: **Pinnacle's line**, which is
shaped by sharp money and is the industry benchmark for fair odds. Beating
the de-vigged sharp line ("positive CLV") is the most durable, documented
edge in sports betting. Arbitrage legs are sized so every outcome pays the
same amount.

## Going live (please don't rush this)

- **markets**: set `FUND_LIVE=1` *and* generate live Alpaca keys. Only
  after months of profitable paper records.
- **polymarket**: live execution would require `py-clob-client` plus a
  funded Polygon wallet, and is intentionally not wired up. If the paper
  record holds up for months, that integration is the next step — ask for it.
- **sportsbook**: paper-only forever by design; use the TS dashboard in
  this repo (`apps/web`) as the execution assistant for a human.

## Architecture

```
run.py                      CLI entry
fund/
  config.py                 all knobs, env-driven, PAPER-first
  orchestrator.py           the loop: risk gate -> sleeves -> reports
  ledger.py                 unified paper ledger (JSON state + trades.csv)
  risk.py                   fractional Kelly, daily loss limit, kill switch
  notify.py                 7am / 9pm webhook reports (REPORT_WEBHOOK_URL)
  sleeves/
    base.py                 Sleeve interface
    markets/                the original multi-strategy Alpaca bot
      strategies.py           signal generators (unchanged)
      broker.py               Alpaca data + OTO stop orders
      sizing.py               ATR sizing + correlation filter
      sleeve.py
    polymarket/
      client.py               leaderboard / trades / midpoint / resolution
      sleeve.py                leader discovery + copy logic + seatbelts
    sportsbook/
      oddsapi.py               The Odds API client
      ev.py                    de-vig, +EV detection, arb math
      sleeve.py                scan, bet, auto-settle
```

A sleeve that's missing its API key or dependency disables itself with a
warning; the rest of the fund keeps running. One sleeve crashing cannot
take down another (isolated per-cycle), and a fund-level halt still lets
sleeves manage exits and stops — it only blocks *new* risk.
