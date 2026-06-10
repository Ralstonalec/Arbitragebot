"""
SimBroker — built-in paper trading account, no signup required.

Implements the same interface as the Alpaca Broker (equity, open_positions,
market_open, get_bars, buy_with_stop, close_position, last_price) but holds
cash/positions in the fund ledger and fills at live Yahoo Finance prices.
The markets and insiders sleeves fall back to it automatically when Alpaca
keys aren't set, so the whole fund runs in paper with zero accounts.

Differences from a real (even paper) broker, stated honestly:
  - Fills are at the last traded price: no spread, no slippage, no partial
    fills. Real results will be a little worse.
  - Stops are software-side, enforced when prices are refreshed each poll
    cycle (a real broker holds stock stops on the exchange).
  - Yahoo intraday data is slightly delayed. Fine at 15-min+ horizons.
"""

import json
import logging
import urllib.request
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd

from ... import config

log = logging.getLogger("fund.simbroker")

_NY = ZoneInfo("America/New_York")
PRICE_TTL_SECONDS = 300

# Yahoo intervals: 240-min bars are resampled from hourly
_INTERVALS = {15: ("15m", "30d"), 60: ("60m", "120d"), 240: ("60m", "240d")}


def _yahoo_symbol(symbol: str) -> str:
    return symbol.replace("/", "-")  # BTC/USD -> BTC-USD


def _fetch_chart(symbol: str, interval: str, range_: str) -> pd.DataFrame:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{_yahoo_symbol(symbol)}?interval={interval}&range={range_}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (fund-bot)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    result = data["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    df = pd.DataFrame(
        {k: quote[k] for k in ("open", "high", "low", "close", "volume")},
        index=pd.to_datetime(result["timestamp"], unit="s", utc=True),
    ).dropna(subset=["close"])
    return df


class SimBroker:
    """Drop-in paper broker. State lives in ledger.state['sim_broker']."""

    def __init__(self, ledger):
        self.ledger = ledger
        self.state = ledger.state.setdefault("sim_broker", {
            "cash": config.START_BANKROLL * config.ALLOCATIONS["markets"],
            "positions": {},  # symbol -> {qty, avg_entry_price, stop, last}
        })
        self._price_checked_at = 0.0
        log.info(f"Internal paper broker active (Yahoo data) — cash "
                 f"${self.state['cash']:,.2f}. Set ALPACA_API_KEY for "
                 f"realistic broker fills.")

    # ------------------------------------------------------------- account
    def equity(self) -> float:
        self._refresh_marks()
        positions = self.state["positions"]
        return self.state["cash"] + sum(
            p["qty"] * p.get("last", p["avg_entry_price"]) for p in positions.values()
        )

    def open_positions(self) -> dict:
        self._refresh_marks()  # also enforces software stops
        out = {}
        for sym, p in self.state["positions"].items():
            last = p.get("last", p["avg_entry_price"])
            out[sym] = {
                "qty": p["qty"],
                "avg_entry_price": p["avg_entry_price"],
                "unrealized_pl": (last - p["avg_entry_price"]) * p["qty"],
            }
        return out

    def market_open(self) -> bool:
        now = datetime.now(_NY)
        return (now.weekday() < 5
                and dtime(9, 30) <= now.time() <= dtime(16, 0))

    # ---------------------------------------------------------------- data
    def get_bars(self, symbol: str, asset_class: str, timeframe_min: int,
                 limit: int = config.HISTORY_BARS) -> pd.DataFrame:
        interval, range_ = _INTERVALS.get(timeframe_min, ("1d", "1y"))
        df = _fetch_chart(symbol, interval, range_)
        if timeframe_min == 240 and not df.empty:
            df = df.resample("4h").agg(
                {"open": "first", "high": "max", "low": "min",
                 "close": "last", "volume": "sum"}).dropna(subset=["close"])
        if not df.empty:
            self._mark(symbol, float(df["close"].iloc[-1]))
        return df.tail(limit)

    def last_price(self, symbol: str) -> float | None:
        try:
            df = _fetch_chart(symbol, "5m", "1d")
            price = float(df["close"].iloc[-1])
            self._mark(symbol, price)
            return price
        except Exception as e:
            log.info("%s: no price (%s)", symbol, e)
            return None

    # -------------------------------------------------------------- orders
    def buy_with_stop(self, symbol: str, asset_class: str, qty: float,
                      stop_price: float):
        price = self.last_price(symbol)
        if price is None:
            raise RuntimeError(f"no price for {symbol}")
        cost = qty * price
        if cost > self.state["cash"]:
            raise RuntimeError(f"insufficient sim cash for {symbol} "
                               f"(${cost:,.2f} > ${self.state['cash']:,.2f})")
        self.state["cash"] -= cost
        self.state["positions"][symbol] = {
            "qty": qty, "avg_entry_price": price, "stop": stop_price,
            "last": price, "opened": datetime.now(_NY).isoformat(),
        }
        self.ledger.save()
        log.info("SIM BUY %s %s @ %.2f (stop %s)", qty, symbol, price, stop_price)

    def close_position(self, symbol: str):
        pos = self.state["positions"].pop(symbol, None)
        if pos is None:
            return
        price = self.last_price(symbol) or pos.get("last", pos["avg_entry_price"])
        self.state["cash"] += pos["qty"] * price
        self.ledger.save()
        log.info("SIM CLOSED %s @ %.2f (entry %.2f, P&L %+.2f)", symbol, price,
                 pos["avg_entry_price"],
                 (price - pos["avg_entry_price"]) * pos["qty"])

    # ------------------------------------------------------------ internal
    def _mark(self, symbol: str, price: float):
        pos = self.state["positions"].get(symbol)
        if pos:
            pos["last"] = price

    def _refresh_marks(self):
        """Refresh held-symbol prices (throttled) and fire software stops."""
        import time as _time
        now = _time.time()
        if now - self._price_checked_at < PRICE_TTL_SECONDS:
            return
        self._price_checked_at = now
        for symbol in list(self.state["positions"]):
            pos = self.state["positions"].get(symbol)
            price = self.last_price(symbol)
            if price is None or pos is None:
                continue
            stop = pos.get("stop")
            if stop and price <= stop:
                log.info("SIM STOP fired: %s at %.2f (stop %.2f)",
                         symbol, price, stop)
                self.state["cash"] += pos["qty"] * stop  # assume stop fill
                del self.state["positions"][symbol]
                self.ledger.save()
