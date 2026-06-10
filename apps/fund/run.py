#!/usr/bin/env python3
"""
Fund manager entry point.

  python run.py               run the fund loop (paper mode by default)
  python run.py --once        single scan cycle, then exit
  python run.py --status      print fund equity / positions and exit
  python run.py --resume      clear a risk halt (after you've reviewed why)
  python run.py --live-check  validate keys/balances and show what
                              FUND_LIVE=1 will do — run before going live
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Multi-sleeve trading fund")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    parser.add_argument("--status", action="store_true", help="print status and exit")
    parser.add_argument("--resume", action="store_true", help="clear risk halts")
    parser.add_argument("--live-check", action="store_true",
                        help="preflight live-mode credentials and limits")
    args = parser.parse_args()

    if args.live_check:
        from fund.preflight import run_live_check
        print(run_live_check())
        return

    from fund.orchestrator import Fund, setup_logging
    setup_logging()
    fund = Fund()

    if args.status:
        print(fund.status())
    elif args.resume:
        fund.risk.resume()
    elif args.once:
        fund.cycle()
        print(fund.status())
    else:
        fund.run()


if __name__ == "__main__":
    main()
