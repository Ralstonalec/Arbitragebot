"""
Insiders sleeve — copy the people with information or skill edges:

  1. US politicians: congressional STOCK Act disclosures. Buys above the
     size floor are copied; the same politician selling closes our copy.
     "Trump emphasis": filers whose name matches INS_EMPHASIS_NAMES
     (default: trump), and trades in Trump-linked tickers (default: DJT),
     get INS_EMPHASIS_MULT x stake. Note: Donald Trump as President files
     no trade disclosures — the emphasis catches Trump family members in
     Congress, allies you configure, and Trump-linked tickers. Disclosures
     lag the actual trade by up to 45 days; that lag is the cost of this
     signal and it is priced in by smaller stakes.
  2. Top stock traders: quarterly 13F filings of superinvestor funds
     (Berkshire, Pershing Square, Duquesne, ...). New positions / >25%
     adds are copied at half weight (the data is 45+ days stale); a fund
     fully exiting closes our copy.

Execution goes through the same Alpaca (paper) account as the markets
sleeve, with a 15% exchange-side stop on every entry and a max-hold
timeout. The sleeve tracks its own symbols and never touches the markets
sleeve's instruments. Its equity is reported under the markets/Alpaca
account (returned as None here to avoid double counting).
"""

import csv
import os
import time
from datetime import datetime, timezone

from ... import config
from ..base import Sleeve
from . import congress, edgar

STOP_PCT = 0.15
SECONDS_PER_DAY = 86400


