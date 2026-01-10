"""
Meta-Agent: Ranking, Weighting, and Auto-Disable Logic.
This is the "selection pressure" that promotes or demotes agents based on performance.
"""
from typing import Dict, Any, Optional
from backtests.agent_metrics import compute_composite_score
import logging

logger = logging.getLogger(__name__)

# Thresholds for agent approval
MIN_SIGNALS = 25        # Minimum signal count for evaluation
MIN_HIT_RATE = 0.45     # Minimum hit rate to stay enabled
MIN_MEAN_RET = 0.0      # Minimum mean return (must be non-negative)
MAX_WEIGHT = 5.0        # Cap on weight to prevent concentration


def _extract_horizon_stats(stats: Dict, horizon: str = "ret_20d") -> Dict:
    """
    Extract stats for a given horizon, handling both formats:
    - New format: {"ret_20d": {"mean": ..., "hit_rate": ..., "count": ...}}
    - Existing format: {"forward_returns": {"20d": {"mean": ..., "n": ...}}, "hit_rate": ..., "total_signals": ...}
    """
    # Try new format first
    if horizon in stats:
        return stats[horizon]
    
    # Try existing backtest format
    horizon_key = horizon.replace("ret_", "")  # "ret_20d" -> "20d"
    fr = stats.get("forward_returns", {})
    if horizon_key in fr:
        h = fr[horizon_key]
        return {
            "mean": h.get("mean", 0.0),
            "std": h.get("std", 0.0),
            "count": h.get("n", stats.get("total_signals", 0)),
            "hit_rate": stats.get("hit_rate", 0.0),  # hit_rate is at top level in existing format
        }
    
    return {}


def rank_agents(agent_metrics: Dict[str, Dict], horizon: str = "ret_20d") -> Dict[str, Dict]:
    """
    Produces agent enable/disable and weight decisions based on performance.
    
    Args:
        agent_metrics: Dict from aggregate_agent_metrics or loaded from existing metrics files
        horizon: Which forward return horizon to use for ranking (e.g., "ret_20d", "ret_60d")
    
    Returns:
        Dict mapping agent name -> decision dict with:
            - enabled: bool
            - weight: float (0.0 to MAX_WEIGHT)
            - reason: str
            - rank: int (1 = best)
            - score: float (composite score)
    """
    decisions = {}
    scores = []
    
    for agent, stats in agent_metrics.items():
        h = _extract_horizon_stats(stats, horizon)
        
        # Check for insufficient data
        count = h.get("count", 0)
        if not h or count < MIN_SIGNALS:
            decisions[agent] = {
                "enabled": False,
                "weight": 0.0,
                "reason": f"insufficient data ({count} < {MIN_SIGNALS})",
                "rank": None,
                "score": 0.0,
            }
            continue
        
        hit_rate = h.get("hit_rate", 0.0)
        mean_ret = h.get("mean", 0.0)
        
        # Check for underperformance
        if hit_rate < MIN_HIT_RATE:
            decisions[agent] = {
                "enabled": False,
                "weight": 0.0,
                "reason": f"hit_rate {hit_rate:.2%} < {MIN_HIT_RATE:.0%}",
                "rank": None,
                "score": compute_composite_score(stats, horizon),
            }
            continue
        
        if mean_ret < MIN_MEAN_RET:
            decisions[agent] = {
                "enabled": False,
                "weight": 0.0,
                "reason": f"mean_return {mean_ret:.2%} < {MIN_MEAN_RET:.0%}",
                "rank": None,
                "score": compute_composite_score(stats, horizon),
            }
            continue
        
        # Agent passes - calculate weight proportional to performance
        # Weight formula: mean_return * hit_rate * 10, clamped to [0.1, MAX_WEIGHT]
        raw_weight = mean_ret * hit_rate * 10
        weight = max(0.1, min(raw_weight, MAX_WEIGHT))
        
        score = compute_composite_score(stats, horizon)
        scores.append((agent, score))
        
        decisions[agent] = {
            "enabled": True,
            "weight": round(weight, 3),
            "reason": "approved",
            "rank": None,  # Will be filled in after sorting
            "score": round(score, 6),
        }
    
    # Assign ranks to enabled agents
    scores.sort(key=lambda x: x[1], reverse=True)
    for rank, (agent, _) in enumerate(scores, start=1):
        if agent in decisions:
            decisions[agent]["rank"] = rank
    
    # Log summary
    enabled_count = sum(1 for d in decisions.values() if d["enabled"])
    logger.info(f"Meta-Agent decisions: {enabled_count}/{len(decisions)} agents enabled")
    
    return decisions


def get_capital_allocation(decisions: Dict[str, Dict]) -> Dict[str, float]:
    """
    Converts weight decisions to capital allocation percentages.
    Normalizes weights to sum to 1.0.
    
    Returns:
        Dict mapping agent name -> allocation fraction
    """
    enabled = {k: v["weight"] for k, v in decisions.items() if v["enabled"]}
    
    if not enabled:
        return {}
    
    total_weight = sum(enabled.values())
    return {k: round(w / total_weight, 4) for k, w in enabled.items()}


def format_ranking_report(decisions: Dict[str, Dict]) -> str:
    """
    Formats a human-readable ranking report.
    """
    lines = ["=" * 60, "META-AGENT RANKING REPORT", "=" * 60, ""]
    
    # Enabled agents by rank
    enabled = [(k, v) for k, v in decisions.items() if v["enabled"]]
    enabled.sort(key=lambda x: x[1]["rank"] or 999)
    
    lines.append("ENABLED AGENTS:")
    lines.append("-" * 40)
    for agent, d in enabled:
        lines.append(f"  #{d['rank']}: {agent}")
        lines.append(f"      Weight: {d['weight']:.3f} | Score: {d['score']:.6f}")
    
    if not enabled:
        lines.append("  (none)")
    
    lines.append("")
    
    # Disabled agents
    disabled = [(k, v) for k, v in decisions.items() if not v["enabled"]]
    disabled.sort(key=lambda x: x[0])
    
    lines.append("DISABLED AGENTS:")
    lines.append("-" * 40)
    for agent, d in disabled:
        lines.append(f"  {agent}: {d['reason']}")
    
    if not disabled:
        lines.append("  (none)")
    
    lines.append("")
    
    # Capital allocation
    alloc = get_capital_allocation(decisions)
    lines.append("CAPITAL ALLOCATION:")
    lines.append("-" * 40)
    for agent, pct in sorted(alloc.items(), key=lambda x: -x[1]):
        lines.append(f"  {agent}: {pct:.1%}")
    
    lines.append("=" * 60)
    return "\n".join(lines)
