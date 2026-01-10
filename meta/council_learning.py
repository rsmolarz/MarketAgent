"""
Council Learning Module
Tracks LLM council voting outcomes per agent to identify "fail-first" agents.
Agents with high ignore rates under uncertainty get weight penalties.
"""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_cached_regime() -> str:
    """Get current regime from cache or return default."""
    try:
        from regime.confidence import get_cached_regime as _get_regime
        return _get_regime() or "unknown"
    except ImportError:
        return "unknown"


def record_council_outcome(agent_name: str, decision: str) -> None:
    """
    Record a council voting outcome for an agent.
    Updates per-agent per-regime statistics for fail-first tracking.
    """
    from app import db
    from models import AgentCouncilStat

    regime = get_cached_regime()
    
    try:
        row = AgentCouncilStat.query.filter_by(
            agent_name=agent_name, 
            regime=regime
        ).first()
        
        if not row:
            row = AgentCouncilStat(agent_name=agent_name, regime=regime)
            db.session.add(row)
        
        decision_upper = (decision or "").upper()
        
        if decision_upper == "ACT":
            row.votes_act += 1
        elif decision_upper == "WATCH":
            row.votes_watch += 1
        else:
            row.votes_ignore += 1
            row.last_ignore_ts = datetime.utcnow()
            if not row.first_failure_ts:
                row.first_failure_ts = datetime.utcnow()
        
        row.last_updated = datetime.utcnow()
        db.session.commit()
        
        logger.debug(f"Recorded council outcome: {agent_name} -> {decision} (regime={regime})")
        
    except Exception as e:
        logger.error(f"Error recording council outcome for {agent_name}: {e}")
        db.session.rollback()


def fail_first_ranking(min_n: int = 10, regime: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns agents ranked by ignore rate (highest first) in current regime.
    Only includes agents with at least min_n council votes.
    
    Returns:
        List of {"agent": str, "fail_rate": float, "n": int, "regime": str}
    """
    from models import AgentCouncilStat
    
    if regime is None:
        regime = get_cached_regime()
    
    try:
        rows = AgentCouncilStat.query.filter_by(regime=regime).all()
        ranked = []
        
        for r in rows:
            n = r.total_votes
            if n < min_n:
                continue
            
            fail_rate = r.ignore_rate
            ranked.append({
                "agent": r.agent_name,
                "fail_rate": round(fail_rate, 3),
                "n": n,
                "regime": r.regime,
                "last_ignore": r.last_ignore_ts.isoformat() if r.last_ignore_ts else None,
            })
        
        ranked.sort(key=lambda x: x["fail_rate"], reverse=True)
        return ranked
        
    except Exception as e:
        logger.error(f"Error computing fail-first ranking: {e}")
        return []


def get_agent_fail_rate(agent_name: str, regime: Optional[str] = None) -> float:
    """
    Get the ignore/fail rate for a specific agent in the given regime.
    Returns 0.0 if agent has insufficient data.
    """
    from models import AgentCouncilStat
    
    if regime is None:
        regime = get_cached_regime()
    
    try:
        row = AgentCouncilStat.query.filter_by(
            agent_name=agent_name,
            regime=regime
        ).first()
        
        if not row or row.total_votes < 5:
            return 0.0
        
        return row.ignore_rate
        
    except Exception as e:
        logger.error(f"Error getting fail rate for {agent_name}: {e}")
        return 0.0
