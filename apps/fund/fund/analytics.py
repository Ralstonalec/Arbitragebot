"""
Trade analytics: `python run.py --analyze`.

Reads the three records the fund keeps —
  ledger.json   open/closed positions with metadata and realized P&L
  trades.csv    every fill across all sleeves
  equity.csv    per-cycle equity snapshots (written by the orchestrator)
— and produces the report an auditor would want:

  - equity curve: total return, annualized Sharpe, max drawdown, best/worst day
  - per sleeve: win rate, profit factor, expectancy, avg win/loss, hold time
  - attribution: which leader wallets / politicians / funds / books /
    symbols actually made the money (the piggyback hypothesis, tested)
"""

import csv
import os
from collections import defaultdict
from datetime import datetime, timezone

from . import config

EQUITY_FILE = str(config.DATA_DIR / "equity.csv")


def record_equity(total: float, per_sleeve: dict[str, float]):
    """Called by the orchestrator each cycle."""
    new_file = not os.path.exists(EQUITY_FILE)
    with open(EQUITY_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "total"] + sorted(per_sleeve))
        w.writerow([datetime.now(timezone.utc).isoformat(), round(total, 2)]
                   + [round(per_sleeve[k], 2) for k in sorted(per_sleeve)])


# ----------------------------------------------------------------- helpers
def _hours_between(a: str, b: str) -> float | None:
    try:
        t0 = datetime.fromisoformat(a.replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return (t1 - t0).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


def trade_stats(pnls: list[float], holds: list[float] | None = None) -> str:
    if not pnls:
        return "    no closed trades yet"
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    lines = [
        f"    closed: {len(pnls)}   win rate: {len(wins) / len(pnls):.0%}   "
        f"profit factor: {pf:.2f}",
        f"    total P&L: {sum(pnls):+,.2f}   "
        f"avg win: {gross_win / len(wins):+,.2f}" if wins else
        f"    total P&L: {sum(pnls):+,.2f}   avg win: n/a",
    ]
    if losses:
        lines[-1] += f"   avg loss: {sum(losses) / len(losses):+,.2f}"
    lines.append(f"    expectancy: {sum(pnls) / len(pnls):+,.2f}/trade   "
                 f"best: {max(pnls):+,.2f}   worst: {min(pnls):+,.2f}")
    if holds:
        holds = sorted(holds)
        lines.append(f"    median hold: {holds[len(holds) // 2]:.1f}h")
    return "\n".join(lines)


def _attribution(rows: list[tuple[str, float]], label: str) -> list[str]:
    """rows = [(group_key, pnl)] -> ranked table."""
    groups = defaultdict(list)
    for key, pnl in rows:
        groups[key].append(pnl)
    if not groups:
        return []
    out = [f"    by {label}:"]
    ranked = sorted(groups.items(), key=lambda kv: -sum(kv[1]))
    for key, pnls in ranked[:10]:
        wins = sum(1 for p in pnls if p > 0)
        out.append(f"      {key[:42]:<42} {sum(pnls):>+10,.2f}  "
                   f"({wins}/{len(pnls)} wins)")
    return out


# ------------------------------------------------------------ equity curve
def equity_curve_report() -> list[str]:
    if not os.path.exists(EQUITY_FILE):
        return ["  no equity history yet (written every poll cycle)"]
    daily: dict[str, float] = {}
    first = last = None
    with open(EQUITY_FILE) as f:
        for row in csv.DictReader(f):
            try:
                eq = float(row["total"])
            except (KeyError, ValueError):
                continue
            day = row["timestamp"][:10]
            daily[day] = eq  # last snapshot of the day
            last = eq
            if first is None:
                first = eq
    if first is None or len(daily) == 0:
        return ["  no equity history yet"]

    lines = [f"  equity: ${last:,.2f}   "
             f"total return: {(last / first - 1):+.2%} over {len(daily)} day(s)"]

    days = sorted(daily)
    rets = []
    for prev, cur in zip(days, days[1:]):
        if daily[prev] > 0:
            rets.append(daily[cur] / daily[prev] - 1)
    if len(rets) >= 5:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        std = var ** 0.5
        if std > 0:
            lines.append(f"  annualized Sharpe (daily): "
                         f"{mean / std * (252 ** 0.5):.2f}   "
                         f"daily vol: {std:.2%}")
        best, worst = max(rets), min(rets)
        lines.append(f"  best day: {best:+.2%}   worst day: {worst:+.2%}")
    peak, max_dd = 0.0, 0.0
    for d in days:
        peak = max(peak, daily[d])
        if peak > 0:
            max_dd = max(max_dd, 1 - daily[d] / peak)
    lines.append(f"  max drawdown (daily closes): {max_dd:.2%}")
    return lines


# ------------------------------------------------------------------ report
def analyze(ledger, learner=None) -> str:
    from .learning import csv_outcomes

    sections = ["═══ FUND ANALYTICS ═══", "", "Equity curve:"]
    sections += equity_curve_report()

    closed = [p for p in ledger.state["positions"] if p["status"] == "closed"]
    csv_pnls: dict[str, list] = defaultdict(list)
    for sleeve, group, pnl in csv_outcomes():
        csv_pnls[sleeve].append((group, pnl))

    # --- polymarket
    pm = [p for p in closed if p["sleeve"] == "polymarket"]
    sections += ["", "polymarket (copy-trading):"]
    sections.append(trade_stats(
        [p["pnl"] for p in pm],
        [h for p in pm if (h := _hours_between(p["opened"], p.get("closed", ""))) is not None]))
    sections += _attribution(
        [(p["meta"].get("note", "?").replace("copy ", ""), p["pnl"]) for p in pm],
        "leader")

    # --- sportsbook
    sb = [p for p in closed if p["sleeve"] == "sportsbook"]
    sections += ["", "sportsbook (+EV / arb):"]
    sections.append(trade_stats([p["pnl"] for p in sb]))
    sections += _attribution(
        [(p["meta"].get("book", "?"), p["pnl"]) for p in sb], "book")
    sections += _attribution(
        [("arb" if "arb_edge" in p["meta"] else "+EV", p["pnl"]) for p in sb],
        "type")

    # --- markets / insiders (from trades.csv pairing)
    for sleeve, label, group_label in (
            ("markets", "markets (multi-strategy)", "symbol"),
            ("insiders", "insiders (politicians + 13F)", "source")):
        rows = csv_pnls.get(sleeve, [])
        sections += ["", f"{label}:"]
        sections.append(trade_stats([pnl for _, pnl in rows]))
        sections += _attribution(rows, group_label)

    # --- self-learning state
    if learner is not None:
        learner.refresh()
        sections += ["", "Learning (stake multipliers from realized outcomes):"]
        sections += learner.summary()

    # --- open positions
    open_pos = ledger.open_positions()
    sections += ["", f"Open ledger positions: {len(open_pos)}"]
    for p in open_pos:
        mark = p.get("mark", p["entry_price"])
        if p["kind"] == "shares":
            unreal = (mark - p["entry_price"]) * p["qty"]
            sections.append(f"  [{p['sleeve']}] {p['description'][:55]:<55} "
                            f"{unreal:+,.2f} unrealized")
        else:
            sections.append(f"  [{p['sleeve']}] {p['description'][:55]:<55} "
                            f"stake {p['stake']:,.2f} @ {p['odds']:.2f}")
    return "\n".join(sections)
