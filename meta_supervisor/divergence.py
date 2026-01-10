import json
from pathlib import Path
from datetime import datetime, timezone

RECON = Path("alpha/reconciled.jsonl")
SIM_LOG = Path("allocation/sim_log.json")
STATE = Path("meta_supervisor/state/divergence.json")

ALERT_THRESHOLD_BPS = 100

def load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def load_json(p: Path):
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def save_state(state: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))

def compute_divergence(horizon_hours: int = 24) -> dict:
    """
    Compute divergence between simulated and live performance.
    
    Compares:
    - Simulated: Expected PnL based on allocation weights
    - Live: Actual realized PnL from reconciled events
    """
    recon = [r for r in load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == horizon_hours]
    
    if not recon:
        return {
            "divergence_bps": 0,
            "alert": False,
            "reason": "no_data",
        }
    
    by_agent = {}
    for r in recon[-100:]:
        agent = r.get("agent", "unknown")
        pnl = float(r.get("realized_pnl_bps", 0))
        by_agent.setdefault(agent, []).append(pnl)
    
    live_pnl = {agent: sum(pnls) for agent, pnls in by_agent.items()}
    live_total = sum(live_pnl.values())
    
    weights_data = load_json(Path("allocation/weights.json"))
    weights = weights_data.get("weights", {})
    
    if not weights:
        return {
            "divergence_bps": 0,
            "alert": False,
            "reason": "no_weights",
            "live_pnl_bps": round(live_total, 2),
        }
    
    sim_total = 0
    for agent, weight in weights.items():
        agent_pnl = live_pnl.get(agent, 0)
        sim_total += agent_pnl * weight
    
    divergence = abs(live_total - sim_total)
    
    alert = divergence > ALERT_THRESHOLD_BPS
    
    result = {
        "computed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "horizon_hours": horizon_hours,
        "live_pnl_bps": round(live_total, 2),
        "sim_pnl_bps": round(sim_total, 2),
        "divergence_bps": round(divergence, 2),
        "alert": alert,
        "threshold_bps": ALERT_THRESHOLD_BPS,
        "agents_compared": len(by_agent),
    }
    
    save_state(result)
    return result

def get_latest_divergence() -> dict:
    """Get latest divergence state"""
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}

if __name__ == "__main__":
    print(json.dumps(compute_divergence(), indent=2))
