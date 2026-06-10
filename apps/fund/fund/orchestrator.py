"""
Fund orchestrator: one risk manager, N sleeves, one loop.

Every POLL_SECONDS it:
  1. Computes total fund equity (ledger sleeves + Alpaca account)
  2. Runs the risk check — daily loss limit & drawdown kill switch.
     When tripped, sleeves still manage exits/stops but open nothing new.
  3. Runs each enabled sleeve's cycle, isolated so one sleeve's crash
     can't take down the others
  4. Sends the 7am / 9pm fund reports
"""

import logging
import time

from . import config, notify
from .ledger import Ledger
from .risk import RiskManager

log = logging.getLogger("fund")


def _load_sleeve_class(name: str):
    """Import lazily so a missing optional dep (pandas/alpaca-py) only
    knocks out its own sleeve, not the whole fund."""
    if name == "markets":
        from .sleeves.markets.sleeve import MarketsSleeve
        return MarketsSleeve
    if name == "polymarket":
        from .sleeves.polymarket.sleeve import PolymarketSleeve
        return PolymarketSleeve
    if name == "sportsbook":
        from .sleeves.sportsbook.sleeve import SportsbookSleeve
        return SportsbookSleeve
    if name == "insiders":
        from .sleeves.insiders.sleeve import InsidersSleeve
        return InsidersSleeve
    return None


def setup_logging():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()],
    )


class Fund:
    def __init__(self):
        self.ledger = Ledger()
        self.risk = RiskManager(self.ledger)
        self.sleeves = []
        for name in config.ENABLED_SLEEVES:
            try:
                cls = _load_sleeve_class(name)
            except ImportError as e:
                log.warning("Sleeve %r unavailable (missing dependency: %s)", name, e)
                continue
            if cls is None:
                log.warning("Unknown sleeve %r ignored", name)
                continue
            self.sleeves.append(cls(self.ledger))
        mode = "PAPER" if config.PAPER else "*** LIVE ***"
        log.info("Fund up in %s mode. Sleeves: %s", mode,
                 ", ".join(f"{s.name}{'' if s.enabled else ' (disabled)'}"
                           for s in self.sleeves))

    def total_equity(self) -> float:
        total = self.ledger.ledger_equity()
        for s in self.sleeves:
            if not s.ledger_managed:
                eq = s.equity()
                if eq is not None:
                    total += eq
        return total

    def cycle(self):
        equity = self.total_equity()
        allow_entries, reason = self.risk.check(equity)
        if not allow_entries:
            log.info("Entries paused: %s", reason)
        for sleeve in self.sleeves:
            try:
                sleeve.cycle(allow_entries)
            except Exception as e:
                log.error("%s cycle failed: %s", sleeve.name, e)
        notify.maybe_send_reports(self.ledger, self.sleeves)

    def run(self):
        log.info("Fund equity: $%s — polling every %ds",
                 f"{self.total_equity():,.2f}", config.POLL_SECONDS)
        while True:
            try:
                self.cycle()
            except KeyboardInterrupt:
                log.info("Stopped by user. Ledger saved; open positions remain.")
                break
            except Exception as e:
                log.error("Cycle failed: %s", e)
            time.sleep(config.POLL_SECONDS)

    def status(self) -> str:
        return notify.fund_snapshot(self.ledger, self.sleeves)
