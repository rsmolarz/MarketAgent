from collections import Counter, defaultdict
from typing import Dict, List, Any
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _vote_to_score(v: str) -> float:
    v = (v or "").upper()
    if v == "ACT":
        return 1.0
    if v == "WATCH":
        return 0.5
    return 0.0


def ensemble_cluster_votes(
    per_agent: Dict[str, Dict[str, Any]],
    clusters: Dict[str, str],
    agent_weights: Dict[str, float] | None = None
) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate agent votes into cluster-level decisions.
    
    Args:
        per_agent: {agent: {"vote":"ACT|WATCH|IGNORE", "confidence":0..1, "analysis": str}}
        clusters: {agent: cluster_id}
        agent_weights: optional weighting (e.g. regime weight * allocator weight)
    
    Returns:
        {cluster_id: {"vote", "confidence", "members", "vote_breakdown"}}
    """
    agent_weights = agent_weights or {}
    bucket = defaultdict(list)

    for agent, payload in per_agent.items():
        cid = clusters.get(agent, "unclustered")
        w = float(agent_weights.get(agent, 1.0))
        vote = (payload.get("vote") or "IGNORE").upper()
        conf = float(payload.get("confidence") or 0.5)
        bucket[cid].append((agent, vote, conf, w))

    out = {}
    for cid, rows in bucket.items():
        total_w = sum(w for _, _, _, w in rows) or 1.0
        score = sum(_vote_to_score(vote) * conf * w for _, vote, conf, w in rows) / total_w

        if score >= 0.72:
            final_vote = "ACT"
        elif score >= 0.45:
            final_vote = "WATCH"
        else:
            final_vote = "IGNORE"

        breakdown = Counter(v for _, v, _, _ in rows)
        out[cid] = {
            "vote": final_vote,
            "confidence": round(score, 4),
            "members": [a for a, _, _, _ in rows],
            "vote_breakdown": dict(breakdown),
        }
    return out


def load_cluster_map() -> Dict[str, str]:
    """Load agent->cluster mappings from meta/clusters.json or return empty dict."""
    path = Path("meta/clusters.json")
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load cluster map: {e}")
        return {}


def save_cluster_map(clusters: Dict[str, str]) -> None:
    """Save agent->cluster mappings to meta/clusters.json."""
    path = Path("meta/clusters.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(clusters, f, indent=2)


def build_clusters_from_correlation(correlation_matrix: Dict[str, Dict[str, float]], threshold: float = 0.7) -> Dict[str, str]:
    """
    Build clusters from agent correlation matrix.
    
    Args:
        correlation_matrix: {agent1: {agent2: correlation, ...}, ...}
        threshold: minimum correlation to cluster agents together
    
    Returns:
        {agent: cluster_id}
    """
    agents = list(correlation_matrix.keys())
    clusters = {}
    cluster_id = 0
    
    for agent in agents:
        if agent in clusters:
            continue
        clusters[agent] = f"cluster_{cluster_id}"
        for other in agents:
            if other in clusters:
                continue
            corr = correlation_matrix.get(agent, {}).get(other, 0.0)
            if abs(corr) >= threshold:
                clusters[other] = f"cluster_{cluster_id}"
        cluster_id += 1
    
    return clusters
