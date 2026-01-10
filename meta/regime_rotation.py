import json
import os

STATS_PATH = os.path.join(os.path.dirname(__file__), "agent_regime_stats.json")


def load_regime_stats(path=None):
    path = path or STATS_PATH
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def apply_regime_rotation(
    allocator_weights: dict,
    active_regime: str,
    regime_confidence: float,
    stats_path=None
):
    """
    Applies regime-aware rotation to agent weights.
    
    - Agents with no edge in current regime get muted (weight=0)
    - Agents with edge get scaled by performance * hit_rate * confidence
    - During transitions (low confidence), all weights are throttled
    """
    stats = load_regime_stats(stats_path)

    rotated = {}

    for agent, weight in allocator_weights.items():
        agent_stats = stats.get(agent, {})
        regime_stats = agent_stats.get(active_regime)

        if not regime_stats:
            rotated[agent] = 0.0
            continue

        perf = max(regime_stats.get("mean_return", 0), 0)
        hit = regime_stats.get("hit_rate", 0)

        score = perf * hit

        rotated[agent] = weight * score * regime_confidence

    return rotated


def get_rotation_summary(active_regime: str, regime_confidence: float):
    """
    Returns summary of which agents are active in current regime.
    """
    stats = load_regime_stats()
    
    summary = []
    for agent, regimes in stats.items():
        regime_data = regimes.get(active_regime)
        if regime_data:
            score = regime_data.get("mean_return", 0) * regime_data.get("hit_rate", 0)
            summary.append({
                "agent": agent,
                "regime": active_regime,
                "mean_return": regime_data.get("mean_return", 0),
                "hit_rate": regime_data.get("hit_rate", 0),
                "score": score,
                "effective_weight": score * regime_confidence
            })
        else:
            summary.append({
                "agent": agent,
                "regime": active_regime,
                "mean_return": 0,
                "hit_rate": 0,
                "score": 0,
                "effective_weight": 0,
                "muted": True
            })
    
    return sorted(summary, key=lambda x: x["effective_weight"], reverse=True)
