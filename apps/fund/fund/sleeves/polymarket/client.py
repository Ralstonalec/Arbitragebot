"""
Read-only client for Polymarket's public APIs (no key required):

  data-api  /v1/leaderboard          top wallets by PnL per window
  data-api  /trades?user=0x..        a wallet's recent fills (public, on-chain)
  clob      /midpoint?token_id=..    current mid price of an outcome token
  gamma     /markets?condition_ids=  market metadata + resolution state
"""

import json
import logging
import urllib.parse
import urllib.request

from ... import config

log = logging.getLogger("fund.polymarket")


def _get(url: str, params: dict | None = None, timeout: int = 15):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "fund-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def leaderboard(window: str, limit: int) -> list[dict]:
    """[{proxyWallet, pnl, vol, userName, ...}] ranked by PnL."""
    try:
        return _get(f"{config.PM_DATA_API}/v1/leaderboard",
                    {"window": window, "limit": limit})
    except Exception as e:
        log.error("leaderboard(%s) failed: %s", window, e)
        return []


def wallet_trades(wallet: str, limit: int = 100) -> list[dict]:
    """Most-recent-first fills: side, asset (token id), conditionId, size,
    price, timestamp, title, outcome, outcomeIndex, eventSlug."""
    try:
        return _get(f"{config.PM_DATA_API}/trades",
                    {"user": wallet, "limit": limit})
    except Exception as e:
        log.error("trades(%s) failed: %s", wallet[:10], e)
        return []


def midpoint(token_id: str) -> float | None:
    try:
        data = _get(f"{config.PM_CLOB_API}/midpoint", {"token_id": token_id})
        return float(data["mid"])
    except Exception:
        return None


def market_info(condition_id: str) -> dict | None:
    """Gamma market: includes closed (bool) and outcomePrices after
    resolution (e.g. '["1","0"]')."""
    try:
        markets = _get(f"{config.PM_GAMMA_API}/markets",
                       {"condition_ids": condition_id})
        return markets[0] if markets else None
    except Exception as e:
        log.error("market_info(%s) failed: %s", condition_id[:10], e)
        return None


def resolved_price(condition_id: str, outcome_index: int) -> float | None:
    """1.0 / 0.0 once the market resolved, else None."""
    info = market_info(condition_id)
    if not info or not info.get("closed"):
        return None
    try:
        prices = json.loads(info["outcomePrices"])
        return float(prices[outcome_index])
    except Exception:
        return None
