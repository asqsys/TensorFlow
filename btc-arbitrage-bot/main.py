"""Entry point: poll Binance every second and log triangular arbitrage
opportunities. Paper trading only -- no orders are ever placed.
"""
from __future__ import annotations

import argparse
import logging
import time

import requests

import logstore
from arbitrage import detect_opportunities
from binance_client import fetch_book_tickers
from config import LOG_FILE as DEFAULT_LOG_FILE
from config import POLL_INTERVAL_SECONDS, watched_symbols

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("btc-arbitrage-bot")


def run(poll_interval: float = POLL_INTERVAL_SECONDS,
        max_iterations: int | None = None,
        log_file: str | None = DEFAULT_LOG_FILE) -> None:
    symbols = watched_symbols()
    logger.info("Watching %d markets (paper trading only, no orders will be placed)",
                len(symbols))
    if log_file:
        logger.info("Logging events to %s (read by dashboard.py)", log_file)

    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        try:
            tickers = fetch_book_tickers(symbols)
        except requests.RequestException as exc:
            logger.warning("Failed to fetch prices, will retry next cycle: %s", exc)
            time.sleep(poll_interval)
            continue

        if log_file:
            logstore.append_event(log_file, {
                "type": "sync",
                "ts": logstore.now_iso(),
                "markets_synced": len(tickers),
                "markets_total": len(symbols),
            })

        opportunities = detect_opportunities(tickers)
        if opportunities:
            for opp in opportunities:
                logger.info(
                    "ARBITRAGE OPPORTUNITY alt=%s direction=%s profit=%.4f%%",
                    opp.alt, opp.direction, opp.profit_fraction * 100,
                )
                if log_file:
                    logstore.append_event(log_file, {
                        "type": "opportunity",
                        "ts": logstore.now_iso(),
                        "alt": opp.alt,
                        "direction": opp.direction,
                        "profit_fraction": opp.profit_fraction,
                    })
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
    parser.add_argument("--log-file", type=str, default=DEFAULT_LOG_FILE,
                        help="JSONL file to append events to, read by dashboard.py "
                             "(default: %(default)s)")
    parser.add_argument("--no-log", action="store_true",
                        help="Disable JSONL event logging entirely")
    args = parser.parse_args()

    try:
        run(poll_interval=args.interval, max_iterations=args.iterations,
            log_file=None if args.no_log else args.log_file)
    except KeyboardInterrupt:
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
