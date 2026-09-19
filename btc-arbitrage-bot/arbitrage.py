"""Triangular arbitrage detection across BTC/USDT/ALT markets.

For each altcoin we hold both an ALT/BTC and an ALT/USDT market, plus the
shared BTC/USDT market. That forms a triangle with two possible trade
cycles:

  Cycle "usdt_btc_alt":  USDT -> BTC -> ALT -> USDT
  Cycle "usdt_alt_btc":  USDT -> ALT -> BTC -> USDT

Each cycle is evaluated against current best bid/ask (never the midpoint,
since a real fill crosses the spread) with a taker fee applied on every
leg. This module only detects and reports opportunities; it never places
orders.
"""
from __future__ import annotations

from dataclasses import dataclass

from binance_client import BookTicker
from config import (
    ALTCOINS,
    BTC_QUOTE_SYMBOL,
    MIN_PROFIT_FRACTION,
    TAKER_FEE,
    alt_btc_symbol,
    alt_quote_symbol,
)


@dataclass(frozen=True)
class Opportunity:
    alt: str
    direction: str  # "usdt_btc_alt" or "usdt_alt_btc"
    profit_fraction: float  # e.g. 0.0012 == 0.12% net profit per cycle


def _apply_fee(amount: float, fee: float = TAKER_FEE) -> float:
    return amount * (1.0 - fee)


def _has_tradable_prices(ticker: BookTicker) -> bool:
    """False for a symbol with no live order book (delisted/inactive), where
    Binance returns 0 instead of dropping the symbol from bookTicker."""
    return ticker.bid_price > 0 and ticker.ask_price > 0


def _cycle_usdt_btc_alt(btc_usdt: BookTicker, alt_btc: BookTicker,
                         alt_usdt: BookTicker) -> float:
    """USDT -> BTC -> ALT -> USDT. Returns final USDT amount from 1 USDT."""
    btc_amount = _apply_fee(1.0 / btc_usdt.ask_price)
    alt_amount = _apply_fee(btc_amount / alt_btc.ask_price)
    return _apply_fee(alt_amount * alt_usdt.bid_price)


def _cycle_usdt_alt_btc(btc_usdt: BookTicker, alt_btc: BookTicker,
                         alt_usdt: BookTicker) -> float:
    """USDT -> ALT -> BTC -> USDT. Returns final USDT amount from 1 USDT."""
    alt_amount = _apply_fee(1.0 / alt_usdt.ask_price)
    btc_amount = _apply_fee(alt_amount * alt_btc.bid_price)
    return _apply_fee(btc_amount * btc_usdt.bid_price)


def detect_opportunities(
    tickers: dict[str, BookTicker],
    altcoins: list[str] = ALTCOINS,
    min_profit_fraction: float = MIN_PROFIT_FRACTION,
) -> list[Opportunity]:
    """Scan all watched triangles and return profitable opportunities.

    Markets missing from `tickers` (e.g. a symbol dropped from a partial
    API response) or with no live order book -- Binance returns bid/ask of
    0 for a delisted or inactive symbol instead of omitting it -- are
    skipped rather than raising, since a single stale or degraded poll
    shouldn't crash the scanning loop.
    """
    btc_usdt = tickers.get(BTC_QUOTE_SYMBOL)
    if btc_usdt is None or not _has_tradable_prices(btc_usdt):
        return []

    opportunities: list[Opportunity] = []
    for alt in altcoins:
        alt_btc = tickers.get(alt_btc_symbol(alt))
        alt_usdt = tickers.get(alt_quote_symbol(alt))
        if alt_btc is None or alt_usdt is None:
            continue
        if not _has_tradable_prices(alt_btc) or not _has_tradable_prices(alt_usdt):
            continue

        final_a = _cycle_usdt_btc_alt(btc_usdt, alt_btc, alt_usdt)
        profit_a = final_a - 1.0
        if profit_a >= min_profit_fraction:
            opportunities.append(Opportunity(alt, "usdt_btc_alt", profit_a))

        final_b = _cycle_usdt_alt_btc(btc_usdt, alt_btc, alt_usdt)
        profit_b = final_b - 1.0
        if profit_b >= min_profit_fraction:
            opportunities.append(Opportunity(alt, "usdt_alt_btc", profit_b))

    opportunities.sort(key=lambda o: o.profit_fraction, reverse=True)
    return opportunities
