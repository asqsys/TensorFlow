import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage import detect_opportunities
from binance_client import BookTicker
from config import BTC_QUOTE_SYMBOL, alt_btc_symbol, alt_quote_symbol


def make_ticker(symbol, bid, ask):
    return BookTicker(symbol=symbol, bid_price=bid, bid_qty=1.0,
                       ask_price=ask, ask_qty=1.0)


def test_no_opportunity_in_fair_market():
    # Cross rate is exactly consistent (0.05 BTC/ETH * 50000 USDT/BTC ==
    # 2500 USDT/ETH), zero spread. Fees alone should erase any "profit".
    tickers = {
        BTC_QUOTE_SYMBOL: make_ticker(BTC_QUOTE_SYMBOL, 50000, 50000),
        alt_btc_symbol("ETH"): make_ticker(alt_btc_symbol("ETH"), 0.05, 0.05),
        alt_quote_symbol("ETH"): make_ticker(alt_quote_symbol("ETH"), 2500, 2500),
    }
    assert detect_opportunities(tickers, altcoins=["ETH"]) == []


def test_detects_mispriced_alt_usdt_leg():
    # ETHUSDT (2600 bid) is priced well above the fair cross rate implied
    # by ETHBTC * BTCUSDT (~2500), so routing USDT -> BTC -> ETH -> USDT
    # should be profitable even after fees.
    tickers = {
        BTC_QUOTE_SYMBOL: make_ticker(BTC_QUOTE_SYMBOL, 50000, 50010),
        alt_btc_symbol("ETH"): make_ticker(alt_btc_symbol("ETH"), 0.04995, 0.0500),
        alt_quote_symbol("ETH"): make_ticker(alt_quote_symbol("ETH"), 2600, 2601),
    }
    opportunities = detect_opportunities(tickers, altcoins=["ETH"])

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.alt == "ETH"
    assert opp.direction == "usdt_btc_alt"
    assert opp.profit_fraction > 0.03  # ~3.7% expected, well above threshold


def test_missing_symbol_is_skipped_not_raised():
    tickers = {
        BTC_QUOTE_SYMBOL: make_ticker(BTC_QUOTE_SYMBOL, 50000, 50010),
        # ETHBTC intentionally missing
        alt_quote_symbol("ETH"): make_ticker(alt_quote_symbol("ETH"), 2600, 2601),
    }
    assert detect_opportunities(tickers, altcoins=["ETH"]) == []


def test_missing_btc_usdt_returns_empty():
    tickers = {
        alt_btc_symbol("ETH"): make_ticker(alt_btc_symbol("ETH"), 0.05, 0.05),
        alt_quote_symbol("ETH"): make_ticker(alt_quote_symbol("ETH"), 2500, 2500),
    }
    assert detect_opportunities(tickers, altcoins=["ETH"]) == []


def test_opportunities_sorted_by_profit_descending():
    tickers = {
        BTC_QUOTE_SYMBOL: make_ticker(BTC_QUOTE_SYMBOL, 50000, 50010),
        alt_btc_symbol("ETH"): make_ticker(alt_btc_symbol("ETH"), 0.04995, 0.0500),
        alt_quote_symbol("ETH"): make_ticker(alt_quote_symbol("ETH"), 2600, 2601),
        alt_btc_symbol("SOL"): make_ticker(alt_btc_symbol("SOL"), 0.00199, 0.00200),
        alt_quote_symbol("SOL"): make_ticker(alt_quote_symbol("SOL"), 200, 201),
    }
    opportunities = detect_opportunities(tickers, altcoins=["ETH", "SOL"])
    profits = [o.profit_fraction for o in opportunities]
    assert profits == sorted(profits, reverse=True)
