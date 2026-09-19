"""Local live dashboard for the arbitrage scanner.

Reads the same JSONL event log main.py writes to (see logstore.py) and
serves a single self-refreshing HTML page. Uses only the standard library
(no Flask) since the scanner's only other dependency is `requests`.

This dashboard is read-only monitoring: it never talks to Binance and
never places orders, same as the scanner it observes.
"""
from __future__ import annotations

import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import logstore
from config import (
    DASHBOARD_HOST,
    DASHBOARD_MAX_EVENTS,
    DASHBOARD_PORT,
    DASHBOARD_REFRESH_SECONDS,
    LOG_FILE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("btc-arbitrage-dashboard")

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BTC Arbitrage Scanner</title>
<style>
  :root {
    color-scheme: light;
    --surface-1:      #fcfcfb;
    --page:           #f9f9f7;
    --text-primary:   #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:     #898781;
    --border:         rgba(11,11,11,0.10);
    --gridline:       #e1e0d9;
    --series-1:       #2a78d6;  /* usdt_btc_alt */
    --series-2:       #eb6834;  /* usdt_alt_btc */
    --good:           #0ca30c;
    --critical:       #d03b3b;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --surface-1:      #1a1a19;
      --page:           #0d0d0d;
      --text-primary:   #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted:     #898781;
      --border:         rgba(255,255,255,0.10);
      --gridline:       #2c2c2a;
      --series-1:       #3987e5;
      --series-2:       #d95926;
      --good:           #0ca30c;
      --critical:       #e66767;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 24px 16px 48px;
    background: var(--page);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .wrap { max-width: 880px; margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .subtitle { color: var(--text-secondary); font-size: 13px; margin: 0 0 4px; }
  .disclaimer {
    color: var(--text-muted); font-size: 12px; margin: 0 0 20px;
  }
  .status-row {
    display: flex; align-items: center; gap: 8px; font-size: 13px;
    color: var(--text-secondary); margin-bottom: 20px;
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
  .dot.good { background: var(--good); }
  .dot.critical { background: var(--critical); }
  .tiles {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }
  .tile {
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 8px; padding: 14px 16px;
  }
  .tile .label {
    font-size: 12px; color: var(--text-secondary); margin-bottom: 6px;
  }
  .tile .value {
    font-size: 24px; font-variant-numeric: tabular-nums; font-weight: 600;
  }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th {
    text-align: left; font-weight: 500; color: var(--text-secondary);
    border-bottom: 1px solid var(--gridline); padding: 8px 10px;
  }
  td {
    padding: 8px 10px; border-bottom: 1px solid var(--gridline);
    font-variant-numeric: tabular-nums;
  }
  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    font-size: 12px; color: #fff;
  }
  .badge.usdt_btc_alt { background: var(--series-1); }
  .badge.usdt_alt_btc { background: var(--series-2); }
  .empty { color: var(--text-muted); padding: 20px 10px; text-align: center; }
</style>
</head>
<body>
<div class="wrap">
  <h1>BTC Arbitrage Scanner</h1>
  <p class="subtitle">Triangular arbitrage across Binance BTC/USDT/ALT markets</p>
  <p class="disclaimer">Paper trading only &mdash; this dashboard is read-only monitoring; no orders are ever placed.</p>

  <div class="status-row">
    <span class="dot" id="sync-dot"></span>
    <span id="sync-text">Loading&hellip;</span>
  </div>

  <div class="tiles">
    <div class="tile"><div class="label">Markets synced</div><div class="value" id="tile-markets">&mdash;</div></div>
    <div class="tile"><div class="label">Opportunities (window)</div><div class="value" id="tile-count">&mdash;</div></div>
    <div class="tile"><div class="label">Best profit</div><div class="value" id="tile-best">&mdash;</div></div>
    <div class="tile"><div class="label">Avg profit</div><div class="value" id="tile-avg">&mdash;</div></div>
  </div>

  <table>
    <thead><tr><th>Time (UTC)</th><th>Alt</th><th>Direction</th><th>Profit</th></tr></thead>
    <tbody id="opp-rows"></tbody>
  </table>
  <div class="empty" id="empty-state" style="display:none;">No opportunities detected yet &mdash; market is efficient, as expected most of the time.</div>
</div>

<script>
const DIRECTION_LABEL = {
  usdt_btc_alt: "USDT&rarr;BTC&rarr;ALT",
  usdt_alt_btc: "USDT&rarr;ALT&rarr;BTC",
};

function fmtPct(fraction) {
  return (fraction * 100).toFixed(3) + "%";
}

function timeAgo(iso) {
  if (!iso) return null;
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 0) return "just now";
  if (seconds < 60) return Math.floor(seconds) + "s ago";
  return Math.floor(seconds / 60) + "m ago";
}

async function refresh() {
  let data;
  try {
    const res = await fetch("/api/data", { cache: "no-store" });
    data = await res.json();
  } catch (e) {
    document.getElementById("sync-dot").className = "dot critical";
    document.getElementById("sync-text").textContent = "Dashboard cannot reach its own server.";
    return;
  }

  const dot = document.getElementById("sync-dot");
  const text = document.getElementById("sync-text");
  if (data.last_sync) {
    const ago = timeAgo(data.last_sync.ts);
    const stale = (Date.now() - new Date(data.last_sync.ts).getTime()) / 1000 > 10;
    dot.className = "dot " + (stale ? "critical" : "good");
    text.textContent = (stale ? "Stale — " : "Synced — ") + ago +
      " (" + data.last_sync.markets_synced + "/" + data.last_sync.markets_total + " markets)";
    document.getElementById("tile-markets").textContent =
      data.last_sync.markets_synced + "/" + data.last_sync.markets_total;
  } else {
    dot.className = "dot critical";
    text.textContent = "No sync yet — is main.py running with the same --log-file?";
    document.getElementById("tile-markets").textContent = "—";
  }

  document.getElementById("tile-count").textContent = data.stats.total_opportunities;
  document.getElementById("tile-best").textContent = fmtPct(data.stats.best_profit_fraction);
  document.getElementById("tile-avg").textContent = fmtPct(data.stats.avg_profit_fraction);

  const rows = document.getElementById("opp-rows");
  const empty = document.getElementById("empty-state");
  rows.innerHTML = "";
  if (data.opportunities.length === 0) {
    empty.style.display = "block";
  } else {
    empty.style.display = "none";
    for (const opp of data.opportunities) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + opp.ts.replace("T", " ").slice(0, 19) + "</td>" +
        "<td>" + opp.alt + "</td>" +
        "<td><span class=\\"badge " + opp.direction + "\\">" + (DIRECTION_LABEL[opp.direction] || opp.direction) + "</span></td>" +
        "<td>" + fmtPct(opp.profit_fraction) + "</td>";
      rows.appendChild(tr);
    }
  }
}

refresh();
setInterval(refresh, __REFRESH_MS__);
</script>
</body>
</html>
"""


def make_handler(log_file: str, max_events: int, html: str):
    body_bytes = html.encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self._serve_html()
            elif self.path.startswith("/api/data"):
                self._serve_data()
            else:
                self.send_error(404)

        def _serve_html(self):
            body = body_bytes
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_data(self):
            events = logstore.read_events(log_file, max_lines=max_events)
            summary = logstore.summarize(events)
            body = json.dumps(summary).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            logger.debug("%s - %s", self.address_string(), format % args)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-file", type=str, default=LOG_FILE,
                        help="JSONL log to read (default: %(default)s, same default main.py writes to)")
    parser.add_argument("--host", type=str, default=DASHBOARD_HOST,
                        help="Host to bind (default: %(default)s)")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT,
                        help="Port to bind (default: %(default)s)")
    parser.add_argument("--refresh", type=float, default=DASHBOARD_REFRESH_SECONDS,
                        help="Browser poll interval in seconds (default: %(default)s)")
    parser.add_argument("--max-events", type=int, default=DASHBOARD_MAX_EVENTS,
                        help="Max recent log lines to read per request (default: %(default)s)")
    args = parser.parse_args()

    html = DASHBOARD_HTML.replace("__REFRESH_MS__", str(int(args.refresh * 1000)))
    handler = make_handler(args.log_file, args.max_events, html)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    logger.info("Dashboard serving http://%s:%d (reading %s)",
                args.host, args.port, args.log_file)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
