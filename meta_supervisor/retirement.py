import json
from pathlib import Path
from datetime import datetime, timezone

RETIREMENT_LOG = Path("meta_supervisor/state/retirement_log.json")
KILLED_AGENTS = Path("meta_supervisor/state/killed_agents.json")
KILLED_STRATEGIES = Path("meta_supervisor/state/killed_strategies.json")

def retirement_score(stats: dict) -> int:
    """
    Compute retirement score for an agent.
    Higher score = more likely to retire.
    """
    score = 0
    
    alpha_signals = stats.get("alpha_signals", 0)
    runs = stats.get("runs", 0)
    avg_latency = stats.get("avg_latency_ms") or 0
    error_rate = float(stats.get("error_rate", 0))
    pnl = float(stats.get("pnl_sum_bps", 0))
    
    if alpha_signals == 0 and runs > 10:
        score += 25
    
    if avg_latency > 5000:
        score += 20
    
    if runs > 50 and alpha_signals < 3:
        score += 40
    
    if error_rate > 0.05:
        score += 15
    
    if pnl < 0:
        score += 20
    
    return min(score, 100)

def retirement_label(score: int) -> str:
    """Convert retirement score to action label."""
    if score >= 80:
        return "RETIRE"
    elif score >= 50:
        return "DEPRECATE"
    elif score >= 30:
        return "WATCH"
    else:
        return "HEALTHY"

def evaluate_retirements(report: dict) -> dict:
    """
    Evaluate all agents for retirement.
    
    Kill when any 2 of 4 conditions are true:
    1. Alpha < 0 for N periods (negative PnL)
    2. Confidence decay > threshold (multiplier < 0.5)
    3. Cost > value delivered
    4. Repeated regime mismatch (error rate > 10%)
    """
    agents = report.get("agents", {})
    confidence_state = report.get("allocation", {}).get("confidence_state", {})
    
    to_kill = []
    to_deprecate = []
    healthy = []
    
    for name, stats in agents.items():
        conditions_met = 0
        reasons = []
        
        pnl = float(stats.get("pnl_sum_bps", 0))
        if pnl < 0:
            conditions_met += 1
            reasons.append(f"Negative PnL: {pnl} bps")
        
        conf = confidence_state.get(name, {})
        mult = float(conf.get("confidence_multiplier", 1.0))
        if mult < 0.5:
            conditions_met += 1
            reasons.append(f"Confidence decay: {mult}x")
        
        cost = float(stats.get("cost_usd", 0))
        if cost > 0 and pnl <= 0:
            conditions_met += 1
            reasons.append(f"Cost ${cost:.4f} with no positive PnL")
        
        error_rate = float(stats.get("error_rate", 0))
        if error_rate > 0.10:
            conditions_met += 1
            reasons.append(f"High error rate: {error_rate*100:.1f}%")
        
        score = stats.get("retirement_score", retirement_score(stats))
        label = stats.get("retirement_action", retirement_label(score))
        
        entry = {
            "agent": name,
            "score": score,
            "label": label,
            "conditions_met": conditions_met,
            "reason": "; ".join(reasons) if reasons else "No issues",
        }
        
        if conditions_met >= 2 or label == "RETIRE":
            to_kill.append(entry)
        elif conditions_met >= 1 or label == "DEPRECATE":
            to_deprecate.append(entry)
        else:
            healthy.append(entry)
    
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "to_kill": to_kill,
        "to_deprecate": to_deprecate,
        "healthy": healthy,
        "summary": {
            "total": len(agents),
            "kill_count": len(to_kill),
            "deprecate_count": len(to_deprecate),
            "healthy_count": len(healthy),
        }
    }

def kill_agent(agent_name: str, reason: str):
    """Add agent to kill list."""
    killed = []
    if KILLED_AGENTS.exists():
        try:
            killed = json.loads(KILLED_AGENTS.read_text())
        except Exception:
            killed = []
    
    existing = [k for k in killed if k.get("agent") != agent_name]
    existing.append({
        "agent": agent_name,
        "killed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reason": reason,
    })
    
    KILLED_AGENTS.parent.mkdir(parents=True, exist_ok=True)
    KILLED_AGENTS.write_text(json.dumps(existing, indent=2))

def kill_strategy_class(strategy_name: str, reason: str):
    """Kill an entire strategy class."""
    killed = []
    if KILLED_STRATEGIES.exists():
        try:
            killed = json.loads(KILLED_STRATEGIES.read_text())
        except Exception:
            killed = []
    
    existing = [k for k in killed if k.get("strategy") != strategy_name]
    existing.append({
        "strategy": strategy_name,
        "killed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reason": reason,
        "status": "killed",
    })
    
    KILLED_STRATEGIES.parent.mkdir(parents=True, exist_ok=True)
    KILLED_STRATEGIES.write_text(json.dumps(existing, indent=2))

def is_agent_killed(agent_name: str) -> bool:
    """Check if agent is on kill list."""
    if not KILLED_AGENTS.exists():
        return False
    try:
        killed = json.loads(KILLED_AGENTS.read_text())
        return any(k.get("agent") == agent_name for k in killed)
    except Exception:
        return False
