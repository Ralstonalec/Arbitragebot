"""
SEC EDGAR 13F tracking — "top stock traders" as signals.

Follows configured superinvestor funds (Berkshire, Pershing Square,
Duquesne, ...). When a fund files a NEW 13F-HR, we diff it against its
previous holdings snapshot:

  new position or stake increased >25%  -> buy signal
  position fully exited                 -> sell signal

13Fs are quarterly with up to a 45-day lag, so these are conviction
signals on stale information — the sleeve sizes them at half weight.
The first time a fund is seen, we only snapshot its book (we never buy
an entire stale portfolio at once).

13F filings identify holdings by CUSIP + issuer name (no ticker), so
issuer names are mapped to tickers via the SEC's company_tickers.json.
Unmappable names (private notes, foreign listings) are skipped.
"""

import json
import logging
import re
import urllib.request

from ... import config

log = logging.getLogger("fund.insiders")

_UA = {"User-Agent": config.EDGAR_USER_AGENT}
_INFO_RE = re.compile(r"<infoTable>(.*?)</infoTable>", re.S | re.I)
_STRIP_TOKENS = {"INC", "CORP", "CO", "COM", "LTD", "PLC", "CL", "A", "B",
                 "DEL", "NEW", "OF", "HOLDINGS", "HLDGS", "GROUP", "GRP",
                 "THE", "COMPANY", "CORPORATION", "INCORPORATED"}
# 13F filers abbreviate issuer names; expand to match SEC registrant titles
_ABBREV = {"FINL": "FINANCIAL", "PETE": "PETROLEUM", "INTL": "INTERNATIONAL",
           "AMER": "AMERICA",
           "SVCS": "SERVICES", "MTRS": "MOTORS", "COMMUNS": "COMMUNICATIONS",
           "TECHNOLGS": "TECHNOLOGIES", "PPTYS": "PROPERTIES", "PWR": "POWER",
           "LABS": "LABORATORIES", "BANCORPORATION": "BANCORP",
           "PRODS": "PRODUCTS", "RES": "RESOURCES", "ENTMT": "ENTERTAINMENT"}

_ticker_map: dict[str, str] | None = None


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _norm_name(name: str) -> str:
    tokens = re.sub(r"[^A-Z0-9 ]", " ", name.upper()).split()
    return " ".join(_ABBREV.get(t, t) for t in tokens if t not in _STRIP_TOKENS)


def _load_ticker_map() -> dict[str, str]:
    global _ticker_map
    if _ticker_map is None:
        data = json.loads(_get("https://www.sec.gov/files/company_tickers.json"))
        _ticker_map = {}
        for row in data.values():
            key = _norm_name(row["title"])
            # keep the first (largest-company) mapping per normalized name
            _ticker_map.setdefault(key, row["ticker"])
    return _ticker_map


def name_to_ticker(issuer_name: str) -> str | None:
    tmap = _load_ticker_map()
    key = _norm_name(issuer_name)
    if key in tmap:
        return tmap[key]
    # spacing differences: "SIRIUSXM" vs "SIRIUS XM", "MACYS" vs "MACY 'S"
    squashed = {k.replace(" ", ""): t for k, t in tmap.items()}
    if key.replace(" ", "") in squashed:
        return squashed[key.replace(" ", "")]
    # fallback: unique prefix match
    hits = {t for k, t in tmap.items() if k.startswith(key) or key.startswith(k)}
    return hits.pop() if len(hits) == 1 else None


def _tag(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S | re.I)
    return m.group(1).strip() if m else ""


def latest_13f(cik: str) -> tuple[str, str] | None:
    """(accession_number, report_date) of the newest 13F-HR, or None."""
    cik10 = str(int(cik)).zfill(10)
    subs = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik10}.json"))
    r = subs["filings"]["recent"]
    for i in range(len(r["form"])):
        if r["form"][i] == "13F-HR":
            return r["accessionNumber"][i], r["reportDate"][i]
    return None


def holdings(cik: str, accession: str) -> dict[str, float]:
    """{issuer_name: total_value_usd} from a 13F-HR information table."""
    cik_int = int(cik)
    acc = accession.replace("-", "")
    idx = json.loads(_get(
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/index.json"))
    names = [it["name"] for it in idx["directory"]["item"]]
    xml_name = next(
        (n for n in names
         if n.lower().endswith(".xml") and "primary_doc" not in n.lower()),
        None)
    if xml_name is None:
        raise RuntimeError(f"no infotable xml in {accession}")
    xml = _get(
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{xml_name}"
    ).decode(errors="replace")

    book: dict[str, float] = {}
    for block in _INFO_RE.findall(xml):
        if _tag(block, "putCall"):
            continue  # skip options
        name = _tag(block, "nameOfIssuer")
        try:
            value = float(_tag(block, "value"))
        except ValueError:
            continue
        if name:
            book[name] = book.get(name, 0.0) + value
    return book


def new_13f_signals(cik: str, fund_name: str, state: dict) -> list[dict]:
    """
    Diff the newest 13F against the stored snapshot in `state` (mutated).
    Returns [{ticker, side, fund, issuer, note}].
    """
    latest = latest_13f(cik)
    if latest is None:
        return []
    accession, report_date = latest
    fund_state = state.setdefault(cik, {})
    if fund_state.get("accession") == accession:
        return []

    book = holdings(cik, accession)
    prev = fund_state.get("holdings")
    fund_state["accession"] = accession
    fund_state["report_date"] = report_date
    fund_state["holdings"] = book

    if prev is None:
        log.info("%s: first 13F snapshot (%s, %d holdings) — no signals yet",
                 fund_name, report_date, len(book))
        return []

    signals = []
    for issuer, value in book.items():
        old = prev.get(issuer)
        if old is None or (old > 0 and value / old > 1.25):
            ticker = name_to_ticker(issuer)
            if ticker is None:
                log.info("%s: cannot map issuer %r to a ticker — skipped",
                         fund_name, issuer)
                continue
            action = "new position" if old is None else f"added {value/old - 1:.0%}"
            signals.append({"ticker": ticker, "side": "buy", "fund": fund_name,
                            "issuer": issuer, "note": f"{action} ({report_date})"})
    for issuer in prev:
        if issuer not in book:
            ticker = name_to_ticker(issuer)
            if ticker:
                signals.append({"ticker": ticker, "side": "sell",
                                "fund": fund_name, "issuer": issuer,
                                "note": f"exited ({report_date})"})
    log.info("%s: new 13F %s -> %d signals", fund_name, report_date, len(signals))
    return signals
