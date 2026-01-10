"""
Ensemble Meta-Agent

Votes across agents weighted by regime skill.
This is the final layer that produces actionable signals.

Behavior:
- Each agent emits a signal (+1 / -1 / 0)
- Votes are weighted by regime-specific performance, decay factor, regime confidence
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime

STATS_PATH = os.path.join(os.path.dirname(__file__), "agent_regime_stats.json")


def load_regime_stats(path=None):
    path = path or STATS_PATH
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def ensemble_vote(
    agent_signals: Dict[str, int],
    regime: str,
    confidence: float,
    regime_stats: Dict = None,
    decay_factors: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Compute ensemble vote across all agents.
    
    Args:
        agent_signals: Dict of agent_name -> signal (+1, -1, or 0)
        regime: Current market regime
        confidence: Regime confidence (0-1)
        regime_stats: Per-agent regime performance stats
        decay_factors: Per-agent decay factors
    
    Returns:
        Ensemble signal (BULLISH/BEARISH/NEUTRAL) with score
    """
    if regime_stats is None:
        regime_stats = load_regime_stats()
    if decay_factors is None:
        decay_factors = {}

    vote = 0.0
    contributions = []

    for agent, signal in agent_signals.items():
        if signal == 0:
            continue
            
        stats = regime_stats.get(agent, {}).get(regime)
        if not stats:
            continue

        mean_return = stats.get("mean_return", 0)
        hit_rate = stats.get("hit_rate", 0)
        decay = decay_factors.get(agent, 1.0)

        weight = mean_return * hit_rate * decay * confidence
        contribution = signal * weight
        vote += contribution
        
        contributions.append({
            "agent": agent,
            "signal": signal,
            "weight": round(weight, 4),
            "contribution": round(contribution, 4)
        })

    if vote > 0.02:
        ensemble_signal = "BULLISH"
    elif vote < -0.02:
        ensemble_signal = "BEARISH"
    else:
        ensemble_signal = "NEUTRAL"

    return {
        "ensemble_signal": ensemble_signal,
        "score": round(vote, 4),
        "regime": regime,
        "confidence": round(confidence, 3),
        "contributions": sorted(contributions, key=lambda x: abs(x["contribution"]), reverse=True)
    }


def aggregate_findings_to_signals(findings: List[Dict]) -> Dict[str, int]:
    """
    Convert recent findings to directional signals per agent.
    
    Rules:
    - Severity critical/high with bullish indicator -> +1
    - Severity critical/high with bearish indicator -> -1
    - Otherwise -> 0
    """
    signals = {}
    
    bullish_keywords = ["momentum", "bullish", "buy", "long", "upside", "support", "breakout"]
    bearish_keywords = ["correction", "bearish", "sell", "short", "downside", "resistance", "breakdown", "stress", "risk"]
    
    for f in findings:
        agent = f.get("agent") or f.get("agent_name")
        if not agent:
            continue
        
        severity = f.get("severity", "low")
        if severity not in ["high", "critical"]:
            if agent not in signals:
                signals[agent] = 0
            continue
        
        title = (f.get("title") or "").lower()
        description = (f.get("description") or "").lower()
        text = title + " " + description
        
        bullish_score = sum(1 for kw in bullish_keywords if kw in text)
        bearish_score = sum(1 for kw in bearish_keywords if kw in text)
        
        if bullish_score > bearish_score:
            signal = 1
        elif bearish_score > bullish_score:
            signal = -1
        else:
            signal = 0
        
        if agent in signals:
            signals[agent] += signal
        else:
            signals[agent] = signal
    
    normalized = {}
    for agent, total in signals.items():
        if total > 0:
            normalized[agent] = 1
        elif total < 0:
            normalized[agent] = -1
        else:
            normalized[agent] = 0
    
    return normalized


def run_ensemble(
    findings: List[Dict],
    regime: str,
    confidence: float,
    decay_factors: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Full ensemble pipeline from findings to signal.
    """
    signals = aggregate_findings_to_signals(findings)
    result = ensemble_vote(signals, regime, confidence, decay_factors=decay_factors)
    result["timestamp"] = datetime.utcnow().isoformat()
    result["agents_contributing"] = len([s for s in signals.values() if s != 0])
    return result
