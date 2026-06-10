"""
Polymarket copy-trading sleeve — "piggyback the consistent winners".

How it works:
  1. Leader discovery (daily): pull the public PnL leaderboard for two
     windows (1 week AND 1 month). Only wallets in the top N of BOTH
     windows with PnL above PM_MIN_PNL qualify — one lucky bet doesn't
     get followed, sustained profit does. Wallets you pin via
     PM_FOLLOW_WALLETS are always included.
  2. Copy entries: poll each leader's public trade feed. When a leader
     BUYS at meaningful size, mirror the position at the current market
     mid — scaled to OUR bankroll (capped at MAX_STAKE_PCT of equity),
     never to theirs. Skips: dust trades, near-resolved prices, ultra-
     short-term markets (15-min crypto up/down), and entries where the
     price already ran more than PM_MAX_SLIPPAGE past the leader's fill.
  3. Copy exits: if the leader sells the same token, we exit too.
  4. Self-defense (leaders can be wrong): hard stop if the mark drops
     PM_STOP_LOSS_FRAC below our entry, take-profit near 1.00, and
     settlement at 1/0 when the market resolves.

Paper-only by design: fills are simulated at the CLOB midpoint and
recorded in the fund ledger. Real execution would use py-clob-client with
a funded wallet — do not bolt that on until months of paper results hold up,
and remember a copy always enters AFTER the leader moved the price.
"""

import time

from ... import config, risk
from ..base import Sleeve
from . import client


class PolymarketSleeve(Sleeve):
    name = "polymarket"

    # ------------------------------------------------------------- leaders
    def _refresh_leaders(self, state: dict):
        now = time.time()
        if now - state.get("leaders_refreshed_at", 0) < config.PM_LEADER_REFRESH_HOURS * 3600:
            return
        state["leaders_refreshed_at"] = now

        per_window = {}
        for window in config.PM_WINDOWS:
            rows = client.leaderboard(window, config.PM_TOP_N)
            per_window[window] = {
                r["proxyWallet"].lower(): float(r.get("pnl", 0))
                for r in rows
                if float(r.get("pnl", 0)) >= config.PM_MIN_PNL
            }
        if not all(per_window.values()):
            self.log.warning("leaderboard fetch incomplete; keeping old leaders")
            if state.get("leaders"):
                return
        # consistency filter: profitable on BOTH windows
        windows = list(per_window.values())
        consistent = set(windows[0]).intersection(*windows[1:]) if windows else set()
        ranked = sorted(consistent, key=lambda w: -per_window[config.PM_WINDOWS[-1]][w])

        leaders = list(dict.fromkeys(config.PM_FOLLOW_WALLETS + ranked))
        leaders = leaders[: config.PM_MAX_FOLLOWED]
        added = set(leaders) - set(state.get("leaders", []))
        state["leaders"] = leaders
        # don't replay a new leader's entire history — only copy fresh trades
        seen = state.setdefault("last_seen_ts", {})
        for w in added:
            seen.setdefault(w, now - 3600)
        self.log.info("Following %d wallets%s", len(leaders),
                      f" (+{len(added)} new)" if added else "")

    # --------------------------------------------------------------- copies
    @staticmethod
    def _is_short_term(trade: dict) -> bool:
        slug = (trade.get("eventSlug") or trade.get("slug") or "").lower()
        return any(p in slug for p in config.PM_SKIP_SLUG_PATTERNS)

    def _held_assets(self) -> dict:
        return {p["meta"]["asset"]: p for p in self.ledger.open_positions(self.name)}

    def _copy_entries(self, state: dict, allow_entries: bool):
        held = self._held_assets()
        seen = state.setdefault("last_seen_ts", {})
        for wallet in state.get("leaders", []):
            last_ts = seen.get(wallet, time.time() - 3600)
            trades = client.wallet_trades(wallet, limit=50)
            if not trades:
                continue
            seen[wallet] = max(last_ts, max(t["timestamp"] for t in trades))

            for t in sorted(trades, key=lambda x: x["timestamp"]):
                if t["timestamp"] <= last_ts:
                    continue
                asset = t["asset"]
                usd = t["size"] * t["price"]

                if t["side"] == "SELL" and asset in held:
                    pos = held.pop(asset)
                    mark = client.midpoint(asset) or pos.get("mark", pos["entry_price"])
                    self.ledger.close_shares(pos, mark, f"leader {wallet[:8]} exited")
                    self.log.info("COPY EXIT %s @ %.3f (leader sold)",
                                  pos["description"][:50], mark)
                    continue

                if (t["side"] != "BUY" or not allow_entries
                        or asset in held
                        or usd < config.PM_MIN_LEADER_TRADE_USD
                        or self._is_short_term(t)
                        or not (config.PM_MIN_PRICE <= t["price"] <= config.PM_MAX_PRICE)):
                    continue

                mid = client.midpoint(asset)
                if mid is None or mid > t["price"] + config.PM_MAX_SLIPPAGE \
                        or not (config.PM_MIN_PRICE <= mid <= config.PM_MAX_PRICE):
                    continue

                equity = self.ledger.sleeve_equity(self.name)
                # treat the leader's fill price as an implied prob estimate
                stake = risk.kelly_stake(equity, win_prob=min(mid + 0.05, 0.95),
                                         decimal_odds=1.0 / mid)
                stake = min(stake, risk.capped_stake(equity, usd))
                if stake < 5:
                    continue
                qty = round(stake / mid, 2)
                desc = f"{t.get('title', asset[:16])} — {t.get('outcome', '?')}"
                pos = self.ledger.open_shares(
                    self.name, t["conditionId"], desc, qty, mid,
                    meta={
                        "asset": asset,
                        "outcome_index": t.get("outcomeIndex", 0),
                        "leader": wallet,
                        "leader_price": t["price"],
                        "note": f"copy {t.get('name') or wallet[:8]}",
                    },
                )
                if pos:
                    held[asset] = pos
                    self.log.info("COPY %s: $%.2f @ %.3f (leader %s @ %.3f)",
                                  desc[:60], stake, mid, wallet[:8], t["price"])

    # ------------------------------------------------------------ positions
    def _manage_positions(self):
        for pos in self.ledger.open_positions(self.name):
            asset = pos["meta"]["asset"]

            settled = client.resolved_price(pos["market_id"],
                                            pos["meta"]["outcome_index"])
            if settled is not None:
                self.ledger.close_shares(pos, settled, "market resolved")
                self.log.info("RESOLVED %s -> %.0f", pos["description"][:50], settled)
                continue

            mid = client.midpoint(asset)
            if mid is None:
                continue
            pos["mark"] = mid

            if mid <= pos["entry_price"] * (1 - config.PM_STOP_LOSS_FRAC):
                self.ledger.close_shares(pos, mid, "stop loss")
                self.log.info("STOP %s @ %.3f (entry %.3f)",
                              pos["description"][:50], mid, pos["entry_price"])
            elif mid >= config.PM_TAKE_PROFIT_PRICE:
                self.ledger.close_shares(pos, mid, "take profit (near-resolved)")
                self.log.info("TAKE PROFIT %s @ %.3f", pos["description"][:50], mid)
        self.ledger.save()

    # ----------------------------------------------------------------- main
    def cycle(self, allow_entries: bool):
        if not self.enabled:
            return
        state = self.ledger.sleeve_state(self.name)
        self._refresh_leaders(state)
        self._manage_positions()
        self._copy_entries(state, allow_entries)
        self.ledger.save()
