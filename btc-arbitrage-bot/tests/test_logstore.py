import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logstore


def test_read_events_missing_file_returns_empty(tmp_path):
    assert logstore.read_events(str(tmp_path / "missing.jsonl")) == []


def test_append_and_read_round_trip(tmp_path):
    path = str(tmp_path / "log.jsonl")
    logstore.append_event(path, {"type": "sync", "ts": "t1", "markets_synced": 51, "markets_total": 51})
    logstore.append_event(path, {"type": "opportunity", "ts": "t2", "alt": "ETH",
                                  "direction": "usdt_btc_alt", "profit_fraction": 0.001})

    events = logstore.read_events(path)
    assert len(events) == 2
    assert events[0]["type"] == "sync"
    assert events[1]["alt"] == "ETH"


def test_read_events_skips_malformed_lines(tmp_path):
    path = str(tmp_path / "log.jsonl")
    with open(path, "w") as f:
        f.write('{"type": "sync", "ts": "t1", "markets_synced": 51, "markets_total": 51}\n')
        f.write("not json\n")
        f.write('{"type": "opportunity", "ts": "t2", "alt": "ETH", "direction": "usdt_btc_alt", "profit_fraction": 0.002}\n')

    events = logstore.read_events(path)
    assert len(events) == 2


def test_read_events_respects_max_lines(tmp_path):
    path = str(tmp_path / "log.jsonl")
    for i in range(10):
        logstore.append_event(path, {"type": "sync", "ts": f"t{i}", "markets_synced": 51, "markets_total": 51})

    events = logstore.read_events(path, max_lines=3)
    assert [e["ts"] for e in events] == ["t7", "t8", "t9"]


def test_summarize_empty():
    summary = logstore.summarize([])
    assert summary["last_sync"] is None
    assert summary["opportunities"] == []
    assert summary["stats"]["total_opportunities"] == 0
    assert summary["stats"]["avg_profit_fraction"] == 0.0


def test_summarize_picks_latest_sync_and_sorts_opportunities_desc():
    events = [
        {"type": "sync", "ts": "t1", "markets_synced": 50, "markets_total": 51},
        {"type": "opportunity", "ts": "t2", "alt": "ETH", "direction": "usdt_btc_alt", "profit_fraction": 0.001},
        {"type": "sync", "ts": "t3", "markets_synced": 51, "markets_total": 51},
        {"type": "opportunity", "ts": "t4", "alt": "SOL", "direction": "usdt_alt_btc", "profit_fraction": 0.003},
    ]
    summary = logstore.summarize(events)

    assert summary["last_sync"]["ts"] == "t3"
    assert [o["alt"] for o in summary["opportunities"]] == ["SOL", "ETH"]
    assert summary["stats"]["total_opportunities"] == 2
    assert summary["stats"]["best_profit_fraction"] == 0.003
    assert abs(summary["stats"]["avg_profit_fraction"] - 0.002) < 1e-9


def test_summarize_limits_opportunities_returned():
    events = [
        {"type": "opportunity", "ts": f"t{i}", "alt": "ETH", "direction": "usdt_btc_alt", "profit_fraction": 0.001}
        for i in range(5)
    ]
    summary = logstore.summarize(events, max_opportunities=2)
    assert len(summary["opportunities"]) == 2
