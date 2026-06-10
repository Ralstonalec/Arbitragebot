# The Fund — multi-sleeve trading & betting bot

One bankroll, one risk manager, three independent profit engines
("sleeves"). The goal is to scan **every** market the fund can reach for
positive expected value and put capital only where an edge is measurable.

| Sleeve | Where the edge comes from | Execution |
|---|---|---|
| **markets** | Multi-strategy Alpaca bot: mean reversion (SPY/QQQ), momentum breakout (BTC), trend following (GLD/USO). ATR sizing, hard 1% stops, correlation filter. | Real orders to Alpaca **paper** account |
| **polymarket** | **Copy-trading consistent winners**: follows wallets that rank in the top-50 PnL on Polymarket on *both* the 1-week and 1-month leaderboards, and mirrors their entries/exits scaled to our bankroll. | Internal paper ledger at live CLOB prices |
| **sportsbook** | **Piggybacking the sharps**: de-vigs Pinnacle's line into fair probabilities and bets soft books priced ≥3% above fair (+EV), plus cross-book arbitrage when best prices imply <100%. | Internal paper ledger, auto-settled from real scores |
| **insiders** | **Copying disclosed trades of US politicians and top funds**: congressional STOCK Act filings (with a configurable "Trump factor" — emphasized names/tickers get 2× stake) and quarterly 13F filings of superinvestors (Buffett, Ackman, Druckenmiller, Tepper, Burry). | Real orders to the same Alpaca **paper** account, 15% exchange-side stops |

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

**US politicians & top stock traders (insiders sleeve)** — two public
disclosure streams, both with legally-mandated lag you cannot remove:
1. *Congress*: STOCK Act periodic transaction reports (via Quiver
   Quantitative if `QUIVER_API_KEY` is set, else Capitol Trades' public
   endpoint). Purchases ≥ $15k are copied; the same filer selling closes
   our copy; every position carries a 15% exchange-side stop and a 90-day
   max hold. **The Trump factor**: Donald Trump as President files no
   trade disclosures (PTRs come from members of Congress; the President
   files only an annual form) — so the emphasis is implemented as a 2×
   stake multiplier on (a) any filer whose name matches `trump` (family
   members serving in Congress), (b) allies you list in
   `INS_EMPHASIS_NAMES`, and (c) Trump-linked tickers (`DJT` by default).
2. *Superinvestor 13Fs* (SEC EDGAR, free): when a tracked fund files a new
   13F, new positions and >25% adds are copied at half weight (the data is
   45+ days stale), and a fund fully exiting closes our copy. Issuer names
   are mapped to tickers via the SEC registrant list (verified 26/26 on
   Berkshire's live book).

**Sports betting** — individual sharp bettors aren't publicly trackable, so
the sleeve piggybacks the next best thing: **Pinnacle's line**, which is
shaped by sharp money and is the industry benchmark for fair odds. Beating
the de-vigged sharp line ("positive CLV") is the most durable, documented
edge in sports betting. Arbitrage legs are sized so every outcome pays the
same amount.

## Going live — drop money in, it decides

The fund is built so going live is one switch plus funded accounts. With
`FUND_LIVE=1` it sizes every position off **actual balances**, not the
paper bankroll number:

1. **Preflight first** — validates every credential and prints what live
   mode will do, without placing anything:
   ```bash
   python run.py --live-check
   ```
2. **Markets + insiders**: generate **live** Alpaca keys, fund the
   account, set the keys. `FUND_LIVE=1` routes both sleeves to the live
   endpoint; stakes scale off real account equity.
3. **Polymarket**: deposit USDC (Polygon) into a Polymarket account, then:
   ```bash
   export POLYMARKET_PRIVATE_KEY="0x..."   # controls real funds — env only
   export POLYMARKET_FUNDER="0x..."        # proxy wallet if you signed up on the site
   export POLYMARKET_SIGNATURE_TYPE=1      # 1=email login, 2=browser wallet, 0=raw EOA
   ```
   Copies become real Fill-Or-Kill market orders; the sleeve syncs its
   cash from your actual USDC balance every cycle. Resolved winners
   need a one-click redeem in the Polymarket UI.
4. **Sportsbook**: stays paper *structurally* — sportsbooks have no
   execution API. It keeps producing settled +EV/arb records; placing
   those bets is a human job (the TS dashboard assists).

Live mode adds one extra brake on top of everything else: a hard
`MAX_LIVE_STAKE_USD` ceiling (default **$250/position**) so percentage
caps can't compound into big tickets while trust is being earned. The
daily loss limit and the 15% drawdown kill switch apply to real money
exactly as they do on paper. Raise the limits deliberately, in steps,
as the live record accumulates — and only fund it with money you are
truly fine losing.

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
    insiders/
      congress.py              STOCK Act filings (Quiver / Capitol Trades)
      edgar.py                 SEC 13F diffing + issuer->ticker mapping
      sleeve.py                copy logic, Trump emphasis, stops, max-hold
```

A sleeve that's missing its API key or dependency disables itself with a
warning; the rest of the fund keeps running. One sleeve crashing cannot
take down another (isolated per-cycle), and a fund-level halt still lets
sleeves manage exits and stops — it only blocks *new* risk.
