"""
Live-mode preflight: `python run.py --live-check`.

Validates every credential and connection the fund would use with real
money and prints exactly what FUND_LIVE=1 will and will not do. Run this
BEFORE flipping the switch; it never places orders.
"""

from . import config

OK, BAD, WARN = "  ✅", "  ❌", "  ⚠️ "


def _check_alpaca(lines: list[str]):
    lines.append("markets + insiders (Alpaca):")
    if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
        lines.append(f"{BAD} ALPACA_API_KEY / ALPACA_SECRET_KEY not set — "
                     "both sleeves will be disabled")
        return
    try:
        from alpaca.trading.client import TradingClient
        acct = TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY,
                             paper=config.PAPER).get_account()
        endpoint = "PAPER endpoint" if config.PAPER else "LIVE endpoint (real money)"
        lines.append(f"{OK} connected to {endpoint} — equity ${float(acct.equity):,.2f}, "
                     f"status {acct.status}")
        if not config.PAPER and float(acct.equity) <= 0:
            lines.append(f"{WARN} live account has no equity — fund it at alpaca.markets")
    except Exception as e:
        lines.append(f"{BAD} Alpaca connection failed: {e}")


def _check_polymarket(lines: list[str]):
    lines.append("polymarket:")
    if config.PAPER or not config.POLYMARKET_PRIVATE_KEY:
        why = ("FUND_LIVE not set" if config.PAPER
               else "POLYMARKET_PRIVATE_KEY not set")
        lines.append(f"{WARN} paper execution ({why}) — fills simulated at midpoint")
        return
    try:
        from .sleeves.polymarket.executor import ClobExecutor
        bal = ClobExecutor().usdc_balance()
        if bal is None:
            lines.append(f"{BAD} connected but could not read USDC balance")
        elif bal <= 0:
            lines.append(f"{WARN} LIVE executor works but USDC balance is $0 — "
                         "deposit on Polygon first")
        else:
            lines.append(f"{OK} LIVE executor armed — USDC balance ${bal:,.2f}")
    except ImportError:
        lines.append(f"{BAD} py-clob-client not installed: pip install py-clob-client")
    except Exception as e:
        lines.append(f"{BAD} CLOB auth failed: {e} "
                     "(check key, POLYMARKET_FUNDER and POLYMARKET_SIGNATURE_TYPE)")


def _check_sportsbook(lines: list[str]):
    lines.append("sportsbook:")
    if config.THE_ODDS_API_KEY:
        lines.append(f"{OK} key set — paper bets, auto-settled from real scores")
    else:
        lines.append(f"{WARN} THE_ODDS_API_KEY not set — sleeve disabled")
    lines.append(f"{WARN} this sleeve NEVER places real bets (books have no API); "
                 "it measures whether the edges would have paid")


def run_live_check() -> str:
    mode = "LIVE (FUND_LIVE=1)" if not config.PAPER else "PAPER (default)"
    lines = [
        f"Mode: {mode}",
        "",
    ]
    _check_alpaca(lines)
    lines.append("")
    _check_polymarket(lines)
    lines.append("")
    _check_sportsbook(lines)
    lines += [
        "",
        "Risk limits in force (live and paper):",
        f"   per-position cap: {config.MAX_STAKE_PCT:.0%} of equity"
        + (f", hard ${config.MAX_LIVE_STAKE_USD:,.0f} ceiling per trade (live)"
           if not config.PAPER else ""),
        f"   Kelly fraction: {config.KELLY_FRACTION:g}",
        f"   daily loss limit: {config.DAILY_LOSS_LIMIT:.0%} (pauses entries)",
        f"   max drawdown: {config.MAX_DRAWDOWN:.0%} (kill switch, needs --resume)",
        "",
        "To go live: export FUND_LIVE=1 (plus live Alpaca keys and/or a funded",
        "Polymarket wallet), re-run this check, then start the loop.",
    ]
    return "\n".join(lines)
