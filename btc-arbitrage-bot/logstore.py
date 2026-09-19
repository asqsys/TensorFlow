"""JSONL event log shared by the scanner (writer) and dashboard (reader).

Two record types are written, one per poll cycle each:
  {"type": "sync", "ts": <iso8601>, "markets_synced": int, "markets_total": int}
  {"type": "opportunity", "ts": <iso8601>, "alt": str, "direction": str,
   "profit_fraction": float}
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_event(path: str, record: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def read_events(path: str, max_lines: int = 2000) -> list[dict]:
    """Return up to the last `max_lines` well-formed events, oldest first.

    Missing files and malformed lines (e.g. a write caught mid-flush) are
    treated as empty/skipped rather than raised, since this is read by a
    dashboard that polls continuously and must stay up even on a partial
    or not-yet-created log file.
    """
    if not os.path.exists(path):
        return []

    with open(path) as f:
        lines = f.readlines()[-max_lines:]

    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def summarize(events: list[dict], max_opportunities: int = 100) -> dict:
    sync_events = [e for e in events if e.get("type") == "sync"]
    opp_events = [e for e in events if e.get("type") == "opportunity"]

    profits = [e["profit_fraction"] for e in opp_events]
    recent_opportunities = sorted(
        opp_events, key=lambda e: e.get("ts", ""), reverse=True
    )[:max_opportunities]

    return {
        "last_sync": sync_events[-1] if sync_events else None,
        "opportunities": recent_opportunities,
        "stats": {
            "total_opportunities": len(opp_events),
            "avg_profit_fraction": sum(profits) / len(profits) if profits else 0.0,
            "best_profit_fraction": max(profits) if profits else 0.0,
            "window_start_ts": events[0]["ts"] if events else None,
        },
    }
