"""
Press-release & news search: `python run.py --news "AAPL"` (or any query).

Three free sources, merged and sorted newest-first:
  - SEC EDGAR full-text search over 8-K filings — 8-Ks are where companies
    legally file material events, with the press release usually attached
    as an exhibit. The highest-signal, zero-spin source.
  - Yahoo Finance news for the ticker/query
  - Google News RSS

Also used by the insiders sleeve: when it copies a disclosed trade, it logs
the latest press releases for that ticker so the trade record carries the
"why now" context.
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from . import config

log = logging.getLogger("fund.news")


def _get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (fund-bot)", **(headers or {})})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def edgar_8k(query: str, days: int) -> list[dict]:
    """8-K filings (material events / press releases) mentioning the query."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    params = urllib.parse.urlencode({
        "q": f'"{query}"', "forms": "8-K", "dateRange": "custom",
        "startdt": str(start), "enddt": str(datetime.now(timezone.utc).date()),
    })
    data = json.loads(_get(f"https://efts.sec.gov/LATEST/search-index?{params}",
                           headers={"User-Agent": config.EDGAR_USER_AGENT}))
    out = []
    for hit in data.get("hits", {}).get("hits", [])[:10]:
        src = hit.get("_source", {})
        adsh, _, filename = hit.get("_id", "::").partition(":")
        ciks = src.get("ciks") or [""]
        company = (src.get("display_names") or ["?"])[0]
        url = ""
        if ciks[0] and adsh and filename:
            url = (f"https://www.sec.gov/Archives/edgar/data/"
                   f"{int(ciks[0])}/{adsh.replace('-', '')}/{filename}")
        out.append({
            "date": src.get("file_date", ""),
            "title": f"8-K filed by {company}",
            "source": "SEC EDGAR",
            "url": url,
        })
    return out


def yahoo_news(query: str) -> list[dict]:
    params = urllib.parse.urlencode({"q": query, "newsCount": 10, "quotesCount": 0})
    data = json.loads(_get(
        f"https://query1.finance.yahoo.com/v1/finance/search?{params}"))
    out = []
    for n in data.get("news", []):
        ts = n.get("providerPublishTime")
        date = (datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
                if ts else "")
        out.append({"date": date, "title": n.get("title", ""),
                    "source": f"Yahoo/{n.get('publisher', '?')}",
                    "url": n.get("link", "")})
    return out


def google_news(query: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {"q": f"{query} press release", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    xml = _get(f"https://news.google.com/rss/search?{params}").decode(errors="replace")
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S)[:10]:
        title = re.search(r"<title>(.*?)</title>", item, re.S)
        link = re.search(r"<link>(.*?)</link>", item, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S)
        date = ""
        if pub:
            try:
                date = parsedate_to_datetime(pub.group(1)).date().isoformat()
            except (ValueError, TypeError):
                pass
        out.append({"date": date,
                    "title": (title.group(1) if title else "").strip(),
                    "source": "Google News",
                    "url": (link.group(1) if link else "").strip()})
    return out


def search_news(query: str, days: int = 14) -> list[dict]:
    items = []
    for fn in (edgar_8k, yahoo_news, google_news):
        try:
            items += fn(query, days) if fn is edgar_8k else fn(query)
        except Exception as e:
            log.info("%s failed: %s", fn.__name__, e)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    items = [i for i in items if not i["date"] or i["date"] >= cutoff]
    return sorted(items, key=lambda i: i["date"], reverse=True)


def format_news(query: str, items: list[dict]) -> str:
    if not items:
        return f"No press releases / news found for {query!r}."
    lines = [f"Press releases & news for {query!r} ({len(items)} items):", ""]
    for i in items:
        lines.append(f"  {i['date'] or '????-??-??'}  [{i['source']}] {i['title']}")
        if i["url"]:
            lines.append(f"      {i['url']}")
    return "\n".join(lines)
