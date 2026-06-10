"""
Unified paper ledger for the ledger-managed sleeves (polymarket, sportsbook).

State is a single JSON file so the fund survives restarts; every fill is
also appended to trades.csv for analysis. The markets sleeve is NOT in
here — its cash and positions live in the Alpaca account and are merged
into fund equity at report time.

Position kinds:
  "shares" — Polymarket outcome shares: value = qty * mark price.
  "bet"    — sportsbook stake at decimal odds: carried at stake until
             settled (won -> stake * odds back, lost -> 0).
"""

import csv
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from . import config

log = logging.getLogger("fund")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Ledger:
    def __init__(self):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = config.LEDGER_FILE
        if os.path.exists(self.path):
            with open(self.path) as f:
                self.state = json.load(f)
        else:
            self.state = {
                "created": _now(),
                "start_bankroll": config.START_BANKROLL,
                "cash": {
                    "polymarket": config.START_BANKROLL * config.ALLOCATIONS["polymarket"],
                    "sportsbook": config.START_BANKROLL * config.ALLOCATIONS["sportsbook"],
                },
                "positions": [],
                "realized_pnl": {"polymarket": 0.0, "sportsbook": 0.0},
                "risk": {},          # peak equity, day-start equity, halt flags
                "sleeve_state": {},  # per-sleeve persistent scratch space
            }
            self.save()
        log.info(
            "Ledger loaded: cash=%s, %d open positions",
            {k: round(v, 2) for k, v in self.state["cash"].items()},
            len(self.open_positions()),
        )

    # ------------------------------------------------------------- persist
    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.state, f, indent=2)
        os.replace(tmp, self.path)

    def sleeve_state(self, sleeve: str) -> dict:
        return self.state["sleeve_state"].setdefault(sleeve, {})

    # ------------------------------------------------------------ accounts
    def cash(self, sleeve: str) -> float:
        return self.state["cash"].get(sleeve, 0.0)

    def open_positions(self, sleeve: str | None = None) -> list[dict]:
        return [
            p for p in self.state["positions"]
            if p["status"] == "open" and (sleeve is None or p["sleeve"] == sleeve)
        ]

    def sleeve_equity(self, sleeve: str) -> float:
        value = 0.0
        for p in self.open_positions(sleeve):
            if p["kind"] == "shares":
                value += p["qty"] * p.get("mark", p["entry_price"])
            else:  # bet carried at stake until settled
                value += p["stake"]
        return self.cash(sleeve) + value

    def ledger_equity(self) -> float:
        return sum(self.sleeve_equity(s) for s in self.state["cash"])

    # ---------------------------------------------------------------- fills
    def _log_trade(self, action, sleeve, description, qty, price, pnl, note):
        new_file = not os.path.exists(config.TRADE_LOG)
        with open(config.TRADE_LOG, "a", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["timestamp", "sleeve", "action", "description",
                            "qty", "price", "pnl", "note"])
            w.writerow([_now(), sleeve, action, description,
                        round(qty, 6), round(price, 6),
                        round(pnl, 2) if pnl is not None else "",
                        note])

    def open_shares(self, sleeve, market_id, description, qty, price, meta) -> dict | None:
        cost = qty * price
        if cost <= 0 or cost > self.cash(sleeve):
            return None
        self.state["cash"][sleeve] -= cost
        pos = {
            "id": uuid.uuid4().hex[:12], "sleeve": sleeve, "kind": "shares",
            "market_id": market_id, "description": description,
            "qty": qty, "entry_price": price, "mark": price,
            "stake": cost, "opened": _now(), "status": "open", "meta": meta,
        }
        self.state["positions"].append(pos)
        self._log_trade("BUY", sleeve, description, qty, price, None,
                        meta.get("note", ""))
        self.save()
        return pos

    def close_shares(self, pos: dict, price: float, note: str = ""):
        proceeds = pos["qty"] * price
        pnl = proceeds - pos["stake"]
        self.state["cash"][pos["sleeve"]] += proceeds
        self.state["realized_pnl"][pos["sleeve"]] += pnl
        pos.update(status="closed", closed=_now(), exit_price=price, pnl=pnl)
        self._log_trade("SELL", pos["sleeve"], pos["description"],
                        pos["qty"], price, pnl, note)
        self.save()

    def open_bet(self, sleeve, market_id, description, stake, odds, meta) -> dict | None:
        if stake <= 0 or stake > self.cash(sleeve):
            return None
        self.state["cash"][sleeve] -= stake
        pos = {
            "id": uuid.uuid4().hex[:12], "sleeve": sleeve, "kind": "bet",
            "market_id": market_id, "description": description,
            "qty": stake, "entry_price": odds, "stake": stake, "odds": odds,
            "opened": _now(), "status": "open", "meta": meta,
        }
        self.state["positions"].append(pos)
        self._log_trade("BET", sleeve, description, stake, odds, None,
                        meta.get("note", ""))
        self.save()
        return pos

    def settle_bet(self, pos: dict, won: bool, note: str = ""):
        payout = pos["stake"] * pos["odds"] if won else 0.0
        pnl = payout - pos["stake"]
        self.state["cash"][pos["sleeve"]] += payout
        self.state["realized_pnl"][pos["sleeve"]] += pnl
        pos.update(status="closed", closed=_now(),
                   result="won" if won else "lost", pnl=pnl)
        self._log_trade("SETTLE", pos["sleeve"], pos["description"],
                        pos["stake"], pos["odds"], pnl,
                        ("won " if won else "lost ") + note)
        self.save()
