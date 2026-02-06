import json
import os

STATS_PATH = os.path.join(os.path.dirname(__file__), "agent_regime_stats.json")


def load_regime_stats(path=None):
    path = path or STATS_PATH
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


SYSTEM_AGENTS = {'CodeGuardianAgent', 'HealthCheckAgent', 'MetaSupervisorAgent'}
MIN_BASELINE_WEIGHT = 0.40


def apply_regime_rotation(
    allocator_weights: dict,
    active_regime: str,
    regime_confidence: float,
    stats_path=None
):
    """
    Applies regime-aware rotation to agent weights.
    
    - Agents with regime stats get scaled by performance * hit_rate * confidence
    - Agents WITHOUT stats get a minimum baseline weight (not 0) to ensure execution
    - System agents always get full weight regardless of regime
    - During transitions (low confidence), non-system agent weights are throttled
    """
    stats = load_regime_stats(stats_path)

    rotated = {}

    for agent, weight in allocator_weights.items():
        if agent in SYSTEM_AGENTS:
            rotated[agent] = weight
            continue
        
        agent_stats = stats.get(agent, {})
        regime_stats = agent_stats.get(active_regime)

        if not regime_stats:
            rotated[agent] = weight * MIN_BASELINE_WEIGHT * max(regime_confidence, 0.5)
            continue

        perf = max(regime_stats.get("mean_return", 0), 0)
        hit = regime_stats.get("hit_rate", 0)

        score = perf * hit

        rotated[agent] = max(weight * score * regime_confidence, weight * MIN_BASELINE_WEIGHT * 0.5)

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
