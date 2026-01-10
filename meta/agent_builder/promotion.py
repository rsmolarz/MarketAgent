from __future__ import annotations
import json
from pathlib import Path

RESULTS_DIR = Path("backtest_results")

def load_result(agent_name: str) -> dict:
    p = RESULTS_DIR / f"{agent_name}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())

def score_agent(agent_name: str) -> dict:
    r = load_result(agent_name)
    if not r:
        return {
            "agent": agent_name,
            "signals": 0,
            "hit_20d": None,
            "mean_20d": None,
            "score": 0.0,
            "recommendation": "NO_DATA"
        }
    
    signals_data = r.get("signals", {})
    fwd20 = signals_data.get("forward", {}).get("20d", {})
    count = signals_data.get("signal_count", 0)

    hit = fwd20.get("hit_rate")
    mean = fwd20.get("mean")

    score = 0.0
    if hit is not None:
        score += (hit - 0.5) * 100.0
    if mean is not None:
        score += mean * 100.0

    return {
        "agent": agent_name,
        "signals": count,
        "hit_20d": hit,
        "mean_20d": mean,
        "score": score,
        "recommendation": (
            "PROMOTE" if (count >= 20 and hit is not None and hit >= 0.55)
            else "HOLD" if (count >= 5)
            else "PRUNE"
        )
    }


def score_all_agents() -> list:
    """Score all agents with backtest results."""
    results = []
    for p in RESULTS_DIR.glob("*.json"):
        agent_name = p.stem
        results.append(score_agent(agent_name))
    return sorted(results, key=lambda x: x["score"], reverse=True)
