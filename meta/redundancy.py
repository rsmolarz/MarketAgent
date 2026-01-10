"""
Agent Redundancy Pruning via Correlation Clustering

Problem solved:
Multiple agents fire the same signal → false diversification → capital dilution.

Solution:
Cluster agents by signal co-movement, keep the strongest per cluster, down-weight the rest.
"""
import numpy as np
from collections import defaultdict
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CORR_LOOKBACK = 300
CORR_THRESHOLD = 0.85

_cached_redundant = set()
_cache_timestamp = None
_CACHE_TTL_MINUTES = 15


def compute_agent_signal_vectors():
    """
    Builds binary time-series vectors per agent:
    1 = signal fired, 0 = no signal
    """
    from models import Finding
    
    rows = (
        Finding.query
        .order_by(Finding.timestamp.desc())
        .limit(CORR_LOOKBACK)
        .all()
    )

    by_ts = defaultdict(set)
    for r in rows:
        by_ts[r.timestamp].add(r.agent_name)

    agents = sorted({r.agent_name for r in rows})
    matrix = {a: [] for a in agents}

    for _, active_agents in sorted(by_ts.items()):
        for a in agents:
            matrix[a].append(1 if a in active_agents else 0)

    return agents, matrix


def find_redundant_agents():
    """
    Find agents that are redundant based on signal correlation.
    Uses caching to avoid repeated DB queries.
    
    Returns set of agent names that should be down-weighted because
    they correlate too highly with other agents.
    """
    global _cached_redundant, _cache_timestamp
    
    now = datetime.utcnow()
    if _cache_timestamp and (now - _cache_timestamp) < timedelta(minutes=_CACHE_TTL_MINUTES):
        return _cached_redundant
    
    try:
        agents, matrix = compute_agent_signal_vectors()
        redundant = set()

        for i, a1 in enumerate(agents):
            for a2 in agents[i+1:]:
                v1, v2 = matrix[a1], matrix[a2]
                if len(v1) < 20:
                    continue

                corr = np.corrcoef(v1, v2)[0, 1]
                if not np.isnan(corr) and corr >= CORR_THRESHOLD:
                    redundant.add(a2)
                    logger.debug(f"Agent {a2} redundant with {a1} (corr={corr:.2f})")

        _cached_redundant = redundant
        _cache_timestamp = now
        return redundant
    except Exception as e:
        logger.warning(f"Redundancy check failed: {e}")
        return _cached_redundant if _cached_redundant else set()


def refresh_redundancy_cache():
    """
    Force refresh of redundancy cache.
    Call this from scheduler within app context.
    """
    global _cache_timestamp
    _cache_timestamp = None
    return find_redundant_agents()


def find_redundant_pairs(corr_threshold: float = 0.85):
    """
    Find pairs of redundant agents based on signal correlation.
    
    Returns list of (agent1, agent2) tuples where correlation >= threshold.
    Used for building agent clusters.
    """
    try:
        agents, matrix = compute_agent_signal_vectors()
        pairs = []

        for i, a1 in enumerate(agents):
            for a2 in agents[i+1:]:
                v1, v2 = matrix[a1], matrix[a2]
                if len(v1) < 20:
                    continue
                corr = np.corrcoef(v1, v2)[0, 1]
                if not np.isnan(corr) and corr >= corr_threshold:
                    pairs.append((a1, a2))

        return pairs
    except Exception as e:
        logger.warning(f"find_redundant_pairs failed: {e}")
        return []


def get_redundancy_report():
    """
    Get detailed redundancy analysis for reporting.
    """
    try:
        agents, matrix = compute_agent_signal_vectors()
        correlations = []

        for i, a1 in enumerate(agents):
            for a2 in agents[i+1:]:
                v1, v2 = matrix[a1], matrix[a2]
                if len(v1) < 20:
                    continue

                corr = np.corrcoef(v1, v2)[0, 1]
                if not np.isnan(corr):
                    correlations.append({
                        "agent1": a1,
                        "agent2": a2,
                        "correlation": round(corr, 3),
                        "is_redundant": corr >= CORR_THRESHOLD
                    })

        return {
            "threshold": CORR_THRESHOLD,
            "lookback": CORR_LOOKBACK,
            "agent_count": len(agents),
            "correlations": sorted(correlations, key=lambda x: -x["correlation"])
        }
    except Exception as e:
        logger.warning(f"Redundancy report failed: {e}")
        return {"error": str(e)}
