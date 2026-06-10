"""
Sportsbook sleeve — +EV vs the sharp line, plus cross-book arbitrage.

Two ways it makes (paper) money:
  1. +EV bets: de-vig Pinnacle's h2h line into fair probabilities, then
     bet at soft books offering prices where fair_prob * price - 1 >= SB_MIN_EV.
     Stakes are fractional-Kelly sized from the fair probability.
  2. Arbitrage: when the best prices across books imply < 100% total
     probability, bet every outcome for a guaranteed margin.

Bets are pre-match only and settle automatically from the scores endpoint.

This sleeve is paper-only and structurally must stay that way: sportsbooks
have no execution API, so real money here means a human placing the bets
the sleeve surfaces (the TS dashboard in this repo is the assist tool).
The paper record tells you honestly whether the edges survive.
"""

import time
from datetime import datetime, timezone

from ... import config, risk
from ..base import Sleeve
from . import ev, oddsapi


def _parse_ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


class SportsbookSleeve(Sleeve):
    name = "sportsbook"

    def __init__(self, ledger):
        super().__init__(ledger)
        if not config.THE_ODDS_API_KEY:
            self.disable("THE_ODDS_API_KEY not set")

    # -------------------------------------------------------------- settle
    def _settle(self):
        open_bets = self.ledger.open_positions(self.name)
        if not open_bets:
            return
        sports = {b["meta"]["sport"] for b in open_bets}
        results = {}
        for sport in sports:
            for game in oddsapi.scores(sport):
                if not game.get("completed") or not game.get("scores"):
                    continue
                scores = {s["name"]: float(s["score"]) for s in game["scores"]}
                if len(scores) < 2:
                    continue
                ordered = sorted(scores.items(), key=lambda kv: -kv[1])
                winner = "Draw" if ordered[0][1] == ordered[1][1] else ordered[0][0]
                results[game["id"]] = winner

        for bet in open_bets:
            winner = results.get(bet["meta"]["event_id"])
            if winner is None:
                continue
            won = bet["meta"]["outcome"] == winner
            self.ledger.settle_bet(bet, won, f"winner: {winner}")
            self.log.info("SETTLED %s -> %s (%+.2f)", bet["description"][:60],
                          "WON" if won else "lost", bet["pnl"])

    # ---------------------------------------------------------------- scan
    def _bet_key(self, event_id: str, outcome: str, book: str) -> str:
        return f"{event_id}|{outcome}|{book}"

    def _scan(self):
        state = self.ledger.sleeve_state(self.name)
        placed = state.setdefault("placed", {})
        now = time.time()
        # forget keys older than a week so state doesn't grow forever
        for k in [k for k, ts in placed.items() if now - ts > 7 * 86400]:
            del placed[k]

        for sport in config.SB_SPORTS:
            for event in oddsapi.odds(sport):
                if _parse_ts(event.get("commence_time", "")) <= now:
                    continue  # pre-match only
                books = ev.extract_h2h(event)
                if len(books) < 2:
                    continue
                label = f"{event.get('away_team')} @ {event.get('home_team')}"
                equity = self.ledger.sleeve_equity(self.name)

                self._try_arb(event, books, label, equity, placed, now)
                self._try_ev(event, sport, books, label, equity, placed, now)

    def _try_ev(self, event, sport, books, label, equity, placed, now):
        fair = ev.fair_probs(books, config.SB_SHARP_BOOK)
        if fair is None:
            return  # sharp book not quoting this event
        bets = ev.find_ev_bets(books, fair, config.SB_MIN_EV,
                               config.SB_MAX_DECIMAL_ODDS, config.SB_SHARP_BOOK)
        learner = getattr(self.ledger, "learner", None)
        count = 0
        for b in bets:
            if count >= config.SB_MAX_BETS_PER_EVENT:
                break
            key = self._bet_key(event["id"], b["outcome"], b["book"])
            if key in placed:
                continue
            # learner: a book whose "+EV" bets keep losing gets cut/dropped
            mult = learner.multiplier(self.name, b["book"]) if learner else 1.0
            if mult <= 0:
                continue
            stake = risk.kelly_stake(equity, b["fair_prob"], b["price"]) * mult
            if stake < 1:
                continue
            pos = self.ledger.open_bet(
                self.name, event["id"],
                f"{label}: {b['outcome']} @ {b['price']:.2f} ({b['book']})",
                stake, b["price"],
                meta={"event_id": event["id"], "sport": sport,
                      "outcome": b["outcome"], "book": b["book"],
                      "fair_prob": round(b["fair_prob"], 4),
                      "ev": round(b["ev"], 4),
                      "note": f"+EV {b['ev']:.1%} vs {config.SB_SHARP_BOOK}"},
            )
            if pos:
                placed[key] = now
                count += 1
                self.log.info("+EV BET $%.2f on %s @ %.2f at %s (edge %.1f%%)",
                              stake, b["outcome"], b["price"], b["book"],
                              b["ev"] * 100)

    def _try_arb(self, event, books, label, equity, placed, now):
        arb = ev.find_arb(books)
        if arb is None:
            return
        if any(self._bet_key(event["id"], leg["outcome"], leg["book"]) in placed
               for leg in arb["legs"]):
            return
        total = round(equity * config.SB_ARB_TOTAL_STAKE_PCT, 2)
        stakes = ev.arb_stakes(arb["legs"], total, arb["total_implied"])
        sport = event.get("sport_key", "")
        for leg, stake in zip(arb["legs"], stakes):
            if stake < 1:
                continue
            pos = self.ledger.open_bet(
                self.name, event["id"],
                f"{label}: ARB {leg['outcome']} @ {leg['price']:.2f} ({leg['book']})",
                stake, leg["price"],
                meta={"event_id": event["id"], "sport": sport,
                      "outcome": leg["outcome"], "book": leg["book"],
                      "arb_edge": round(arb["edge"], 4),
                      "note": f"arb edge {arb['edge']:.2%}"},
            )
            if pos:
                placed[self._bet_key(event["id"], leg["outcome"], leg["book"])] = now
        self.log.info("ARB %s: %.2f%% edge, total $%.2f across %d legs",
                      label, arb["edge"] * 100, total, len(arb["legs"]))

    # ---------------------------------------------------------------- main
    def cycle(self, allow_entries: bool):
        if not self.enabled:
            return
        self._settle()
        if allow_entries:
            self._scan()
        self.ledger.save()
