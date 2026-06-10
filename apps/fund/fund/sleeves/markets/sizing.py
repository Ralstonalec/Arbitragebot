"""
Markets-sleeve risk:
  - ATR-based position sizing: every trade risks exactly RISK_PER_TRADE of
    equity. Quiet instruments get bigger size, volatile ones smaller.
  - Hard stop at entry - ATR_STOP_MULT * ATR. No exceptions, no widening.
  - Correlation filter: caps simultaneous risk-on positions (SPY/QQQ/BTC)
    so the sleeve never triples the same macro bet.
"""

from ... import config


def position_size(equity: float, price: float, atr_value: float) -> tuple[float, float]:
    """
    Returns (qty, stop_price).
    qty sized so that (entry - stop) * qty == equity * RISK_PER_TRADE.
    """
    stop_distance = config.ATR_STOP_MULT * atr_value
    if stop_distance <= 0 or price <= 0:
        return 0.0, 0.0
    dollars_at_risk = equity * config.RISK_PER_TRADE
    qty = dollars_at_risk / stop_distance
    # never put more than 25% of equity in one position (sanity cap)
    max_qty = (equity * 0.25) / price
    qty = min(qty, max_qty)
    stop_price = price - stop_distance
    return round(qty, 6), round(stop_price, 2)


def correlation_filter_allows(symbol: str, open_positions: dict) -> bool:
    """Blocks a new risk-on entry if too many risk-on assets are held."""
    if len(open_positions) >= config.MAX_TOTAL_POSITIONS:
        return False
    if symbol not in config.RISK_ON_GROUP:
        return True
    risk_on_held = sum(1 for s in open_positions if s in config.RISK_ON_GROUP)
    return risk_on_held < config.MAX_RISK_ON_POSITIONS
