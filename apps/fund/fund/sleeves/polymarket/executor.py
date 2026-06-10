"""
Execution layer for the Polymarket sleeve.

PaperExecutor — simulates fills at the CLOB midpoint (the default).
ClobExecutor  — places REAL FOK market orders through py-clob-client with
                a funded Polymarket wallet. Selected only when FUND_LIVE=1
                and POLYMARKET_PRIVATE_KEY is set.

Both expose the same interface:
    buy(token_id, usd, mid)   -> (qty, avg_price) or None
    sell(token_id, qty, mid)  -> avg_price or None
    usdc_balance()            -> float or None (None = paper, use ledger cash)

Live notes:
  - Orders are Fill-Or-Kill: either the whole copy fills at market or
    nothing does. No resting orders to babysit.
  - Resolved winning shares must be redeemed (Polymarket UI does this in
    one click); the take-profit at 0.98 exits most positions before that.
"""

import logging

from ... import config

log = logging.getLogger("fund.polymarket")


class PaperExecutor:
    live = False

    def buy(self, token_id: str, usd: float, mid: float):
        if mid <= 0:
            return None
        return round(usd / mid, 2), mid

    def sell(self, token_id: str, qty: float, mid: float):
        return mid

    def usdc_balance(self):
        return None


class ClobExecutor:
    live = True

    def __init__(self):
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OrderType
        self._OrderType = OrderType
        self.client = ClobClient(
            host=config.PM_CLOB_API,
            chain_id=137,  # Polygon
            key=config.POLYMARKET_PRIVATE_KEY,
            signature_type=config.POLYMARKET_SIGNATURE_TYPE,
            funder=config.POLYMARKET_FUNDER or None,
        )
        self.client.set_api_creds(self.client.create_or_derive_api_creds())
        bal = self.usdc_balance()
        log.warning("*** LIVE Polymarket executor armed. USDC balance: %s ***",
                    f"${bal:,.2f}" if bal is not None else "unknown")

    def _market_order(self, token_id: str, amount: float, side_name: str):
        from py_clob_client.clob_types import MarketOrderArgs
        from py_clob_client.order_builder.constants import BUY, SELL
        side = BUY if side_name == "buy" else SELL
        order = self.client.create_market_order(
            MarketOrderArgs(token_id=token_id, amount=round(amount, 2), side=side)
        )
        resp = self.client.post_order(order, self._OrderType.FOK)
        if not resp or not resp.get("success"):
            log.error("LIVE %s failed: %s", side_name, resp)
            return None
        return resp

    @staticmethod
    def _amounts(resp) -> tuple[float, float] | None:
        """(making, taking) from an order response, if reported."""
        try:
            making = float(resp.get("makingAmount") or 0)
            taking = float(resp.get("takingAmount") or 0)
            return (making, taking) if making > 0 and taking > 0 else None
        except (TypeError, ValueError):
            return None

    def buy(self, token_id: str, usd: float, mid: float):
        """FOK market buy of `usd` worth; returns (shares, avg_price)."""
        resp = self._market_order(token_id, usd, "buy")
        if resp is None:
            return None
        amounts = self._amounts(resp)
        if amounts:
            spent, shares = amounts
            return round(shares, 2), round(spent / shares, 4)
        return round(usd / mid, 2), mid  # filled but amounts unreported

    def sell(self, token_id: str, qty: float, mid: float):
        """FOK market sell of `qty` shares; returns avg_price."""
        resp = self._market_order(token_id, qty, "sell")
        if resp is None:
            return None
        amounts = self._amounts(resp)
        if amounts:
            shares, received = amounts
            return round(received / shares, 4)
        return mid

    def usdc_balance(self) -> float | None:
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
            res = self.client.get_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
            return float(res["balance"]) / 1e6  # USDC has 6 decimals
        except Exception as e:
            log.error("balance fetch failed: %s", e)
            return None


def make_executor():
    """Live executor only when explicitly armed; paper otherwise."""
    if not config.PAPER and config.POLYMARKET_PRIVATE_KEY:
        return ClobExecutor()
    if not config.PAPER:
        log.warning("FUND_LIVE=1 but POLYMARKET_PRIVATE_KEY not set — "
                    "polymarket sleeve stays in paper execution")
    return PaperExecutor()
