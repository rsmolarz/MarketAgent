"""
Agent Failure Tracking During Uncertainty

Detects which agents fail first during uncertainty spikes.
This is an early regime transition detector.

An agent is "failing" if:
- Issued signals during uncertainty window
- Forward return < 0 (or below benchmark)
- Confidence > threshold (agent thought it was right)

If multiple unrelated agents fail first → regime shift incoming.
This becomes training data for the LLM council.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import os

FAIL_WINDOW_MIN = 90  # Look back 90 minutes for failure patterns
FAILURE_THRESHOLD = 0.7  # 70% failure rate triggers early warning

_failure_log: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)

LOG_PATH = os.path.join(os.path.dirname(__file__), "uncertainty_failures.json")


def record_agent_outcome(
    agent: str,
    pnl: float,
    ts: Optional[datetime] = None,
    provisional: bool = False
):
    """
    Record an agent outcome during uncertainty.
    
    Args:
        agent: Agent name
        pnl: Profit/loss of the signal
        ts: Timestamp (defaults to now)
        provisional: Whether signal was issued during uncertainty
    """
    if ts is None:
        ts = datetime.utcnow()
    
    if provisional:
        _failure_log[agent].append((ts, pnl))
        
        _failure_log[agent] = [
            (t, p) for (t, p) in _failure_log[agent]
            if t >= ts - timedelta(hours=4)
        ][-100:]


def failing_agents(now: Optional[datetime] = None) -> Dict[str, float]:
    """
    Get agents that are failing during uncertainty.
    
    Returns:
        Dict of agent -> failure_rate (0.0 to 1.0)
    """
    if now is None:
        now = datetime.utcnow()
    
    cutoff = now - timedelta(minutes=FAIL_WINDOW_MIN)
    stats = {}

    for agent, rows in _failure_log.items():
        recent = [p for (t, p) in rows if t >= cutoff]
        if len(recent) >= 5:
            failure_rate = sum(1 for p in recent if p < 0) / len(recent)
            stats[agent] = round(failure_rate, 3)

    return stats


def get_early_warnings(now: Optional[datetime] = None) -> Dict[str, any]:
    """
    Detect early regime transition signals.
    
    If multiple unrelated agents fail first → regime shift incoming.
    """
    if now is None:
        now = datetime.utcnow()
    
    failures = failing_agents(now)
    
    early_warning_agents = {
        agent: rate for agent, rate in failures.items()
        if rate >= FAILURE_THRESHOLD
    }
    
    result = {
        "timestamp": now.isoformat(),
        "early_warning": len(early_warning_agents) >= 2,
        "failing_agents": early_warning_agents,
        "all_failure_rates": failures,
        "threshold": FAILURE_THRESHOLD,
        "window_minutes": FAIL_WINDOW_MIN,
    }
    
    if result["early_warning"]:
        result["event"] = "early_regime_transition"
        result["message"] = f"Multiple agents failing: {list(early_warning_agents.keys())}"
        _log_early_warning(result)
    
    return result


def _log_early_warning(warning: dict):
    """Persist early warning for training data."""
    try:
        history = []
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH) as f:
                history = json.load(f)
        
        history.append(warning)
        history = history[-1000:]
        
        with open(LOG_PATH, "w") as f:
            json.dump(history, f, indent=2, default=str)
    except Exception:
        pass


def get_failure_summary() -> dict:
    """Get summary of failure tracking for API."""
    now = datetime.utcnow()
    return {
        "tracked_agents": list(_failure_log.keys()),
        "total_records": sum(len(v) for v in _failure_log.values()),
        "current_failures": failing_agents(now),
        "early_warnings": get_early_warnings(now),
    }
