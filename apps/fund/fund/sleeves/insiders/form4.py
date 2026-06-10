"""
SEC Form 3/4 tracking — parrot specific insiders' PERSONAL trades.

This is the freshest legal "follow Trump's money" signal that exists.
Donald Trump is a >10% beneficial owner of DJT (Trump Media), and family
members sit on boards / hold >10% stakes in several listed companies.
Section 16 of the Exchange Act forces every one of their trades in those
companies onto a public Form 4 within TWO BUSINESS DAYS — not the 45-day
lag of congressional PTRs or the quarterly lag of 13Fs.

What we copy:
  Form 4, transaction code P (open-market purchase)  -> buy signal
  Form 4, transaction code S (open-market sale)      -> sell signal
  Form 3 (new insider position disclosed)            -> buy signal
  transaction code A (stock award/grant)             -> ignored: a grant
                                                        is compensation,
                                                        not conviction

On the first run per filer we only snapshot history (filings older than
INS_FORM4_BOOTSTRAP_DAYS are marked seen without trading) — we never buy
years-old filings, only what they do from now on.

Filers are configured in INS_FORM4_FILERS as {name: CIK}; defaults are
Donald J. Trump (CIK 947033) and Donald Trump Jr. (CIK 2016181), both
verified live filers on EDGAR. Add more with the env var.
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from ... import config
from .edgar import _get  # shared throttle-free EDGAR fetch with proper UA

log = logging.getLogger("fund.insiders")

_OWNERSHIP_FORMS = {"3", "4", "4/A"}
_SEEN_CAP = 300


def _txt(node, path: str) -> str:
    e = node.find(path)
    return (e.text or "").strip() if e is not None and e.text else ""


def _recent_filings(cik: str) -> list[dict]:
    """[{form, date, accession, doc}] newest first, ownership forms only."""
    cik10 = str(int(cik)).zfill(10)
    subs = json.loads(_get(f"https://data.sec.gov/submissions/CIK{cik10}.json"))
    r = subs["filings"]["recent"]
    docs = r.get("primaryDocument", [""] * len(r["form"]))
    out = []
    for i in range(len(r["form"])):
        if r["form"][i] in _OWNERSHIP_FORMS:
            # primaryDocument may be the xsl-rendered path; the raw XML is
            # the same filename without the xsl prefix dir
            doc = docs[i].split("/")[-1] if docs[i] else ""
            out.append({"form": r["form"][i], "date": r["filingDate"][i],
                        "accession": r["accessionNumber"][i], "doc": doc})
    return out


def _fetch_ownership_xml(cik: str, accession: str, doc: str) -> ET.Element | None:
    cik_int = int(cik)
    acc = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}"
    candidates = [doc] if doc.endswith(".xml") else []
    if not candidates:
        idx = json.loads(_get(f"{base}/index.json"))
        candidates = [it["name"] for it in idx["directory"]["item"]
                      if it["name"].lower().endswith(".xml")]
    for name in candidates:
        try:
            return ET.fromstring(_get(f"{base}/{name}"))
        except ET.ParseError:
            continue
    return None


def _valid_ticker(symbol: str) -> str | None:
    s = symbol.strip().upper()
    return s if re.fullmatch(r"[A-Z]{1,5}", s) else None


def parse_filing(cik: str, accession: str, doc: str, form: str) -> list[dict]:
    """
    Extract actionable transactions from one Form 3/4.
    Returns [{ticker, side, shares, price, note}] (often a single item).
    """
    root = _fetch_ownership_xml(cik, accession, doc)
    if root is None:
        return []
    ticker = _valid_ticker(_txt(root, ".//issuerTradingSymbol"))
    issuer = _txt(root, ".//issuerName")
    if ticker is None:
        return []

    if form == "3":
        shares = sum(
            float(_txt(h, ".//sharesOwnedFollowingTransaction/value") or 0)
            for h in root.iter("nonDerivativeHolding"))
        if shares <= 0:
            return []
        return [{"ticker": ticker, "side": "buy", "shares": shares, "price": 0.0,
                 "note": f"Form 3: new insider position in {issuer} "
                         f"({shares:,.0f} sh)"}]

    bought = sold = 0.0
    buy_px = sell_px = 0.0
    for tr in root.iter("nonDerivativeTransaction"):
        code = _txt(tr, ".//transactionCode")
        shares = float(_txt(tr, ".//transactionShares/value") or 0)
        price = float(_txt(tr, ".//transactionPricePerShare/value") or 0)
        if code == "P":
            bought += shares
            buy_px = price or buy_px
        elif code == "S":
            sold += shares
            sell_px = price or sell_px

    out = []
    if bought > sold:
        out.append({"ticker": ticker, "side": "buy", "shares": bought,
                    "price": buy_px,
                    "note": f"Form 4: open-market BUY {bought:,.0f} sh "
                            f"@ {buy_px:.2f} ({issuer})"})
    elif sold > 0:
        out.append({"ticker": ticker, "side": "sell", "shares": sold,
                    "price": sell_px,
                    "note": f"Form 4: SOLD {sold:,.0f} sh ({issuer})"})
    return out


def _days_old(filing_date: str) -> float:
    try:
        dt = datetime.strptime(filing_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except ValueError:
        return 1e9


def new_signals(cik: str, filer_name: str, state: dict) -> list[dict]:
    """
    Unseen Form 3/4 filings for one filer -> [{ticker, side, filer, note}].
    `state` (mutated) tracks seen accession numbers per CIK.
    """
    filer_state = state.setdefault(cik, {})
    seen: list = filer_state.setdefault("seen", [])
    first_run = not filer_state.get("bootstrapped")

    signals = []
    try:
        filings = _recent_filings(cik)
    except Exception as e:
        log.error("form4 %s: submissions fetch failed: %s", filer_name, e)
        return []

    for f in filings:
        if f["accession"] in seen:
            continue
        seen.append(f["accession"])
        # bootstrap: history is snapshotted, not traded
        if first_run and _days_old(f["date"]) > config.INS_FORM4_BOOTSTRAP_DAYS:
            continue
        try:
            txns = parse_filing(cik, f["accession"], f["doc"], f["form"])
        except Exception as e:
            log.error("form4 %s %s: parse failed: %s",
                      filer_name, f["accession"], e)
            continue
        for t in txns:
            signals.append({"ticker": t["ticker"], "side": t["side"],
                            "filer": filer_name,
                            "note": f"{t['note']} filed {f['date']}"})

    filer_state["bootstrapped"] = True
    del seen[:-_SEEN_CAP]
    if first_run:
        log.info("form4 %s: bootstrapped, %d historical filings snapshotted",
                 filer_name, len(seen))
    if signals:
        log.info("form4 %s: %d new signal(s)", filer_name, len(signals))
    return signals
