"""Sleeve interface: each profit engine implements cycle() and equity()."""

import logging


class Sleeve:
    name = "base"
    # True if positions/cash live in the fund Ledger; False if held at an
    # external broker (markets sleeve -> Alpaca).
    ledger_managed = True

    def __init__(self, ledger):
        self.ledger = ledger
        self.log = logging.getLogger(f"fund.{self.name}")
        self.enabled = True

    def cycle(self, allow_entries: bool):
        """One scan/manage pass. allow_entries=False -> exits/stops only."""
        raise NotImplementedError

    def equity(self) -> float | None:
        """Current sleeve equity, or None if unknown."""
        if self.ledger_managed:
            return self.ledger.sleeve_equity(self.name)
        return None

    def disable(self, reason: str):
        if self.enabled:
            self.log.warning("Sleeve disabled: %s", reason)
        self.enabled = False
