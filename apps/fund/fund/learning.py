"""
Self-learning layer: the fund adjusts itself based on realized outcomes.

Every closed trade is an outcome attached to a SOURCE — the leader wallet
that was copied, the politician or 13F fund that was followed, the
bookmaker that was bet at, the instrument a strategy traded. Each cycle
the learner re-scores every source from its recent record (last 50 closed
trades) and hands the sleeves a stake multiplier:

  evidence                                   multiplier
  ------------------------------------------ ----------
  fewer than 4 closed trades                  1.0   (not enough evidence)
  losing money                                0.5   (probation: half stake)
  losing money, 8+ trades, win rate < 35%     0.0   (dropped — stop copying)
  profitable with win rate >= 55%             1.25  (earned trust, capped)

Concretely: a Polymarket leader whose copies keep losing gets halved and
then dropped from the follow list; a bookmaker whose "+EV" bets don't
settle positive stops getting bets; a politician whose disclosures don't
work out stops being copied; an instrument that keeps stopping out gets
its size cut to zero until evidence improves.

Deliberately simple, bounded, and transparent: scores are recomputed from
the persistent trade record every cycle (nothing hidden, survives
restarts), boosts are capped at 1.25x so success can't compound into
oversizing, and all hard risk caps still apply after the multiplier.
Sources earn their way back automatically if later trades win, because
scoring always reflects the recent window, not a permanent verdict.
"""

import csv
import logging
import os
from collections import defaultdict

from . import config

log = logging.getLogger("fund.learning")

MIN_SAMPLE = 4          # trades before any adjustment
DROP_SAMPLE = 8         # trades before a source can be dropped
DROP_WIN_RATE = 0.35
BOOST_WIN_RATE = 0.55
PROBATION_MULT = 0.5
BOOST_MULT = 1.25
WINDOW = 50             # most recent closed trades per source


def _insiders_group(buy_note: str) -> str:
    """'congress:Jane Doe: $32,500 ...' -> 'congress:Jane Doe'"""
    return ":".join(buy_note.split(":")[:2]).strip()


def csv_outcomes() -> list[tuple[str, str, float]]:
    """
    [(sleeve, source, pnl)] for broker-executed sleeves (markets, insiders)
    by FIFO-pairing BUY rows with SELL/STOP rows in trades.csv. The source
    comes from the BUY lot (the sell note says why we exited, not who we
    followed).
    """
    if not os.path.exists(config.TRADE_LOG):
        return []
    open_lots: dict[tuple, list] = defaultdict(list)
    out = []
    with open(config.TRADE_LOG) as f:
        for row in csv.DictReader(f):
            sleeve = row.get("sleeve", "")
            if sleeve not in ("markets", "insiders"):
                continue
            try:
                qty, price = float(row["qty"]), float(row["price"])
            except (ValueError, KeyError):
                continue
            key = (sleeve, row["description"])
            if row["action"] == "BUY":
                group = (_insiders_group(row.get("note", ""))
                         if sleeve == "insiders" else row["description"])
                open_lots[key].append((qty, price, group))
            elif row["action"] in ("SELL", "STOP") and open_lots[key]:
                lot_qty, lot_price, group = open_lots[key].pop(0)
                if price > 0:
                    out.append((sleeve, group,
                                (price - lot_price) * min(qty, lot_qty)))
    return out


def ledger_outcomes(ledger) -> list[tuple[str, str, float]]:
    """[(sleeve, source, pnl)] for ledger-managed sleeves."""
    out = []
    for p in ledger.state["positions"]:
        if p["status"] != "closed" or "pnl" not in p:
            continue
        meta = p.get("meta", {})
        if p["sleeve"] == "polymarket":
            source = meta.get("leader", "?")
        elif p["sleeve"] == "sportsbook":
            source = meta.get("book", "?")
        else:
            continue
        out.append((p["sleeve"], source, p["pnl"]))
    return out


class Learner:
    def __init__(self, ledger):
        self.ledger = ledger
        self.scores: dict[tuple[str, str], dict] = {}
        self._last_mults: dict[tuple[str, str], float] = {}

    def refresh(self):
        per_source: dict[tuple[str, str], list[float]] = defaultdict(list)
        for sleeve, source, pnl in ledger_outcomes(self.ledger) + csv_outcomes():
            per_source[(sleeve, source)].append(pnl)
        self.scores = {}
        for key, pnls in per_source.items():
            recent = pnls[-WINDOW:]
            wins = sum(1 for p in recent if p > 0)
            self.scores[key] = {"n": len(recent), "pnl": sum(recent),
                                "win_rate": wins / len(recent)}
        self._log_changes()

    def multiplier(self, sleeve: str, source: str) -> float:
        s = self.scores.get((sleeve, source))
        if s is None or s["n"] < MIN_SAMPLE:
            return 1.0
        if s["pnl"] < 0:
            if s["n"] >= DROP_SAMPLE and s["win_rate"] < DROP_WIN_RATE:
                return 0.0
            return PROBATION_MULT
        if s["win_rate"] >= BOOST_WIN_RATE:
            return BOOST_MULT
        return 1.0

    def blacklisted(self, sleeve: str, source: str) -> bool:
        return self.multiplier(sleeve, source) == 0.0

    def _log_changes(self):
        for key, s in self.scores.items():
            mult = self.multiplier(*key)
            old = self._last_mults.get(key, 1.0)
            if mult != old:
                self.ledger.state.setdefault("learning_log", []).append(
                    {"source": f"{key[0]}/{key[1]}", "from": old, "to": mult,
                     "n": s["n"], "pnl": round(s["pnl"], 2),
                     "win_rate": round(s["win_rate"], 3)})
                log.warning("LEARNED: %s/%s %.2gx -> %.2gx "
                            "(%d trades, P&L %+.2f, win rate %.0f%%)",
                            key[0], key[1][:30], old, mult,
                            s["n"], s["pnl"], s["win_rate"] * 100)
            self._last_mults[key] = mult

    def summary(self) -> list[str]:
        if not self.scores:
            return ["  no closed trades yet — all sources at neutral 1.0x"]
        lines = []
        ranked = sorted(self.scores.items(),
                        key=lambda kv: self.multiplier(*kv[0]))
        for key, s in ranked:
            mult = self.multiplier(*key)
            if mult == 1.0 and s["n"] < MIN_SAMPLE:
                continue
            tag = {0.0: "DROPPED ", PROBATION_MULT: "probation",
                   BOOST_MULT: "boosted ", 1.0: "neutral "}[mult]
            lines.append(f"  {tag} {mult:>4.2g}x  {key[0]}/{key[1][:38]:<38} "
                         f"{s['n']:>3} trades  {s['pnl']:>+10,.2f}  "
                         f"wr {s['win_rate']:.0%}")
        return lines or ["  all sources neutral (insufficient evidence)"]
