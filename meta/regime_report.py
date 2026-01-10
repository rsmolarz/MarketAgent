"""
Regime-Conditioned Backtesting Report

Explains decisions, not just outcomes:
- Regime
- Confidence
- Historical performance
- Rotation + decay impact
"""

import json
import os
from typing import Dict, List, Any
from datetime import datetime

STATS_PATH = os.path.join(os.path.dirname(__file__), "agent_regime_stats.json")


def load_regime_stats(path=None):
    path = path or STATS_PATH
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def explain_agent_decision(
    agent: str,
    regime: str,
    confidence: float,
    base_weight: float,
    decay_factor: float,
    regime_stats: dict = None
) -> Dict[str, Any]:
    """
    Generate explainability report for a single agent decision.
    
    Returns JSON-serializable dict suitable for dashboard tooltips,
    audit logs, and investor explainability.
    """
    if regime_stats is None:
        regime_stats = load_regime_stats()
    
    stats = regime_stats.get(agent, {}).get(regime)

    if not stats:
        return {
            "agent": agent,
            "regime": regime,
            "confidence": confidence,
            "decision": "OFF",
            "final_weight": 0.0,
            "reason": "No historical edge in this regime"
        }

    mean_return = stats.get("mean_return", 0)
    hit_rate = stats.get("hit_rate", 0)

    final_weight = base_weight * mean_return * hit_rate * decay_factor * confidence

    decision = "ACTIVE" if final_weight > 0.01 else "OFF"
    
    if decision == "ACTIVE":
        reason = f"Positive edge in {regime} (ret={mean_return:.1%}, hit={hit_rate:.0%})"
    else:
        reason = f"Insufficient edge after decay/confidence adjustment"

    return {
        "agent": agent,
        "regime": regime,
        "confidence": round(confidence, 3),
        "mean_return": round(mean_return, 4),
        "hit_rate": round(hit_rate, 3),
        "decay_factor": round(decay_factor, 3),
        "base_weight": round(base_weight, 3),
        "final_weight": round(final_weight, 4),
        "decision": decision,
        "reason": reason
    }


def generate_rotation_report(
    agents: List[str],
    regime: str,
    confidence: float,
    base_weights: Dict[str, float],
    decay_factors: Dict[str, float],
    regime_stats: dict = None
) -> Dict[str, Any]:
    """
    Generate full rotation report for all agents.
    """
    if regime_stats is None:
        regime_stats = load_regime_stats()
    
    decisions = []
    active_count = 0
    total_weight = 0.0
    
    for agent in agents:
        base = base_weights.get(agent, 1.0)
        decay = decay_factors.get(agent, 1.0)
        
        decision = explain_agent_decision(
            agent, regime, confidence, base, decay, regime_stats
        )
        decisions.append(decision)
        
        if decision["decision"] == "ACTIVE":
            active_count += 1
            total_weight += decision["final_weight"]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "regime": regime,
        "confidence": confidence,
        "active_agents": active_count,
        "total_agents": len(agents),
        "total_weight": round(total_weight, 4),
        "decisions": sorted(decisions, key=lambda x: x["final_weight"], reverse=True)
    }


def generate_historical_report(
    agent: str,
    date: str,
    regime: str,
    confidence: float,
    base_weight: float = 1.0,
    decay_factor: float = 1.0,
    regime_stats: dict = None
) -> Dict[str, Any]:
    """
    Generate historical decision explanation for a specific date.
    Used for backtesting audit trails.
    """
    decision = explain_agent_decision(
        agent, regime, confidence, base_weight, decay_factor, regime_stats
    )
    decision["date"] = date
    return decision
