"""Minimal client for The Odds API v4 (same key as the TS platform)."""

import json
import logging
import urllib.parse
import urllib.request

from ... import config

log = logging.getLogger("fund.sportsbook")


def _get(path: str, params: dict):
    params = {"apiKey": config.THE_ODDS_API_KEY, **params}
    url = f"{config.THE_ODDS_API_BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "fund-bot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        remaining = resp.headers.get("x-requests-remaining")
        if remaining is not None and float(remaining) < 50:
            log.warning("The Odds API quota low: %s requests remaining", remaining)
        return json.loads(resp.read().decode())


def odds(sport: str) -> list[dict]:
    """Events with h2h prices across books in decimal odds."""
    try:
        return _get(f"/sports/{sport}/odds", {
            "regions": config.SB_REGIONS,
            "markets": "h2h",
            "oddsFormat": "decimal",
        })
    except Exception as e:
        log.error("odds(%s) failed: %s", sport, e)
        return []


def scores(sport: str) -> list[dict]:
    """Recent completed events (for settling paper bets)."""
    try:
        return _get(f"/sports/{sport}/scores", {
            "daysFrom": config.SB_SETTLE_DAYS_FROM,
        })
    except Exception as e:
        log.error("scores(%s) failed: %s", sport, e)
        return []
