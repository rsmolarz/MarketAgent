import json
from pathlib import Path
from datetime import datetime, timezone

RECONCILED = Path("alpha/reconciled.jsonl")
TELEMETRY = Path("telemetry/events.jsonl")
KILLED_AGENTS = Path("meta_supervisor/state/killed_agents.json")
KILLED_STRATEGIES = Path("meta_supervisor/state/killed_strategies.json")
PROMOTABLE = Path("meta_supervisor/state/promotable_agents.json")

def load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def load_json_list(p: Path) -> list:
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []

def save_json_list(p: Path, data: list):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))

def compute_agent_metrics(agent: str, lookback: int = 50) -> dict:
    recon = [r for r in load_jsonl(RECONCILED) if r.get("agent") == agent][-lookback:]
    tel = [t for t in load_jsonl(TELEMETRY) if t.get("agent") == agent][-lookback:]
    
    if not recon and not tel:
        return {"exists": False}
    
    pnls = [float(r.get("realized_pnl_bps", 0)) for r in recon]
    rolling_pnl = sum(pnls)
    
    errors = sum(1 for t in tel if t.get("errors", 0) > 0)
    error_rate = errors / max(len(tel), 1)
    
    latencies = [t.get("latency_ms", 0) for t in tel if t.get("latency_ms")]
    median_latency = sorted(latencies)[len(latencies)//2] if latencies else 0
    
    last_5_pnl = sum(pnls[-5:]) if len(pnls) >= 5 else sum(pnls)
    
    return {
        "exists": True,
        "rolling_pnl_bps": round(rolling_pnl, 2),
        "error_rate": round(error_rate, 3),
        "median_latency_ms": median_latency,
        "last_5_runs_pnl": round(last_5_pnl, 2),
        "run_count": len(tel),
        "signal_count": len(recon),
    }

def check_promotion_gate(agent: str) -> dict:
    metrics = compute_agent_metrics(agent)
    
    if not metrics.get("exists"):
        return {"eligible": False, "reason": "No data found"}
    
    eligible = (
        metrics["rolling_pnl_bps"] > 150 and
        metrics["error_rate"] == 0 and
        metrics["median_latency_ms"] < 700
    )
    
    reasons = []
    if metrics["rolling_pnl_bps"] <= 150:
        reasons.append(f"PnL {metrics['rolling_pnl_bps']} bps <= 150 threshold")
    if metrics["error_rate"] > 0:
        reasons.append(f"Error rate {metrics['error_rate']} > 0")
    if metrics["median_latency_ms"] >= 700:
        reasons.append(f"Latency {metrics['median_latency_ms']}ms >= 700ms threshold")
    
    return {
        "eligible": eligible,
        "metrics": metrics,
        "reasons": reasons if reasons else ["All gates passed"]
    }

def check_kill_gate(agent: str) -> dict:
    metrics = compute_agent_metrics(agent)
    
    if not metrics.get("exists"):
        return {"should_kill": False, "reason": "No data found"}
    
    should_kill = (
        metrics["last_5_runs_pnl"] < -100 or
        metrics["error_rate"] > 0.2
    )
    
    reasons = []
    if metrics["last_5_runs_pnl"] < -100:
        reasons.append(f"Last 5 runs PnL {metrics['last_5_runs_pnl']} bps < -100 threshold")
    if metrics["error_rate"] > 0.2:
        reasons.append(f"Error rate {metrics['error_rate']} > 20%")
    
    return {
        "should_kill": should_kill,
        "metrics": metrics,
        "reasons": reasons if reasons else ["No kill conditions met"]
    }

def kill_agent(agent: str):
    killed = load_json_list(KILLED_AGENTS)
    if agent not in killed:
        killed.append(agent)
        save_json_list(KILLED_AGENTS, killed)
    return killed

def promote_agent(agent: str):
    promotable = load_json_list(PROMOTABLE)
    entry = {
        "agent": agent,
        "promoted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "metrics": compute_agent_metrics(agent)
    }
    promotable = [p for p in promotable if p.get("agent") != agent]
    promotable.append(entry)
    save_json_list(PROMOTABLE, promotable)
    return entry

def evaluate_all_agents() -> dict:
    recon = load_jsonl(RECONCILED)
    tel = load_jsonl(TELEMETRY)
    
    agents = set()
    for r in recon:
        agents.add(r.get("agent", "unknown"))
    for t in tel:
        agents.add(t.get("agent", "unknown"))
    
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "promotable": [],
        "killable": [],
        "hold": [],
    }
    
    for agent in agents:
        promo = check_promotion_gate(agent)
        kill = check_kill_gate(agent)
        
        if kill["should_kill"]:
            results["killable"].append({"agent": agent, **kill})
        elif promo["eligible"]:
            results["promotable"].append({"agent": agent, **promo})
        else:
            results["hold"].append({"agent": agent, "promo": promo, "kill": kill})
    
    return results

if __name__ == "__main__":
    result = evaluate_all_agents()
    print(json.dumps(result, indent=2))
