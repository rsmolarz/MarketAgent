"""
Portfolio-level Drawdown Governor

Computes rolling portfolio drawdown from telemetry rewards.
If drawdown breaches threshold:
- reduces allocator aggressiveness
- slows cadence
- optionally quarantines high-variance agents
"""
from dataclasses import dataclass
from typing import Dict, Any, List
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

EVENTS = Path("telemetry/events.jsonl")


@dataclass
class DrawdownState:
    peak: float = 0.0
    equity: float = 0.0
    drawdown: float = 0.0
    breached: bool = False


def load_rewards(last_n: int = 5000) -> List[float]:
    """Load reward history from telemetry events."""
    if not EVENTS.exists():
        return []
    
    out = []
    try:
        for ln in EVENTS.read_text().splitlines()[-last_n:]:
            try:
                e = json.loads(ln)
            except Exception:
                continue
            r = e.get("reward")
            if r is None:
                continue
            out.append(float(r))
    except Exception as e:
        logger.warning(f"Error loading rewards: {e}")
    
    return out


def compute_drawdown(rewards: List[float]) -> DrawdownState:
    """Compute current drawdown state from reward history."""
    st = DrawdownState()
    
    for r in rewards:
        st.equity += r
        if st.equity > st.peak:
            st.peak = st.equity
        st.drawdown = (st.equity - st.peak)
    
    return st


def governor(decision: Dict[str, Any], dd_limit: float = -3.0) -> Dict[str, Any]:
    """
    Apply drawdown governance to allocation decision.
    
    Args:
        decision: allocator decision payload
        dd_limit: drawdown threshold in reward-units (negative)
    
    Returns:
        Modified decision with multipliers:
        - cadence_multiplier < 1 slows scheduler changes/runs
        - budget_multiplier < 1 reduces runs allocated
    """
    rewards = load_rewards(last_n=5000)
    st = compute_drawdown(rewards)
    breached = st.drawdown <= dd_limit

    if breached:
        logger.warning(f"Drawdown breached: {st.drawdown:.2f} <= {dd_limit}")
        return {
            **decision,
            "drawdown": st.drawdown,
            "drawdown_breached": True,
            "cadence_multiplier": 0.5,
            "budget_multiplier": 0.5,
            "reason": f"portfolio drawdown {st.drawdown:.2f} <= limit {dd_limit}",
        }

    return {
        **decision,
        "drawdown": st.drawdown,
        "drawdown_breached": False,
        "cadence_multiplier": 1.0,
        "budget_multiplier": 1.0,
        "reason": "ok",
    }


def get_drawdown_status() -> Dict[str, Any]:
    """Get current drawdown status for dashboard."""
    rewards = load_rewards(last_n=5000)
    st = compute_drawdown(rewards)
    
    return {
        "equity": st.equity,
        "peak": st.peak,
        "drawdown": st.drawdown,
        "drawdown_pct": (st.drawdown / st.peak * 100) if st.peak > 0 else 0.0,
        "sample_count": len(rewards),
    }