def _days_ago(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / SECONDS_PER_DAY
    except ValueError:
        return 1e9


class InsidersSleeve(Sleeve):
    name = "insiders"
    ledger_managed = False

    def __init__(self, ledger):
        super().__init__(ledger)
        self.broker = None
        if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
            self.disable("ALPACA_API_KEY / ALPACA_SECRET_KEY not set "
                         "(insiders sleeve executes through Alpaca)")
            return
        try:
            from ..markets.broker import Broker
            self.broker = Broker()
        except Exception as e:
            self.disable(f"Alpaca init failed: {e}")

    def equity(self) -> float | None:
        return None  # cash lives in the Alpaca account, reported by markets

    # ------------------------------------------------------------- helpers
    def _state(self) -> dict:
        return self.ledger.sleeve_state(self.name)

    def _log_trade(self, action, symbol, qty, price, note=""):
        new_file = not os.path.exists(config.TRADE_LOG)
        with open(config.TRADE_LOG, "a", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["timestamp", "sleeve", "action", "description",
                            "qty", "price", "pnl", "note"])
            w.writerow([datetime.now().isoformat(), self.name, action, symbol,
                        qty, price, "", note])

    def _last_price(self, symbol: str) -> float | None:
        try:
            from alpaca.data.requests import StockLatestTradeRequest
            req = StockLatestTradeRequest(symbol_or_symbols=symbol)
            return float(self.broker.stock_data.get_stock_latest_trade(req)[symbol].price)
        except Exception as e:
            self.log.info("%s: no price (%s) — skipped", symbol, e)
            return None

    def _emphasis(self, politician: str, ticker: str) -> float:
        pol = politician.lower()
        if any(n in pol for n in config.INS_EMPHASIS_NAMES):
            return config.INS_EMPHASIS_MULT
        if ticker.upper() in config.INS_EMPHASIS_TICKERS:
            return config.INS_EMPHASIS_MULT
        return 1.0

    def _followed(self, politician: str) -> bool:
        if not config.INS_FOLLOW_POLITICIANS:
            return True
        pol = politician.lower()
        watched = any(w in pol for w in config.INS_FOLLOW_POLITICIANS)
        emphasized = any(n in pol for n in config.INS_EMPHASIS_NAMES)
        return watched or emphasized

    # --------------------------------------------------------------- trades
    def _buy(self, symbol: str, weight: float, source: str, note: str):
        positions = self._state().setdefault("positions", {})
        if (symbol in positions
                or symbol in config.INSTRUMENTS
                or len(positions) >= config.INS_MAX_POSITIONS):
            return
        price = self._last_price(symbol)
        if price is None or price <= 0:
            return
        equity = self.broker.equity()
        stake = min(equity * config.INS_BASE_STAKE_PCT * weight,
                    equity * config.MAX_STAKE_PCT * 2)
        qty = int(stake / price)
        if qty < 1:
            self.log.info("%s: stake $%.0f < 1 share @ %.2f — skipped",
                          symbol, stake, price)
            return
        stop = round(price * (1 - STOP_PCT), 2)
        self.broker.buy_with_stop(symbol, "stock", qty, stop)
        positions[symbol] = {
            "opened": datetime.now(timezone.utc).isoformat(),
            "source": source, "weight": weight, "qty": qty, "entry": price,
        }
        self._log_trade("BUY", symbol, qty, price, f"{source}: {note} (w={weight:g})")
        self.log.info("COPY BUY %s x%d @ %.2f [%s] %s%s", symbol, qty, price,
                      source, note, " ★emphasis" if weight > 1 else "")

    def _close(self, symbol: str, reason: str):
        positions = self._state().setdefault("positions", {})
        pos = positions.pop(symbol, None)
        if pos is None:
            return
        try:
            self.broker.close_position(symbol)
            price = self._last_price(symbol) or 0.0
            self._log_trade("SELL", symbol, pos["qty"], price, reason)
            self.log.info("COPY EXIT %s (%s)", symbol, reason)
        except Exception as e:
            self.log.error("close %s failed: %s", symbol, e)

    # --------------------------------------------------------------- cycles
    def _reconcile(self):
        """Drop tracked symbols the broker no longer holds (stop fired)."""
        positions = self._state().setdefault("positions", {})
        try:
            held = self.broker.open_positions()
        except Exception:
            return
        for symbol in [s for s in positions if s not in held]:
            pos = positions.pop(symbol)
            self._log_trade("STOP", symbol, pos["qty"], 0, "exchange stop fired")
            self.log.info("%s: exchange stop fired, position gone", symbol)

    def _max_hold_exits(self):
        positions = self._state().setdefault("positions", {})
        for symbol, pos in list(positions.items()):
            if _days_ago(pos["opened"]) >= config.INS_MAX_HOLD_DAYS:
                self._close(symbol, f"max hold {config.INS_MAX_HOLD_DAYS}d")

    def _congress_cycle(self, allow_entries: bool):
        state = self._state()
        processed = state.setdefault("processed", {})
        now = time.time()
        for k in [k for k, ts in processed.items()
                  if now - ts > 90 * SECONDS_PER_DAY]:
            del processed[k]

        positions = state.setdefault("positions", {})
        for t in congress.recent_trades():
            if (t["id"] in processed
                    or _days_ago(t["published"]) > config.INS_LOOKBACK_DAYS
                    or not self._followed(t["politician"])):
                continue
            processed[t["id"]] = now
            source = f"congress:{t['politician']}"

            if t["side"] == "sell":
                pos = positions.get(t["ticker"])
                if pos and pos["source"] == source:
                    self._close(t["ticker"], f"{t['politician']} sold")
                continue

            if not allow_entries or t["usd"] < config.INS_MIN_TRADE_USD:
                continue
            weight = self._emphasis(t["politician"], t["ticker"])
            self._buy(t["ticker"], weight, source,
                      f"${t['usd']:,.0f} on {t['traded']}")

    def _edgar_cycle(self, allow_entries: bool):
        state = self._state()
        # check at most once a day — 13Fs are quarterly
        if time.time() - state.get("edgar_checked_at", 0) < SECONDS_PER_DAY:
            return
        state["edgar_checked_at"] = time.time()
        edgar_state = state.setdefault("edgar", {})
        positions = state.setdefault("positions", {})

        for fund_name, cik in config.INS_13F_FUNDS.items():
            try:
                signals = edgar.new_13f_signals(cik, fund_name, edgar_state)
            except Exception as e:
                self.log.error("13F %s failed: %s", fund_name, e)
                continue
            for s in signals:
                source = f"13f:{s['fund']}"
                if s["side"] == "sell":
                    pos = positions.get(s["ticker"])
                    if pos and pos["source"] == source:
                        self._close(s["ticker"], f"{s['fund']} {s['note']}")
                elif allow_entries:
                    self._buy(s["ticker"], config.INS_13F_WEIGHT, source, s["note"])

    def cycle(self, allow_entries: bool):
        if not self.enabled:
            return
        if not self.broker.market_open():
            return  # stock-only sleeve; queue nothing while closed
        self._reconcile()
        self._max_hold_exits()
        self._congress_cycle(allow_entries)
        self._edgar_cycle(allow_entries)
        self.ledger.save()
