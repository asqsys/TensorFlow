"""Thin client around Binance's public market-data REST API.

Only the public /ticker/bookTicker endpoint is used, so no API key or
secret is required. This endpoint returns the best bid/ask for every
symbol in a single request, which is how the scanner stays in sync with
all watched markets on each poll.
"""
from __future__ import annotations

import requests

from config import BOOK_TICKER_URL, REQUEST_TIMEOUT_SECONDS


class BookTicker:
    __slots__ = ("symbol", "bid_price", "bid_qty", "ask_price", "ask_qty")

    def __init__(self, symbol: str, bid_price: float, bid_qty: float,
                 ask_price: float, ask_qty: float):
        self.symbol = symbol
        self.bid_price = bid_price
        self.bid_qty = bid_qty
        self.ask_price = ask_price
        self.ask_qty = ask_qty


def fetch_book_tickers(symbols: list[str]) -> dict[str, BookTicker]:
    """Fetch best bid/ask for the given symbols in one request.

    Raises requests.RequestException on network/HTTP failure; callers are
    expected to catch this and retry on the next poll cycle.
    """
    wanted = set(symbols)
    response = requests.get(BOOK_TICKER_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    rows = response.json()

    tickers: dict[str, BookTicker] = {}
    for row in rows:
        symbol = row["symbol"]
        if symbol not in wanted:
            continue
        tickers[symbol] = BookTicker(
            symbol=symbol,
            bid_price=float(row["bidPrice"]),
            bid_qty=float(row["bidQty"]),
            ask_price=float(row["askPrice"]),
            ask_qty=float(row["askQty"]),
        )
    return tickers
