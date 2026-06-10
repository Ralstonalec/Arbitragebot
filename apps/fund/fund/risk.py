"""
Fund-level risk:
  - Fractional-Kelly stake sizing for probabilistic bets, hard-capped at
    MAX_STAKE_PCT of equity per position. Quarter-Kelly by default because
    our edge estimates are noisy; full Kelly on a wrong edge is ruin.
  - Daily loss limit: no new entries for the rest of the day after losing
    DAILY_LOSS_LIMIT of equity intraday.
  - Drawdown kill switch: a hard halt at MAX_DRAWDOWN off peak equity that
    persists until you manually clear it (`python run.py --resume`).
"""

import logging
from datetime import date

from . import config

log = logging.getLogger("fund")


def _live_clamp(stake: float) -> float:
    """In live mode, an absolute dollar ceiling sits on top of all % caps."""
    if not config.PAPER:
        return min(stake, config.MAX_LIVE_STAKE_USD)
    return stake


def kelly_stake(equity: float, win_prob: float, decimal_odds: float) -> float:
    """Stake for a binary bet at decimal odds, fractional Kelly + cap."""
    b = decimal_odds - 1.0
    if b <= 0 or not (0 < win_prob < 1):
        return 0.0
    edge = win_prob * b - (1.0 - win_prob)
    if edge <= 0:
        return 0.0
    frac = (edge / b) * config.KELLY_FRACTION
    return round(_live_clamp(min(frac, config.MAX_STAKE_PCT) * equity), 2)


def capped_stake(equity: float, desired: float) -> float:
    """For copies where we have no calibrated win prob: flat cap sizing."""
    return round(_live_clamp(min(desired, config.MAX_STAKE_PCT * equity)), 2)


class RiskManager:
    """Tracks peak/day-start equity in the ledger and gates new entries."""

    def __init__(self, ledger):
        self.ledger = ledger

    def check(self, equity: float) -> tuple[bool, str]:
        """Update marks; return (allow_new_entries, reason_if_blocked)."""
        r = self.ledger.state["risk"]
        today = date.today().isoformat()

        if r.get("day") != today:
            r["day"] = today
            r["day_start_equity"] = equity
            r.pop("daily_halt", None)
        r["peak_equity"] = max(r.get("peak_equity", equity), equity)

        if r.get("hard_halt"):
            return False, r["hard_halt"]

        dd = 1.0 - equity / r["peak_equity"] if r["peak_equity"] > 0 else 0.0
        if dd >= config.MAX_DRAWDOWN:
            r["hard_halt"] = (
                f"drawdown {dd:.1%} >= {config.MAX_DRAWDOWN:.0%} limit "
                f"(peak ${r['peak_equity']:,.0f}, now ${equity:,.0f})"
            )
            self.ledger.save()
            log.error("KILL SWITCH: %s — no new entries until --resume", r["hard_halt"])
            return False, r["hard_halt"]

        day_loss = 1.0 - equity / r["day_start_equity"] if r["day_start_equity"] > 0 else 0.0
        if r.get("daily_halt") or day_loss >= config.DAILY_LOSS_LIMIT:
            if not r.get("daily_halt"):
                r["daily_halt"] = f"daily loss {day_loss:.1%} hit limit"
                log.warning("Daily loss limit hit (%.1f%%) — pausing entries today", day_loss * 100)
            self.ledger.save()
            return False, r["daily_halt"]

        self.ledger.save()
        return True, ""

    def resume(self):
        self.ledger.state["risk"].pop("hard_halt", None)
        self.ledger.state["risk"].pop("daily_halt", None)
        self.ledger.save()
        log.info("Risk halts cleared manually.")
