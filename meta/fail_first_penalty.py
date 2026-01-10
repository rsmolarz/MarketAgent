"""
Fail-First Penalty Module
Applies weight penalties to agents with high ignore rates under uncertainty.
"""
import logging
from typing import Dict

from meta.council_learning import fail_first_ranking, get_agent_fail_rate

logger = logging.getLogger(__name__)


def apply_fail_first_penalty(
    weights: Dict[str, float], 
    uncertainty_level: float,
    threshold: float = 0.67,
    penalty_scale: float = 0.5
) -> Dict[str, float]:
    """
    Apply fail-first penalty to agent weights under high uncertainty.
    
    When uncertainty is high, agents with high ignore rates get their
    weights reduced proportionally to their failure rate.
    
    Args:
        weights: Current agent weight allocations {agent_name: weight}
        uncertainty_level: Current system uncertainty (0.0-1.0)
        threshold: Uncertainty level at which to apply penalties (default 0.67)
        penalty_scale: How aggressive the penalty is (0.0-1.0, default 0.5)
    
    Returns:
        Adjusted weights dict with fail-first penalties applied
    """
    if uncertainty_level < threshold:
        return weights
    
    adjusted = {}
    penalty_factor = (uncertainty_level - threshold) / (1.0 - threshold)
    
    fail_ranking = fail_first_ranking(min_n=5)
    fail_rates = {r["agent"]: r["fail_rate"] for r in fail_ranking}
    
    for agent, weight in weights.items():
        fail_rate = fail_rates.get(agent, 0.0)
        
        if fail_rate > 0.3:
            penalty = fail_rate * penalty_scale * penalty_factor
            adjusted[agent] = max(0.1, weight * (1.0 - penalty))
            
            if penalty > 0.1:
                logger.info(
                    f"Fail-first penalty: {agent} weight {weight:.2f} -> "
                    f"{adjusted[agent]:.2f} (fail_rate={fail_rate:.2f}, "
                    f"uncertainty={uncertainty_level:.2f})"
                )
        else:
            adjusted[agent] = weight
    
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {k: v / total for k, v in adjusted.items()}
    
    return adjusted


def compute_fail_first_multiplier(agent_name: str, uncertainty_level: float) -> float:
    """
    Compute a decay multiplier for a specific agent based on fail-first logic.
    
    Returns a value between 0.5 and 1.0:
    - 1.0 = no penalty (low uncertainty or low fail rate)
    - 0.5 = maximum penalty (high uncertainty + high fail rate)
    """
    if uncertainty_level < 0.5:
        return 1.0
    
    fail_rate = get_agent_fail_rate(agent_name)
    
    if fail_rate < 0.2:
        return 1.0
    
    uncertainty_factor = min(1.0, (uncertainty_level - 0.5) / 0.5)
    
    penalty = fail_rate * uncertainty_factor * 0.5
    
    return max(0.5, 1.0 - penalty)
