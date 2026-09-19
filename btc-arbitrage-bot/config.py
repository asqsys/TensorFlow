"""Configuration for the BTC triangular-arbitrage scanner.

This bot is PAPER TRADING ONLY: it detects and logs triangular arbitrage
opportunities across Binance markets. It never places real orders and
never requires API keys, since only public market-data endpoints are used.
"""

BASE_ASSET = "BTC"
QUOTE_ASSET = "USDT"

# 25 liquid alts, each traded against both BTC and USDT, gives
# 1 (BTC/USDT) + 25 (ALT/BTC) + 25 (ALT/USDT) = 51 markets scanned per cycle.
ALTCOINS = [
    "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "DOT", "MATIC", "LTC",
    "AVAX", "LINK", "ATOM", "XLM", "ETC", "FIL", "APT", "ARB", "OP", "NEAR",
    "ICP", "UNI", "AAVE", "SAND", "SHIB",
]

BTC_QUOTE_SYMBOL = f"{BASE_ASSET}{QUOTE_ASSET}"  # BTCUSDT


def alt_btc_symbol(alt: str) -> str:
    return f"{alt}{BASE_ASSET}"


def alt_quote_symbol(alt: str) -> str:
    return f"{alt}{QUOTE_ASSET}"


def watched_symbols() -> list[str]:
    symbols = [BTC_QUOTE_SYMBOL]
    for alt in ALTCOINS:
        symbols.append(alt_btc_symbol(alt))
        symbols.append(alt_quote_symbol(alt))
    return symbols


# Taker fee assumed on every leg of a triangular trade (Binance default spot
# taker fee, ignoring any BNB discount).
TAKER_FEE = 0.001

# Minimum net profit (as a fraction, e.g. 0.0005 = 0.05%) required after fees
# before an opportunity is logged. Filters out noise from bid/ask rounding.
MIN_PROFIT_FRACTION = 0.0005

POLL_INTERVAL_SECONDS = 1.0

BOOK_TICKER_URL = "https://api.binance.com/api/v3/ticker/bookTicker"
REQUEST_TIMEOUT_SECONDS = 5

# JSONL event log shared with the dashboard (see logstore.py).
LOG_FILE = "scanner_log.jsonl"

DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8765
DASHBOARD_REFRESH_SECONDS = 2.0
DASHBOARD_MAX_EVENTS = 2000
