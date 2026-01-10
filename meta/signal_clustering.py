"""
Signal Clustering Engine

Identifies redundant agents by clustering signal behavior.
"""

import numpy as np
from typing import Dict, List, Tuple, Set
from collections import defaultdict
from sklearn.cluster import AgglomerativeClustering
import logging

logger = logging.getLogger(__name__)


class SignalClusterer:
    def __init__(self, corr_threshold: float = 0.75):
        self.corr_threshold = corr_threshold

    def build_agent_vectors(self, records: List[dict]) -> Dict[str, np.ndarray]:
        """
        Convert backtest records into per-agent vectors
        """
        series = defaultdict(list)

        for r in records:
            val = r.get("forward_return_20d") or r.get("fwd_ret_20d")
            if val is not None:
                agent = r.get("agent") or r.get("agent_name")
                if agent:
                    series[agent].append(val)

        if not series:
            return {}

        min_len = min(len(v) for v in series.values())
        if min_len < 2:
            return {}

        vectors = {
            k: np.array(v[-min_len:]) for k, v in series.items()
        }

        return vectors

    def cluster(self, vectors: Dict[str, np.ndarray]) -> Dict[int, List[str]]:
        """
        Cluster agents by correlation similarity
        """
        if len(vectors) < 2:
            return {0: list(vectors.keys())} if vectors else {}

        agents = list(vectors.keys())
        X = np.vstack([vectors[a] for a in agents])

        corr = np.corrcoef(X)
        corr = np.nan_to_num(corr, nan=0.0)
        distance = 1 - corr

        model = AgglomerativeClustering(
            metric="precomputed",
            linkage="average",
            distance_threshold=1 - self.corr_threshold,
            n_clusters=None
        )

        labels = model.fit_predict(distance)

        clusters = defaultdict(list)
        for agent, label in zip(agents, labels):
            clusters[label].append(agent)

        return dict(clusters)


def select_representatives(
    clusters: Dict[int, List[str]],
    agent_scores: Dict[str, float]
) -> Tuple[Dict[int, str], Set[str]]:
    """
    Keep best-performing agent per cluster.
    
    Returns:
        winners: {cluster_id: best_agent_name}
        losers: set of redundant agent names
    """
    winners = {}
    losers = set()

    for cid, agents in clusters.items():
        ranked = sorted(
            agents,
            key=lambda a: agent_scores.get(a, -1),
            reverse=True
        )
        winners[cid] = ranked[0]
        losers.update(ranked[1:])

    return winners, losers


def get_redundant_agents(
    records: List[dict],
    agent_scores: Dict[str, float],
    corr_threshold: float = 0.75
) -> Set[str]:
    """
    Convenience function to get set of redundant agents.
    
    Usage:
        redundant = get_redundant_agents(backtest_records, agent_scores)
        if agent_name in redundant:
            weight *= 0.25  # fade redundant agents
    """
    clusterer = SignalClusterer(corr_threshold=corr_threshold)
    vectors = clusterer.build_agent_vectors(records)
    
    if not vectors:
        return set()
    
    clusters = clusterer.cluster(vectors)
    _, losers = select_representatives(clusters, agent_scores)
    
    logger.info(f"Clustering found {len(clusters)} clusters, {len(losers)} redundant agents")
    return losers
