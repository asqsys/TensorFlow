# BTC Triangular Arbitrage Scanner

A **paper-trading** scanner that polls Binance's public market-data API
every second and looks for triangular arbitrage opportunities across
BTC/USDT and 25 altcoin markets (51 markets total: `BTCUSDT`, `<ALT>BTC`,
`<ALT>USDT` for each altcoin).

**This bot never places real orders and never requires API keys.** It only
reads public best bid/ask data (`/api/v3/ticker/bookTicker`) and logs any
opportunity it finds. Turning this into a bot that actually trades would
require adding authenticated order-placement, position sizing, slippage
handling, and withdrawal/risk controls -- none of which are implemented
here.

## How it works

For each altcoin `X` there are two possible trade cycles:

- `usdt_btc_alt`: USDT -> BTC -> X -> USDT
- `usdt_alt_btc`: USDT -> X -> BTC -> USDT

Each cycle is evaluated using the best bid/ask that a real market order
would actually cross (never the midpoint), with a 0.1% taker fee applied
on every leg. A cycle is reported as an opportunity when its net result
exceeds `MIN_PROFIT_FRACTION` (default 0.05%) after fees, which filters
out noise from bid/ask rounding.

See `arbitrage.py` for the exact math and `config.py` for the watched
market list and thresholds.

## Usage

```bash
pip install -r requirements.txt
python3 main.py                       # poll every 1s forever
python3 main.py --interval 2          # poll every 2s
python3 main.py --iterations 10       # stop after 10 polls (useful for testing)
```

Opportunities are logged to stdout, e.g.:

```
2026-01-01 00:00:00,000 INFO ARBITRAGE OPPORTUNITY alt=ETH direction=usdt_btc_alt profit=0.1200%
```

## Tests

```bash
python3 -m pytest tests/ -v
```

Tests exercise the arbitrage math directly against mocked bid/ask data
(fair-market no-opportunity case, a deliberately mispriced case, missing
symbols, and profit ordering) so they run without any network access.
