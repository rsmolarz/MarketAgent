import json
import math
from pathlib import Path
from datetime import datetime, timezone

STATE = Path("meta_supervisor/state/cvar_weights.json")

def compute_cvar(pnls: list[float], alpha: float = 0.95) -> float:
    """
    Compute Conditional Value at Risk (CVaR) at given confidence level.
    
    CVaR = average of losses beyond VaR threshold
    Lower (more negative) CVaR = higher tail risk
    """
    if not pnls or len(pnls) < 5:
        return 0
    
    sorted_pnls = sorted(pnls)
    var_index = int((1 - alpha) * len(sorted_pnls))
    var_index = max(0, min(var_index, len(sorted_pnls) - 1))
    
    tail = sorted_pnls[:var_index + 1]
    if not tail:
        return sorted_pnls[0]
    
    return sum(tail) / len(tail)

def compute_cvar_weights(agent_pnls: dict, agents: dict, alpha: float = 0.95) -> dict:
    """
    Compute allocation weights using CVaR-adjusted returns.
    
    weight = (mean_return - λ * CVaR) / total
    
    Args:
        agent_pnls: Dict of agent -> list of PnL values
        agents: Agent stats dict (for filtering killed agents)
        alpha: CVaR confidence level (0.95 = 5% tail)
    
    Returns:
        Dict of agent -> weight (0-1)
    """
    lambda_risk = 0.5
    
    raw_scores = {}
    for agent, pnls in agent_pnls.items():
        if agents.get(agent, {}).get("decision") in ("KILL", "RETIRE"):
            continue
        
        if not pnls or len(pnls) < 5:
            continue
        
        mean_return = sum(pnls) / len(pnls)
        cvar = compute_cvar(pnls, alpha)
        
        risk_adjusted = mean_return - (lambda_risk * abs(cvar))
        
        if risk_adjusted <= 0:
            continue
        
        raw_scores[agent] = risk_adjusted
    
    if not raw_scores:
        return {}
    
    total = sum(raw_scores.values())
    weights = {k: round(v / total, 4) for k, v in raw_scores.items()}
    
    state = {
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "method": "cvar",
        "alpha": alpha,
        "lambda": lambda_risk,
        "weights": weights,
        "agents_included": len(weights),
    }
    
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))
    
    return weights

def get_cvar_weights() -> dict:
    """Get latest CVaR weights"""
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text()).get("weights", {})
    except Exception:
        return {}

if __name__ == "__main__":
    RECON = Path("alpha/reconciled.jsonl")
    REPORT = Path("meta_supervisor/reports/meta_report.json")
    
    def load_jsonl(p):
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    
    recon = [r for r in load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == 24]
    
    agent_pnls = {}
    for r in recon:
        agent = r.get("agent", "unknown")
        pnl = float(r.get("realized_pnl_bps", 0))
        agent_pnls.setdefault(agent, []).append(pnl)
    
    agents = {}
    if REPORT.exists():
        agents = json.loads(REPORT.read_text()).get("agents", {})
    
    weights = compute_cvar_weights(agent_pnls, agents)
    print(json.dumps(weights, indent=2))
