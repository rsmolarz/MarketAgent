"""
Event store helper for parsing telemetry/events.jsonl
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Iterable, Optional

EVENTS = Path("telemetry/events.jsonl")


def iter_events(last_n: int = 20000) -> Iterable[dict]:
    """
    Iterate over the last N events from the telemetry log.
    
    Each event is normalized with a _dt field for datetime access.
    """
    if not EVENTS.exists():
        return
    
    try:
        lines = EVENTS.read_text().splitlines()[-last_n:]
    except Exception:
        return
    
    for ln in lines:
        try:
            e = json.loads(ln)
        except Exception:
            continue
        
        ts = e.get("ts") or e.get("timestamp")
        if isinstance(ts, str):
            try:
                e["_dt"] = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                e["_dt"] = None
        else:
            e["_dt"] = None
        yield e


def get_events_by_agent(agent_name: str, last_n: int = 20000) -> list:
    """Get events filtered by agent name."""
    return [e for e in iter_events(last_n) if e.get("agent") == agent_name]


def get_events_by_type(event_type: str, last_n: int = 20000) -> list:
    """Get events filtered by event type."""
    return [e for e in iter_events(last_n) if e.get("type") == event_type]


def get_equity_curve(last_n: int = 20000) -> list:
    """
    Extract equity curve from events.
    
    Returns list of dicts with timestamp and equity value.
    """
    curve = []
    for e in iter_events(last_n):
        if e.get("type") == "equity" or "equity" in e:
            equity = e.get("equity") or e.get("value")
            if equity is not None and e.get("_dt"):
                curve.append({
                    "timestamp": e["_dt"],
                    "equity": float(equity)
                })
    return sorted(curve, key=lambda x: x["timestamp"])
