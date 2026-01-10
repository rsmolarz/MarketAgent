"""
Capital Attribution Report (LP-Grade)

Answers key questions for LPs, ICs, and auditors:
- Where did returns come from?
- What worked in risk-off?
- Why was capital reduced?
"""
from collections import defaultdict
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def build_capital_attribution(days: int = 30):
    """
    Build capital attribution report by regime and agent.
    
    Args:
        days: Number of days to look back
    
    Returns:
        Dict mapping regime -> agent -> total reward
    """
    from pathlib import Path
    import json
    
    events_path = Path("telemetry/events.jsonl")
    
    if events_path.exists():
        try:
            attribution = defaultdict(lambda: defaultdict(float))
            
            for line in events_path.read_text().splitlines()[-5000:]:
                try:
                    e = json.loads(line)
                    agent = e.get("agent")
                    reward = e.get("reward", 0)
                    regime = e.get("regime", "unknown")

                    if agent:
                        attribution[regime][agent] += float(reward)
                except (json.JSONDecodeError, ValueError):
                    continue

            if attribution:
                return {k: dict(v) for k, v in attribution.items()}
        except Exception as e:
            logger.warning(f"Event file read failed: {e}")
    
    return _build_from_findings(days)


def _build_from_findings(days: int = 30):
    """
    Fallback: build attribution from findings table.
    """
    try:
        from models import Finding
        from datetime import datetime, timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        findings = Finding.query.filter(Finding.timestamp >= cutoff).all()
        
        attribution = defaultdict(lambda: defaultdict(float))
        
        severity_rewards = {
            "critical": 2.0,
            "high": 1.0,
            "medium": 0.5,
            "low": 0.25
        }
        
        for f in findings:
            agent = f.agent_name
            regime = getattr(f, 'regime', 'unknown') or 'unknown'
            sev = getattr(f, 'severity', 'medium') or 'medium'
            reward = severity_rewards.get(sev, 0.5)
            
            attribution[regime][agent] += reward
        
        return {k: dict(v) for k, v in attribution.items()}
    except Exception as e:
        logger.error(f"Findings-based attribution failed: {e}")
        return {}


def get_top_performers(n: int = 5):
    """
    Get top N performing agents across all regimes.
    """
    attribution = build_capital_attribution()
    totals = defaultdict(float)
    
    for regime, agents in attribution.items():
        for agent, reward in agents.items():
            totals[agent] += reward
    
    sorted_agents = sorted(totals.items(), key=lambda x: -x[1])
    return sorted_agents[:n]


def get_regime_summary():
    """
    Get summary of total attribution per regime.
    """
    attribution = build_capital_attribution()
    return {
        regime: sum(agents.values())
        for regime, agents in attribution.items()
    }


def generate_attribution_report():
    """
    Generate full LP-grade attribution report.
    """
    attribution = build_capital_attribution()
    top_performers = get_top_performers(10)
    regime_summary = get_regime_summary()
    
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "period_days": 30,
        "by_regime": attribution,
        "top_performers": [
            {"agent": a, "total_reward": round(r, 2)} 
            for a, r in top_performers
        ],
        "regime_totals": {k: round(v, 2) for k, v in regime_summary.items()},
        "summary": {
            "total_agents": len(set(
                agent 
                for agents in attribution.values() 
                for agent in agents.keys()
            )),
            "total_regimes": len(attribution),
            "total_reward": round(sum(regime_summary.values()), 2)
        }
    }
