"""
Fund reports: 7am brief and 9pm summary across all sleeves, posted to a
Slack/Discord-style webhook when REPORT_WEBHOOK_URL is set, always logged.
"""

import json
import logging
import urllib.request
from datetime import date, datetime

from . import config

log = logging.getLogger("fund")
_sent_today = {"morning": None, "evening": None}


def send(text: str):
    if config.REPORT_WEBHOOK_URL:
        try:
            req = urllib.request.Request(
                config.REPORT_WEBHOOK_URL,
                data=json.dumps({"text": text}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            log.error("Webhook failed: %s", e)
    log.info("\n%s", text)


def fund_snapshot(ledger, sleeves) -> str:
    lines = []
    total = 0.0
    for s in sleeves:
        eq = s.equity()
        if eq is None:
            continue
        total += eq
        n_open = len(ledger.open_positions(s.name)) if s.ledger_managed else "-"
        realized = ledger.state["realized_pnl"].get(s.name, 0.0)
        lines.append(
            f"  {s.name:<11} ${eq:>10,.2f}   open: {n_open}   "
            f"realized: {realized:+,.2f}" if s.ledger_managed
            else f"  {s.name:<11} ${eq:>10,.2f}   (at broker)"
        )
    risk = ledger.state["risk"]
    header = [f"Fund equity: ${total:,.2f}"]
    if risk.get("hard_halt"):
        header.append(f"⛔ HALTED: {risk['hard_halt']}")
    elif risk.get("daily_halt"):
        header.append(f"⏸️ paused today: {risk['daily_halt']}")
    return "\n".join(header + lines)


def maybe_send_reports(ledger, sleeves):
    now = datetime.now()
    today = date.today()

    if now.hour >= config.MORNING_REPORT_HOUR and _sent_today["morning"] != today:
        _sent_today["morning"] = today
        body = fund_snapshot(ledger, sleeves)
        positions = ledger.open_positions()
        lines = [f"☀️ Morning brief — {today}", body,
                 f"Open ledger positions: {len(positions)}"]
        for p in positions[:15]:
            mark = p.get("mark", p["entry_price"])
            lines.append(f"  [{p['sleeve']}] {p['description'][:60]} "
                         f"@ {p['entry_price']:.3f} (mark {mark:.3f})")
        send("\n".join(lines))

    if now.hour >= config.EVENING_REPORT_HOUR and _sent_today["evening"] != today:
        _sent_today["evening"] = today
        send(f"🌙 Evening summary — {today}\n" + fund_snapshot(ledger, sleeves))
