#!/usr/bin/env python3
"""
Fund manager entry point.

  python run.py            run the fund loop (paper mode by default)
  python run.py --once     single scan cycle, then exit
  python run.py --status   print fund equity / positions and exit
  python run.py --resume   clear a risk halt (after you've reviewed why)
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Multi-sleeve trading fund")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    parser.add_argument("--status", action="store_true", help="print status and exit")
    parser.add_argument("--resume", action="store_true", help="clear risk halts")
    args = parser.parse_args()

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
