#!/usr/bin/env python3
"""
Fund manager entry point.

  python run.py               run the fund loop (paper mode by default)
  python run.py --once        single scan cycle, then exit
  python run.py --status      print fund equity / positions and exit
  python run.py --resume      clear a risk halt (after you've reviewed why)
  python run.py --live-check  validate keys/balances and show what
                              FUND_LIVE=1 will do — run before going live
  python run.py --analyze     print the full trade-analytics report
  python run.py --learning    print what the bot has learned per source
  python run.py --news QUERY  search press releases / news for a ticker
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Multi-sleeve trading fund")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    parser.add_argument("--status", action="store_true", help="print status and exit")
    parser.add_argument("--resume", action="store_true", help="clear risk halts")
    parser.add_argument("--live-check", action="store_true",
                        help="preflight live-mode credentials and limits")
    parser.add_argument("--analyze", action="store_true",
                        help="print the trade-analytics report")
    parser.add_argument("--learning", action="store_true",
                        help="print per-source learning adjustments")
    parser.add_argument("--news", metavar="QUERY",
                        help="search press releases / news and exit")
    args = parser.parse_args()

    if args.live_check:
        from fund.preflight import run_live_check
        print(run_live_check())
        return

    if args.news:
        from fund.news import search_news, format_news
        print(format_news(args.news, search_news(args.news)))
        return

    from fund.orchestrator import Fund, setup_logging
    setup_logging()
    fund = Fund()

    if args.status:
        print(fund.status())
    elif args.resume:
        fund.risk.resume()
    elif args.analyze:
        from fund import analytics
        print(analytics.analyze(fund.ledger, fund.learner))
    elif args.learning:
        fund.learner.refresh()
        print("═══ WHAT THE BOT HAS LEARNED ═══\n"
              + "\n".join(fund.learner.summary()))
    elif args.once:
        fund.cycle()
        print(fund.status())
    else:
        fund.run()


if __name__ == "__main__":
    main()
