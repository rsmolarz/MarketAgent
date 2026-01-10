"""
Agent Ensemble Voting (within cluster)

Builds clusters of redundant agents (from correlation).
When signals arrive, produces a cluster-level ensemble decision (ACT/WATCH/IGNORE).

Use ensemble decision to:
- boost confidence
- suppress duplicate alerts
- feed allocator weights
"""
from collections import defaultdict
from typing import Dict, List, Tuple

VOTE_SCORE = {"IGNORE": 0.0, "WATCH": 0.5, "ACT": 1.0}


def build_clusters_from_pairs(redundant_pairs: List[Tuple[str, str]]) -> List[List[str]]:
    """
    Given redundant pairs (a,b) meaning correlated, form clusters.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in redundant_pairs:
        union(a, b)

    groups = defaultdict(list)
    for x in list(parent.keys()):
        groups[find(x)].append(x)

    return [sorted(v) for v in groups.values() if len(v) >= 2]


def ensemble_vote(votes: Dict[str, str], weights: Dict[str, float] = None) -> Dict:
    """
    votes: {agent_name: "ACT"/"WATCH"/"IGNORE"}
    weights: optional {agent_name: weight}
    """
    weights = weights or {}
    total_w = 0.0
    score = 0.0

    for agent, v in votes.items():
        w = float(weights.get(agent, 1.0))
        total_w += w
        score += w * VOTE_SCORE.get(v, 0.0)

    if total_w <= 0:
        return {"consensus": "IGNORE", "agreement": 0.0, "score": 0.0}

    avg = score / total_w

    if avg >= 0.70:
        consensus = "ACT"
    elif avg >= 0.35:
        consensus = "WATCH"
    else:
        consensus = "IGNORE"

    distinct = len(set(votes.values())) if votes else 1
    agreement = 1.0 if distinct == 1 else max(0.0, 1.0 - (distinct - 1) * 0.35)

    return {"consensus": consensus, "agreement": agreement, "score": float(avg)}


def get_cluster_decisions(clusters: List[List[str]], agent_votes: Dict[str, str], 
                          agent_weights: Dict[str, float] = None) -> Dict[str, Dict]:
    """
    For each cluster, compute ensemble decision.
    
    Returns: {cluster_id: {consensus, agreement, score, members}}
    """
    results = {}
    
    for i, cluster in enumerate(clusters):
        cluster_votes = {a: agent_votes.get(a, "WATCH") for a in cluster if a in agent_votes}
        cluster_weights = {a: (agent_weights or {}).get(a, 1.0) for a in cluster}
        
        decision = ensemble_vote(cluster_votes, cluster_weights)
        decision["members"] = cluster
        results[f"cluster_{i}"] = decision
    
    return results
