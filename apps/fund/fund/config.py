"""
Fund configuration. Everything secret comes from environment variables —
never hardcode keys. Defaults are deliberately conservative and PAPER-first.

The fund runs three "sleeves" (independent profit engines under one
risk manager):

  markets     — the multi-strategy Alpaca bot (stocks/ETFs/crypto).
                Cash for this sleeve lives in your Alpaca (paper) account.
  polymarket  — copy-trades consistently profitable Polymarket wallets
                discovered from the public leaderboard.
  sportsbook  — +EV bets where soft books misprice vs the de-vigged
                sharp (Pinnacle) line, plus 2-way arbitrage.

polymarket + sportsbook trade against an internal paper ledger by default.
"""

import os
from pathlib import Path

FUND_ROOT = Path(__file__).resolve().parent.parent  # apps/fund
DATA_DIR = Path(os.environ.get("FUND_DATA_DIR", str(FUND_ROOT / "data")))

# ------------------------------------------------------------------ fund ---
# PAPER mode is the default and the only mode for sportsbook (books have no
# execution API). Markets sleeve uses Alpaca's paper endpoint while PAPER.
PAPER = os.environ.get("FUND_LIVE", "") != "1"

# Logical bankroll for the ledger-managed sleeves (polymarket + sportsbook).
START_BANKROLL = float(os.environ.get("FUND_BANKROLL", "10000"))

# Sleeve allocation as fractions of START_BANKROLL. The markets sleeve's
# capital is whatever sits in the Alpaca account; its number here is only
# used for reporting context.
ALLOCATIONS = {
    "markets": float(os.environ.get("ALLOC_MARKETS", "0.50")),
    "polymarket": float(os.environ.get("ALLOC_POLYMARKET", "0.30")),
    "sportsbook": float(os.environ.get("ALLOC_SPORTSBOOK", "0.20")),
}
ENABLED_SLEEVES = [
    s.strip()
    for s in os.environ.get(
        "SLEEVES", "markets,polymarket,sportsbook,insiders"
    ).split(",")
    if s.strip()
]

# ------------------------------------------------------------------ risk ---
KELLY_FRACTION = float(os.environ.get("KELLY_FRACTION", "0.25"))  # quarter-Kelly
MAX_STAKE_PCT = float(os.environ.get("MAX_STAKE_PCT", "0.02"))    # per bet/copy
DAILY_LOSS_LIMIT = float(os.environ.get("DAILY_LOSS_LIMIT", "0.03"))
MAX_DRAWDOWN = float(os.environ.get("MAX_DRAWDOWN", "0.15"))      # hard halt

POLL_SECONDS = int(os.environ.get("FUND_POLL_SECONDS", "300"))
LOG_FILE = str(DATA_DIR / "fund.log")
TRADE_LOG = str(DATA_DIR / "trades.csv")
LEDGER_FILE = str(DATA_DIR / "ledger.json")

# ---------------------------------------------------------------- reports ---
REPORT_WEBHOOK_URL = os.environ.get("REPORT_WEBHOOK_URL", "")
MORNING_REPORT_HOUR = 7
EVENING_REPORT_HOUR = 21

# =================================================================== markets
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")

RISK_PER_TRADE = 0.01        # 1% of equity risked per trade, hard stop
ATR_PERIOD = 14
ATR_STOP_MULT = 2.0          # stop distance = 2 x ATR
MAX_RISK_ON_POSITIONS = 2    # correlation filter: max concurrent risk-on longs
RISK_ON_GROUP = {"SPY", "QQQ", "BTC/USD"}
MAX_TOTAL_POSITIONS = 5
HISTORY_BARS = 200

# strategy: "mean_reversion" | "momentum_breakout" | "trend_following"
INSTRUMENTS = {
    "SPY": {  # S&P 500 ETF
        "strategy": "mean_reversion",
        "timeframe_min": 15,
        "asset_class": "stock",
        "params": {"lookback": 20, "z_entry": 2.0, "z_exit": 0.25},
    },
    "QQQ": {  # Nasdaq-100 ETF
        "strategy": "mean_reversion",
        "timeframe_min": 15,
        "asset_class": "stock",
        "params": {"lookback": 20, "z_entry": 2.0, "z_exit": 0.25},
    },
    "BTC/USD": {  # Bitcoin (24/7)
        "strategy": "momentum_breakout",
        "timeframe_min": 60,
        "asset_class": "crypto",
        "params": {"breakout_lookback": 20, "exit_lookback": 10},
    },
    "GLD": {  # Gold ETF
        "strategy": "trend_following",
        "timeframe_min": 240,
        "asset_class": "stock",
        "params": {"fast_ema": 20, "slow_ema": 50},
    },
    "USO": {  # Oil ETF
        "strategy": "trend_following",
        "timeframe_min": 240,
        "asset_class": "stock",
        "params": {"fast_ema": 20, "slow_ema": 50},
    },
}

# ================================================================ polymarket
PM_DATA_API = "https://data-api.polymarket.com"
PM_CLOB_API = "https://clob.polymarket.com"
PM_GAMMA_API = "https://gamma-api.polymarket.com"

