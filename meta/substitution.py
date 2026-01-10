"""
Agent Substitution on Uncertainty Spikes

When an agent's LLM uncertainty exceeds the cutoff,
automatically demote it and promote backup agents.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

UNCERTAINTY_CUTOFF = 0.7

_substitution_map = None


def load_substitution_map():
    """Load substitution map from JSON file."""
    global _substitution_map
    if _substitution_map is not None:
        return _substitution_map
    
    map_path = os.path.join(os.path.dirname(__file__), "substitution_map.json")
    try:
        with open(map_path, "r") as f:
            _substitution_map = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load substitution map: {e}")
        _substitution_map = {}
    
    return _substitution_map


def apply_substitution(agent: str, uncertainty: float, weights: dict) -> dict:
    """
    Apply substitution logic when agent uncertainty exceeds cutoff.
    
    Args:
        agent: Agent name
        uncertainty: Agent's uncertainty score [0,1]
        weights: Current weight allocation dict
        
    Returns:
        Modified weights dict with substitutions applied
    """
    if uncertainty < UNCERTAINTY_CUTOFF:
        return weights
    
    substitutions = load_substitution_map()
    backups = substitutions.get(agent, [])
    
    if not backups:
        return weights
    
    demotion = weights.get(agent, 0.0)
    weights[agent] = demotion * 0.3
    
    share = demotion * 0.7 / len(backups)
    for backup in backups:
        weights[backup] = weights.get(backup, 0.0) + share
    
    logger.info(f"Substitution: {agent} (u={uncertainty:.2f}) demoted, "
                f"backups {backups} promoted (+{share:.3f} each)")
    
    return weights


def get_substitution_status(uncertainty_map: dict, weights: dict) -> list:
    """
    Get current substitution status for all agents.
    
    Returns list of dicts with agent, uncertainty, demoted status, and backups.
    """
    substitutions = load_substitution_map()
    status = []
    
    for agent, u in uncertainty_map.items():
        backups = substitutions.get(agent, [])
        status.append({
            "agent": agent,
            "uncertainty": round(u, 3),
            "demoted": u >= UNCERTAINTY_CUTOFF,
            "backups": backups if u >= UNCERTAINTY_CUTOFF else [],
            "weight": round(weights.get(agent, 0.0), 4)
        })
    
    return status
