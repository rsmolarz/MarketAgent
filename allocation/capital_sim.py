import json
from pathlib import Path
from datetime import datetime, timezone

OUT = Path("allocation/weights.json")
SIM_LOG = Path("allocation/sim_log.json")

def compute_weights(agent_stats: dict, min_weight: float = 0.02) -> dict:
    """
    Compute PnL-weighted capital allocation.
    
    Args:
        agent_stats: Dict of agent name -> stats (must have pnl_sum_bps)
        min_weight: Minimum weight per agent (default 2%)
    
    Returns:
        Dict of agent name -> weight (0-1)
    """
    total_alpha = sum(max(0, a.get("pnl_sum_bps", 0)) for a in agent_stats.values())
    
    if total_alpha <= 0:
        return {}
    
    weights = {}
    for name, a in agent_stats.items():
        if a.get("decision") in ("KILL", "RETIRE"):
            continue
        
        alpha = max(0, float(a.get("pnl_sum_bps", 0)))
        if alpha <= 0:
            continue
        
        w = alpha / total_alpha
        weights[name] = max(min_weight, round(w, 4))
    
    total = sum(weights.values())
    if total > 0:
        for k in weights:
            weights[k] = round(weights[k] / total, 4)
    
    return weights

def simulate_deployment(weights: dict, total_capital: float = 100000) -> dict:
    """
    Simulate capital deployment based on weights.
    
    Args:
        weights: Dict of agent name -> weight (0-1)
        total_capital: Total capital to deploy
    
    Returns:
        Dict with deployment simulation results
    """
    deployment = {}
    for agent, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        allocation = round(total_capital * weight, 2)
        deployment[agent] = {
            "weight": weight,
            "allocation_usd": allocation,
            "pct": round(weight * 100, 2),
        }
    
    return deployment

def save_weights(weights: dict):
    """Save weights to file"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "weights": weights,
    }, indent=2))

def log_simulation(weights: dict, deployment: dict):
    """Log simulation run"""
    SIM_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    log = []
    if SIM_LOG.exists():
        try:
            log = json.loads(SIM_LOG.read_text())
        except Exception:
            log = []
    
    log.append({
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "agents": len(weights),
        "top_3": list(weights.keys())[:3],
        "concentration": round(sum(list(weights.values())[:3]), 4) if weights else 0,
    })
    
    SIM_LOG.write_text(json.dumps(log[-100:], indent=2))

def run(agent_stats: dict, total_capital: float = 100000) -> dict:
    """Run full capital simulation"""
    weights = compute_weights(agent_stats)
    deployment = simulate_deployment(weights, total_capital)
    
    save_weights(weights)
    log_simulation(weights, deployment)
    
    return {
        "weights": weights,
        "deployment": deployment,
        "total_agents": len(weights),
        "total_capital": total_capital,
    }

if __name__ == "__main__":
    report_path = Path("meta_supervisor/reports/meta_report.json")
    if report_path.exists():
        report = json.loads(report_path.read_text())
        result = run(report.get("agents", {}))
        print(json.dumps(result, indent=2))
