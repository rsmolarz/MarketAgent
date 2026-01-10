"""
Regime-Conditioned Backtest Report

Provides explainability layer showing why an agent was on/off in a regime.
This is the transparency layer that institutional investors ask for.
"""

from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def build_regime_report(agent: str, regime: str) -> Dict[str, Any]:
    """
    Generate a comprehensive report explaining agent behavior in a regime.
    
    Args:
        agent: Agent name (e.g., "MarketCorrectionAgent")
        regime: Market regime (e.g., "risk_on", "risk_off")
    
    Returns:
        Report with ignore_rate, votes, substitution status, and uncertainty info
    """
    from models import AgentCouncilStat, AgentSubstitution, UncertaintyEvent
    
    stat = (
        AgentCouncilStat.query
        .filter_by(agent_name=agent, regime=regime)
        .first()
    )
    
    subs = (
        AgentSubstitution.query
        .filter_by(from_agent=agent, regime=regime)
        .order_by(AgentSubstitution.timestamp.desc())
        .all()
    )
    
    uncertainty = (
        UncertaintyEvent.query
        .filter_by(active_regime=regime)
        .order_by(UncertaintyEvent.timestamp.desc())
        .first()
    )
    
    return {
        "agent": agent,
        "regime": regime,
        "ignore_rate": round(stat.ignore_rate, 3) if stat else None,
        "votes": stat.total_votes if stat else 0,
        "votes_act": stat.votes_act if stat else 0,
        "votes_watch": stat.votes_watch if stat else 0,
        "votes_ignore": stat.votes_ignore if stat else 0,
        "substituted": bool(subs),
        "substitution_reason": subs[0].reason if subs else None,
        "substitute_agent": subs[0].to_agent if subs else None,
        "substitution_time": subs[0].timestamp.isoformat() if subs else None,
        "uncertainty_score": uncertainty.score if uncertainty else None,
        "uncertainty_spike": uncertainty.spike if uncertainty else False,
        "uncertainty_time": uncertainty.timestamp.isoformat() if uncertainty else None,
    }


def build_multi_agent_report(agents: list, regime: str) -> Dict[str, Any]:
    """
    Generate reports for multiple agents in a regime.
    """
    return {
        "regime": regime,
        "generated_at": datetime.utcnow().isoformat(),
        "agents": {
            agent: build_regime_report(agent, regime)
            for agent in agents
        }
    }


def get_inactive_agents_explanation(regime: str) -> list:
    """
    Get explanations for all inactive agents in a regime.
    
    Returns list of agents that are substituted or have high ignore rates.
    """
    from models import AgentCouncilStat, AgentSubstitution
    
    IGNORE_THRESHOLD = 0.55
    explanations = []
    
    high_ignore = (
        AgentCouncilStat.query
        .filter_by(regime=regime)
        .all()
    )
    
    for stat in high_ignore:
        if stat.ignore_rate >= IGNORE_THRESHOLD and stat.total_votes >= 12:
            sub = (
                AgentSubstitution.query
                .filter_by(from_agent=stat.agent_name, regime=regime)
                .order_by(AgentSubstitution.timestamp.desc())
                .first()
            )
            
            explanations.append({
                "agent": stat.agent_name,
                "reason": "high_ignore_rate",
                "ignore_rate": round(stat.ignore_rate, 3),
                "votes": stat.total_votes,
                "substituted_by": sub.to_agent if sub else None,
                "substitution_time": sub.timestamp.isoformat() if sub else None,
            })
    
    return explanations
