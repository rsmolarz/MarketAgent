"""
Agent Substitution

If Agent A fails → promote Agent B automatically.

Rule: Within the same cluster + regime, promote the strongest backup.
Effect: No alpha gaps, no hard switches, capital flows within clusters only.
"""

import json
import os
from typing import Dict, List, Any

STATS_PATH = os.path.join(os.path.dirname(__file__), "agent_regime_stats.json")
CLUSTERS_PATH = os.path.join(os.path.dirname(__file__), "agent_clusters.json")

DEFAULT_CLUSTERS = {
    "equity": ["EquityMomentumAgent", "MarketCorrectionAgent", "DailyPredictionAgent"],
    "crypto": ["CryptoPredictionAgent", "CryptoFundingRateAgent", "WhaleWalletWatcherAgent"],
    "macro": ["BondStressAgent", "MacroWatcherAgent", "GeopoliticalRiskAgent"],
    "systemic": ["GreatestTradeAgent", "SentimentDivergenceAgent"],
    "alt_data": ["AltDataSignalAgent", "PatentSignalAgent"]
}


def load_regime_stats(path=None):
    path = path or STATS_PATH
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def load_clusters(path=None):
    path = path or CLUSTERS_PATH
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return DEFAULT_CLUSTERS


def save_clusters(clusters: dict, path=None):
    path = path or CLUSTERS_PATH
    with open(path, "w") as f:
        json.dump(clusters, f, indent=2)


def substitute_agents(
    final_weights: Dict[str, float],
    regime: str,
    regime_stats: Dict = None,
    clusters: Dict[str, List[str]] = None
) -> Dict[str, float]:
    """
    Substitute underperforming agents with stronger backups within clusters.
    
    Args:
        final_weights: Current agent weights after rotation
        regime: Current market regime
        regime_stats: Per-agent regime performance stats
        clusters: Agent groupings (substitution happens within clusters)
    
    Returns:
        Adjusted weights with capital redistributed to best performers
    """
    if regime_stats is None:
        regime_stats = load_regime_stats()
    if clusters is None:
        clusters = load_clusters()
    
    adjusted = final_weights.copy()

    for cluster_name, agents in clusters.items():
        active = {a: final_weights.get(a, 0) for a in agents}
        if not active:
            continue

        scored = []
        for agent in agents:
            stats = regime_stats.get(agent, {}).get(regime)
            if stats:
                score = stats.get("mean_return", 0) * stats.get("hit_rate", 0)
                scored.append((agent, score, stats))

        if not scored:
            continue

        best_agent, best_score, _ = max(scored, key=lambda x: x[1])

        redistributed = 0.0
        for agent, weight in active.items():
            if weight < 0.01 and agent != best_agent:
                redistributed += weight
                adjusted[agent] = 0.0

        if redistributed > 0 and best_agent in adjusted:
            adjusted[best_agent] = adjusted.get(best_agent, 0) + redistributed

    return adjusted


def get_substitution_report(
    final_weights: Dict[str, float],
    regime: str,
    regime_stats: Dict = None,
    clusters: Dict[str, List[str]] = None
) -> Dict[str, Any]:
    """
    Generate report showing substitution decisions.
    """
    if regime_stats is None:
        regime_stats = load_regime_stats()
    if clusters is None:
        clusters = load_clusters()
    
    report = {
        "regime": regime,
        "substitutions": []
    }
    
    for cluster_name, agents in clusters.items():
        scored = []
        for agent in agents:
            stats = regime_stats.get(agent, {}).get(regime)
            weight = final_weights.get(agent, 0)
            if stats:
                score = stats.get("mean_return", 0) * stats.get("hit_rate", 0)
                scored.append({
                    "agent": agent,
                    "weight": weight,
                    "score": score,
                    "mean_return": stats.get("mean_return", 0),
                    "hit_rate": stats.get("hit_rate", 0)
                })
            else:
                scored.append({
                    "agent": agent,
                    "weight": weight,
                    "score": 0,
                    "mean_return": 0,
                    "hit_rate": 0,
                    "no_edge": True
                })
        
        if scored:
            best = max(scored, key=lambda x: x["score"])
            muted = [s for s in scored if s["weight"] < 0.01 and s["agent"] != best["agent"]]
            
            if muted:
                report["substitutions"].append({
                    "cluster": cluster_name,
                    "best_agent": best["agent"],
                    "best_score": best["score"],
                    "muted_agents": [m["agent"] for m in muted],
                    "capital_redirected": sum(m["weight"] for m in muted)
                })
    
    return report


IGNORE_THRESHOLD = 0.55
MIN_VOTES = 12

DEFAULT_BACKUP_MAP = {
    "MarketCorrectionAgent": "BondStressAgent",
    "EquityMomentumAgent": "MacroWatcherAgent",
    "GeopoliticalRiskAgent": "SentimentDivergenceAgent",
    "ArbitrageFinderAgent": "CryptoFundingRateAgent",
}


def apply_council_substitution(regime: str, backup_map: Dict[str, str] = None):
    """
    When an agent consistently fails first in a regime (high ignore_rate),
    auto-promote a better peer and log it.
    
    Rule: ignore_rate > 0.55 AND at least 12 council votes → substitute
    
    Args:
        regime: Current market regime
        backup_map: Agent substitution mapping (defaults to DEFAULT_BACKUP_MAP)
    
    Returns:
        List of (from_agent, to_agent) tuples for substitutions made
    """
    from datetime import datetime
    from models import db, AgentCouncilStat, AgentSubstitution
    import logging
    
    logger = logging.getLogger(__name__)
    
    if backup_map is None:
        backup_map = DEFAULT_BACKUP_MAP
    
    substitutions_made = []
    
    for from_agent, to_agent in backup_map.items():
        stat = (
            AgentCouncilStat.query
            .filter_by(agent_name=from_agent, regime=regime)
            .first()
        )
        
        if not stat or stat.total_votes < MIN_VOTES:
            continue
        
        if stat.ignore_rate > IGNORE_THRESHOLD:
            existing = (
                AgentSubstitution.query
                .filter_by(from_agent=from_agent, regime=regime, to_agent=to_agent)
                .order_by(AgentSubstitution.timestamp.desc())
                .first()
            )
            if existing and (datetime.utcnow() - existing.timestamp).days < 1:
                continue
            
            sub = AgentSubstitution(
                timestamp=datetime.utcnow(),
                regime=regime,
                from_agent=from_agent,
                to_agent=to_agent,
                from_decay=round(1.0 - stat.ignore_rate, 3),
                to_decay=1.0,
                confidence="high",
                reason=f"ignore_rate={stat.ignore_rate:.2f}, votes={stat.total_votes}"
            )
            db.session.add(sub)
            substitutions_made.append((from_agent, to_agent))
            logger.info(f"Council substitution: {from_agent} -> {to_agent} in {regime} (ignore_rate={stat.ignore_rate:.2f})")
    
    return substitutions_made
