import json
import math
from pathlib import Path
from datetime import datetime, timezone

from meta_supervisor.confidence_decay import get_confidence_multiplier

PORTFOLIO_STATE = Path("meta_supervisor/state/portfolio_state.json")

def portfolio_from_alpha(events: list[dict]) -> dict:
    """Compute portfolio-level metrics from alpha/reconciled events."""
    if not events:
        return {
            "portfolio_pnl_bps": 0,
            "portfolio_hit_rate": 0,
            "portfolio_max_drawdown_bps": 0,
            "total_signals": 0,
            "sharpe_approx": 0,
        }

    pnl = []
    for e in events:
        pnl.append(float(e.get("realized_pnl_bps", 0)))

    total = sum(pnl)
    hit = sum(1 for p in pnl if p > 0) / max(len(pnl), 1)

    eq = 0
    peak = 0
    max_dd = 0
    for p in pnl:
        eq += p
        peak = max(peak, eq)
        max_dd = min(max_dd, eq - peak)

    avg = total / max(len(pnl), 1)
    variance = sum((p - avg) ** 2 for p in pnl) / max(len(pnl), 1)
    std = math.sqrt(variance) if variance > 0 else 1
    sharpe = (avg / std) * math.sqrt(252) if std > 0 else 0

    return {
        "portfolio_pnl_bps": round(total, 2),
        "portfolio_hit_rate": round(hit, 3),
        "portfolio_max_drawdown_bps": round(max_dd, 2),
        "total_signals": len(pnl),
        "sharpe_approx": round(sharpe, 3),
    }

def compute_agent_weights(agent_stats: dict) -> dict:
    """
    Compute capital allocation weights using softmax.
    
    weight = softmax(alpha * confidence / volatility)
    """
    raw_scores = {}
    
    for name, stats in agent_stats.items():
        pnl = float(stats.get("pnl_sum_bps", 0))
        hit_rate = float(stats.get("hit_rate", 0))
        error_rate = float(stats.get("error_rate", 0))
        
        if error_rate > 0.05 or pnl <= 0:
            continue
        
        confidence = get_confidence_multiplier(name)
        
        volatility = 1.0 + (1.0 - hit_rate)
        
        score = (pnl * confidence) / volatility
        raw_scores[name] = max(score, 0.001)
    
    if not raw_scores:
        return {}
    
    max_score = max(raw_scores.values())
    exp_scores = {k: math.exp(v / max(max_score, 1)) for k, v in raw_scores.items()}
    total_exp = sum(exp_scores.values())
    
    weights = {k: round(v / total_exp, 4) for k, v in exp_scores.items()}
    
    return weights

def portfolio_attribution(events: list[dict], agent_stats: dict) -> dict:
    """
    Compute per-agent attribution to portfolio performance.
    """
    by_agent = {}
    
    for e in events:
        agent = e.get("agent", "unknown")
        pnl = float(e.get("realized_pnl_bps", 0))
        by_agent.setdefault(agent, []).append(pnl)
    
    total_portfolio_pnl = sum(sum(pnls) for pnls in by_agent.values())
    
    attribution = {}
    for agent, pnls in by_agent.items():
        agent_pnl = sum(pnls)
        contribution = (agent_pnl / total_portfolio_pnl * 100) if total_portfolio_pnl != 0 else 0
        
        attribution[agent] = {
            "pnl_bps": round(agent_pnl, 2),
            "signal_count": len(pnls),
            "hit_rate": round(sum(1 for p in pnls if p > 0) / max(len(pnls), 1), 3),
            "contribution_pct": round(contribution, 2),
        }
    
    return attribution

def get_lp_metrics(events: list[dict], agent_stats: dict) -> dict:
    """
    Generate LP-grade portfolio metrics.
    """
    portfolio = portfolio_from_alpha(events)
    weights = compute_agent_weights(agent_stats)
    attribution = portfolio_attribution(events, agent_stats)
    
    active_agents = [n for n, s in agent_stats.items() if s.get("decision") != "KILL"]
    killed_agents = [n for n, s in agent_stats.items() if s.get("decision") == "KILL"]
    
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "portfolio": portfolio,
        "allocation_weights": weights,
        "attribution": attribution,
        "agent_counts": {
            "active": len(active_agents),
            "killed": len(killed_agents),
            "total": len(agent_stats),
        },
        "active_agents": active_agents,
        "killed_agents": killed_agents,
    }
