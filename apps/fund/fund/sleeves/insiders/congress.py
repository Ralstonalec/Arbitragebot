"""
Congressional stock-trade disclosures (STOCK Act periodic transaction
reports). Two providers, tried in order, normalized to one record shape:

  1. Quiver Quantitative (set QUIVER_API_KEY — paid, most reliable)
  2. Capitol Trades public endpoint (no key; may be geo/CDN-blocked)

Reality check baked into the design: PTRs are filed by MEMBERS OF CONGRESS
and may legally lag the trade by up to 45 days. The President (Donald
Trump) files no PTRs at all — only an annual financial disclosure — so
"Trump emphasis" is applied via name-matching (Trump family members who
serve in Congress), the INS_EMPHASIS_NAMES allies list, and Trump-linked
tickers (DJT by default). You are always trading on disclosure, not on
the insider's clock.

Normalized record:
  {id, politician, party, ticker, side ("buy"/"sell"), usd, traded,
   published, source}
"""

import hashlib
import json
import logging
import re
import urllib.parse
import urllib.request

from ... import config

log = logging.getLogger("fund.insiders")

_RANGE_RE = re.compile(r"\$?([\d,]+)\s*-\s*\$?([\d,]+)")


def _get(url: str, headers: dict | None = None):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (fund-bot)", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _trade_id(politician: str, ticker: str, side: str, traded: str, usd: float) -> str:
    raw = f"{politician}|{ticker}|{side}|{traded}|{usd:.0f}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _range_midpoint(text: str) -> float:
    """'$15,001 - $50,000' -> 32500.5; bare numbers pass through."""
    if not text:
        return 0.0
    m = _RANGE_RE.search(str(text))
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", ""))
        return (lo + hi) / 2
    try:
        return float(str(text).replace("$", "").replace(",", ""))
    except ValueError:
        return 0.0


def _normalize(politician, party, ticker, side, usd, traded, published, source):
    side = "buy" if "purchase" in side.lower() or side.lower() == "buy" else "sell"
    ticker = (ticker or "").strip().upper()
    if not ticker or ticker in ("--", "N/A") or len(ticker) > 6:
        return None
    return {
        "id": _trade_id(politician, ticker, side, traded, usd),
        "politician": politician.strip(),
        "party": (party or "").strip(),
        "ticker": ticker,
        "side": side,
        "usd": usd,
        "traded": traded,
        "published": published,
        "source": source,
    }


def _from_quiver() -> list[dict]:
    data = _get(
        "https://api.quiverquant.com/beta/live/congresstrading",
        headers={"Authorization": f"Token {config.QUIVER_API_KEY}"},
    )
    out = []
    for t in data:
        rec = _normalize(
            politician=t.get("Representative") or t.get("Name", ""),
            party=t.get("Party", ""),
            ticker=t.get("Ticker", ""),
            side=t.get("Transaction", ""),
            usd=_range_midpoint(t.get("Range") or t.get("Amount") or
                                t.get("Trade_Size_USD", "")),
            traded=t.get("TransactionDate") or t.get("Date", ""),
            published=t.get("ReportDate") or t.get("Filed") or
                      t.get("TransactionDate", ""),
            source="quiver",
        )
        if rec:
            out.append(rec)
    return out


def _from_capitoltrades() -> list[dict]:
    params = urllib.parse.urlencode({"pageSize": 100, "sortBy": "-pubDate"})
    data = _get(f"https://bff.capitoltrades.com/trades?{params}")
    out = []
    for t in data.get("data", []):
        pol = t.get("politician") or {}
        issuer = t.get("issuer") or {}
        name = (f"{pol.get('firstName', '')} {pol.get('lastName', '')}".strip()
                or t.get("politicianId", "unknown"))
        rec = _normalize(
            politician=name,
            party=pol.get("party", ""),
            ticker=issuer.get("issuerTicker") or t.get("ticker", ""),
            side=t.get("txType", ""),
            usd=float(t.get("value") or 0),
            traded=str(t.get("txDate", "")),
            published=str(t.get("pubDate", ""))[:10],
            source="capitoltrades",
        )
        if rec:
            out.append(rec)
    return out


def recent_trades() -> list[dict]:
    """Most recent congressional trades from the first provider that works."""
    providers = []
    if config.QUIVER_API_KEY:
        providers.append(("quiver", _from_quiver))
    providers.append(("capitoltrades", _from_capitoltrades))

    for name, fn in providers:
        try:
            trades = fn()
            if trades:
                return trades
            log.warning("congress provider %s returned no trades", name)
        except Exception as e:
            log.warning("congress provider %s failed: %s", name, e)
    return []