# Leader discovery: a wallet must rank in the top PM_TOP_N by PnL on BOTH
# windows (recent AND sustained) to be auto-followed — that is the
# "consistent winner" filter, not a one-lucky-bet filter.
PM_WINDOWS = ("1w", "1m")
PM_TOP_N = int(os.environ.get("PM_TOP_N", "50"))
PM_MIN_PNL = float(os.environ.get("PM_MIN_PNL", "25000"))  # USD per window
PM_MAX_FOLLOWED = int(os.environ.get("PM_MAX_FOLLOWED", "8"))
PM_LEADER_REFRESH_HOURS = 24
# Manually pin wallets you trust (comma-separated 0x addresses).
PM_FOLLOW_WALLETS = [
    w.strip().lower()
    for w in os.environ.get("PM_FOLLOW_WALLETS", "").split(",")
    if w.strip()
]

PM_MIN_LEADER_TRADE_USD = float(os.environ.get("PM_MIN_LEADER_TRADE_USD", "500"))
PM_MIN_PRICE = 0.05          # skip near-resolved / longshot copies
PM_MAX_PRICE = 0.93
PM_MAX_SLIPPAGE = 0.05       # skip copy if market moved >5c past leader's price
PM_STOP_LOSS_FRAC = 0.50     # exit if mark drops 50% below our entry
PM_TAKE_PROFIT_PRICE = 0.98  # exit when essentially resolved in our favor
# Skip ultra-short markets (15-min crypto up/down etc.) — uncopyable noise.
PM_SKIP_SLUG_PATTERNS = ("updown", "-15m-", "-1h-", "hourly")

# ================================================================== insiders
# Copy-trades two public disclosure streams through the Alpaca account:
# congressional STOCK Act filings and superinvestor 13F filings.
QUIVER_API_KEY = os.environ.get("QUIVER_API_KEY", "")  # optional, best source
EDGAR_USER_AGENT = os.environ.get(
    "EDGAR_USER_AGENT", "fund-bot admin@example.com"  # SEC requires a contact UA
)

INS_LOOKBACK_DAYS = int(os.environ.get("INS_LOOKBACK_DAYS", "30"))
INS_MIN_TRADE_USD = float(os.environ.get("INS_MIN_TRADE_USD", "15000"))
INS_BASE_STAKE_PCT = float(os.environ.get("INS_BASE_STAKE_PCT", "0.01"))
INS_MAX_POSITIONS = int(os.environ.get("INS_MAX_POSITIONS", "10"))
INS_MAX_HOLD_DAYS = int(os.environ.get("INS_MAX_HOLD_DAYS", "90"))

# Empty = follow every filer above the size floor; otherwise only filers
# whose name contains one of these (comma-separated, case-insensitive).
INS_FOLLOW_POLITICIANS = [
    p.strip().lower()
    for p in os.environ.get("INS_FOLLOW_POLITICIANS", "").split(",")
    if p.strip()
]
# Emphasis ("the Trump factor"): filers matching these names and trades in
# these tickers get INS_EMPHASIS_MULT x stake. Donald Trump as President
# files no trade disclosures — this catches Trump family members in
# Congress, allies you add, and Trump-linked tickers.
INS_EMPHASIS_NAMES = ["trump"] + [
    n.strip().lower()
    for n in os.environ.get("INS_EMPHASIS_NAMES", "").split(",")
    if n.strip()
]
INS_EMPHASIS_TICKERS = {
    t.strip().upper()
    for t in os.environ.get("INS_EMPHASIS_TICKERS", "DJT").split(",")
    if t.strip()
}
INS_EMPHASIS_MULT = float(os.environ.get("INS_EMPHASIS_MULT", "2.0"))

# Superinvestor 13F funds to track: {display name: CIK}.
INS_13F_FUNDS = {
    "Berkshire Hathaway (Buffett)": "0001067983",
    "Pershing Square (Ackman)": "0001336528",
    "Duquesne Family Office (Druckenmiller)": "0001536411",
    "Appaloosa (Tepper)": "0001656456",
    "Scion Asset Management (Burry)": "0001649339",
}
INS_13F_WEIGHT = 0.5  # 13Fs are 45+ days stale -> half-size copies

# ================================================================ sportsbook
THE_ODDS_API_KEY = os.environ.get("THE_ODDS_API_KEY", "")
THE_ODDS_API_BASE_URL = os.environ.get(
    "THE_ODDS_API_BASE_URL", "https://api.the-odds-api.com/v4"
)
SB_SPORTS = [
    s.strip()
    for s in os.environ.get(
        "SB_SPORTS", "basketball_nba,baseball_mlb,icehockey_nhl,soccer_epl"
    ).split(",")
    if s.strip()
]
SB_REGIONS = os.environ.get("SB_REGIONS", "us,eu")
SB_SHARP_BOOK = "pinnacle"   # the "winner" we piggyback: sharpest book's line
SB_MIN_EV = float(os.environ.get("SB_MIN_EV", "0.03"))   # 3% edge after de-vig
SB_MAX_DECIMAL_ODDS = 6.0    # skip longshots; EV estimates are noisiest there
SB_MAX_BETS_PER_EVENT = 1
SB_ARB_TOTAL_STAKE_PCT = 0.04  # arb is near-riskless: allow 2x normal stake
SB_SETTLE_DAYS_FROM = 3
