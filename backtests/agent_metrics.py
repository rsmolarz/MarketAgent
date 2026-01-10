"""
Per-agent performance metrics aggregation.
Consumes forward-return-labeled findings and produces summary statistics.
"""
from collections import defaultdict
from typing import List, Dict, Any
import numpy as np
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def aggregate_agent_metrics(labeled_findings: List[Dict]) -> Dict[str, Dict]:
    """
    Aggregates performance metrics per agent from labeled findings.
    
    Args:
        labeled_findings: List of findings with 'forward_returns' dict
    
    Returns:
        Dict mapping agent name -> performance stats per horizon
    """
    buckets = defaultdict(list)
    
    for f in labeled_findings:
        agent = f.get("agent")
        if not agent:
            continue
        fr = f.get("forward_returns", {})
        if not fr:
            continue
        buckets[agent].append(fr)
    
    stats = {}
    
    for agent, rows in buckets.items():
        if not rows:
            continue
        
        agg = {}
        # Get all keys from first row
        all_keys = set()
        for r in rows:
            all_keys.update(r.keys())
        
        for k in all_keys:
            vals = [r[k] for r in rows if k in r]
            if not vals:
                continue
            agg[k] = {
                "mean": float(np.mean(vals)),
                "median": float(np.median(vals)),
                "std": float(np.std(vals)) if len(vals) > 1 else 0.0,
                "hit_rate": float(sum(v > 0 for v in vals) / len(vals)),
                "count": len(vals),
                "max": float(np.max(vals)),
                "min": float(np.min(vals)),
            }
        stats[agent] = agg
    
    logger.info(f"Aggregated metrics for {len(stats)} agents")
    return stats


def save_agent_metrics(metrics: Dict[str, Dict], output_dir: str = "backtests/metrics") -> None:
    """
    Saves per-agent metrics to individual JSON files.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    for agent, stats in metrics.items():
        agent_file = out_path / f"{agent}.json"
        with open(agent_file, "w") as f:
            json.dump(stats, f, indent=2)
        logger.info(f"Saved metrics for {agent} to {agent_file}")


def load_agent_metrics(metrics_dir: str = "backtests/metrics") -> Dict[str, Dict]:
    """
    Loads all agent metrics from the metrics directory.
    """
    metrics_path = Path(metrics_dir)
    if not metrics_path.exists():
        return {}
    
    metrics = {}
    for json_file in metrics_path.glob("*.json"):
        agent_name = json_file.stem
        with open(json_file, "r") as f:
            metrics[agent_name] = json.load(f)
    
    return metrics


def compute_composite_score(agent_stats: Dict, horizon: str = "ret_20d") -> float:
    """
    Computes a composite score for agent ranking.
    Score = mean_return * hit_rate * sqrt(count)
    
    Handles both formats:
    - New: {"ret_20d": {"mean": ..., "hit_rate": ..., "count": ...}}
    - Existing: {"forward_returns": {"20d": {...}}, "hit_rate": ..., "total_signals": ...}
    """
    # Try new format
    if horizon in agent_stats:
        h = agent_stats[horizon]
        mean_ret = h.get("mean", 0.0)
        hit_rate = h.get("hit_rate", 0.0)
        count = h.get("count", 0)
    else:
        # Try existing format
        horizon_key = horizon.replace("ret_", "")
        fr = agent_stats.get("forward_returns", {})
        if horizon_key not in fr:
            return 0.0
        h = fr[horizon_key]
        mean_ret = h.get("mean", 0.0)
        hit_rate = agent_stats.get("hit_rate", 0.0)
        count = h.get("n", agent_stats.get("total_signals", 0))
    
    # Penalize negative mean returns heavily
    if mean_ret < 0:
        return mean_ret * 10
    
    # Score: mean * hit_rate * sqrt(count) for sample size adjustment
    return mean_ret * hit_rate * np.sqrt(count)
