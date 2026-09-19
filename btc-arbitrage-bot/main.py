"""Entry point: poll Binance every second and log triangular arbitrage
opportunities. Paper trading only -- no orders are ever placed.
"""
from __future__ import annotations

import argparse
import logging
import time

import requests

from arbitrage import detect_opportunities
from binance_client import fetch_book_tickers
from config import POLL_INTERVAL_SECONDS, watched_symbols

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("btc-arbitrage-bot")


def run(poll_interval: float = POLL_INTERVAL_SECONDS,
        max_iterations: int | None = None) -> None:
    symbols = watched_symbols()
    logger.info("Watching %d markets (paper trading only, no orders will be placed)",
                len(symbols))

    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        try:
            tickers = fetch_book_tickers(symbols)
        except requests.RequestException as exc:
            logger.warning("Failed to fetch prices, will retry next cycle: %s", exc)
            time.sleep(poll_interval)
            continue

        opportunities = detect_opportunities(tickers)
        if opportunities:
            for opp in opportunities:
                logger.info(
                    "ARBITRAGE OPPORTUNITY alt=%s direction=%s profit=%.4f%%",
                    opp.alt, opp.direction, opp.profit_fraction * 100,
                )
        else:
            logger.debug("No opportunities this cycle (%d/%d markets synced)",
                         len(tickers), len(symbols))

        time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL_SECONDS,
                        help="Polling interval in seconds (default: %(default)s)")
    parser.add_argument("--iterations", type=int, default=None,
                        help="Stop after this many polls (default: run forever)")
    args = parser.parse_args()

    try:
        run(poll_interval=args.interval, max_iterations=args.iterations)
    except KeyboardInterrupt:
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
