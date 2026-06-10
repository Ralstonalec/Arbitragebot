"""
Markets sleeve — the multi-strategy Alpaca bot as a fund sleeve.

Five instruments, three strategies (mean reversion, momentum breakout,
trend following), ATR sizing, hard 1% stops, correlation filter. Cash and
positions live in the Alpaca (paper) account; the fund pulls equity from
there for reporting and the global kill switch gates new entries.
"""

import csv
import os
from datetime import datetime

from ... import config
from ..base import Sleeve
from . import sizing
from .strategies import get_signal, atr


class MarketsSleeve(Sleeve):
    name = "markets"
    ledger_managed = False

    def __init__(self, ledger):
        super().__init__(ledger)
        self.broker = None
        self.last_bar_time = {}   # symbol -> timestamp of last bar acted on
        self.crypto_stops = {}    # symbol -> software stop price
        if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
            self.disable("ALPACA_API_KEY / ALPACA_SECRET_KEY not set")
            return
        try:
            from .broker import Broker
            self.broker = Broker()
            mode = "PAPER" if config.PAPER else "*** LIVE MONEY ***"
            self.log.info(f"Markets sleeve up in {mode} mode. "
                          f"Equity: ${self.broker.equity():,.2f}")
        except Exception as e:
            self.disable(f"Alpaca init failed: {e}")

    def equity(self) -> float | None:
        if not self.enabled or self.broker is None:
            return None
        try:
            return self.broker.equity()
        except Exception as e:
            self.log.error("equity fetch failed: %s", e)
            return None

    def _log_trade(self, action, symbol, qty, price, note=""):
        new_file = not os.path.exists(config.TRADE_LOG)
        with open(config.TRADE_LOG, "a", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["timestamp", "sleeve", "action", "description",
                            "qty", "price", "pnl", "note"])
            w.writerow([datetime.now().isoformat(), self.name, action, symbol,
                        qty, price, "", note])

    def cycle(self, allow_entries: bool):
        if not self.enabled:
            return
        positions = self.broker.open_positions()
        equity = self.broker.equity()
        stocks_open = self.broker.market_open()

        for symbol, cfg in config.INSTRUMENTS.items():
            try:
                self._handle(symbol, cfg, positions, equity, stocks_open,
                             allow_entries)
            except Exception as e:
                self.log.error("%s: %s", symbol, e)

    def _handle(self, symbol, cfg, positions, equity, stocks_open, allow_entries):
        is_crypto = cfg["asset_class"] == "crypto"
        if not is_crypto and not stocks_open:
            return  # stock market closed

        df = self.broker.get_bars(symbol, cfg["asset_class"], cfg["timeframe_min"])
        if df.empty:
            return

        in_position = symbol in positions

        # --- software stop for crypto (stocks have exchange-side stops) ---
        if is_crypto and in_position and symbol in self.crypto_stops:
            last_price = float(df["close"].iloc[-1])
            if last_price <= self.crypto_stops[symbol]:
                self.broker.close_position(symbol)
                self._log_trade("STOP", symbol, positions[symbol]["qty"], last_price)
                del self.crypto_stops[symbol]
                return

        # --- only act once per completed bar ---
        latest_bar = df.index[-1]
        if self.last_bar_time.get(symbol) == latest_bar:
            return
        self.last_bar_time[symbol] = latest_bar

        signal = get_signal(cfg["strategy"], df, cfg["params"], in_position)
        price = float(df["close"].iloc[-1])

        if signal == "long" and not in_position:
            if not allow_entries:
                self.log.info("%s: entry signal ignored (fund risk halt)", symbol)
                return
            if not sizing.correlation_filter_allows(symbol, positions):
                self.log.info("%s: entry blocked by correlation filter", symbol)
                return
            atr_val = atr(df, config.ATR_PERIOD)
            qty, stop = sizing.position_size(equity, price, atr_val)
            if qty <= 0:
                return
            self.broker.buy_with_stop(symbol, cfg["asset_class"], qty, stop)
            if is_crypto:
                self.crypto_stops[symbol] = stop
            self._log_trade("BUY", symbol, qty, price, f"stop={stop}")

        elif signal == "flat" and in_position:
            self.broker.close_position(symbol)
            self.crypto_stops.pop(symbol, None)
            self._log_trade("SELL", symbol, positions[symbol]["qty"], price,
                            "signal exit")
