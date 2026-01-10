import json
import yaml
from pathlib import Path
from datetime import datetime, timezone

from meta_supervisor.agent_registry import AGENT_STRATEGY_CLASS

KILL_LIST_PATH = Path("meta_supervisor/strategy_kill_list.yaml")


RECON = Path("alpha/reconciled.jsonl")
OUT = Path("meta_supervisor/state/strategy_attribution.json")


def cvar(values: list, alpha: float = 0.95) -> float:
    """Compute Conditional Value at Risk (expected shortfall) at given alpha."""
    if not values:
        return 0.0
    vs = sorted(values)
    cutoff = int(len(vs) * alpha)
    tail = vs[cutoff:]
    if not tail:
        return vs[-1] if vs else 0.0
    return sum(tail) / len(tail)

def load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def load_kill_list() -> dict:
    if not KILL_LIST_PATH.exists():
        return {}
    try:
        return yaml.safe_load(KILL_LIST_PATH.read_text()) or {}
    except Exception:
        return {}

def save_kill_list(data: dict):
    KILL_LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    KILL_LIST_PATH.write_text(yaml.dump(data, default_flow_style=False))

def strategy_attribution(events: list[dict]) -> dict:
    """Compute PnL attribution by strategy class with CVaR on forecast error"""
    by_strategy = {}
    
    for e in events:
        agent = e.get("agent", "unknown")
        strategy = AGENT_STRATEGY_CLASS.get(agent, "unknown")
        pnl = float(e.get("realized_pnl_bps", 0))
        pnl_error = e.get("pnl_error_bps")
        
        if strategy not in by_strategy:
            by_strategy[strategy] = {
                "pnl_sum_bps": 0,
                "trades": 0,
                "hits": 0,
                "agents": set(),
                "errors": [],
            }
        
        by_strategy[strategy]["pnl_sum_bps"] += pnl
        by_strategy[strategy]["trades"] += 1
        by_strategy[strategy]["hits"] += 1 if pnl > 0 else 0
        by_strategy[strategy]["agents"].add(agent)
        if pnl_error is not None:
            try:
                by_strategy[strategy]["errors"].append(float(pnl_error))
            except (ValueError, TypeError):
                pass
    
    result = {}
    for s, data in by_strategy.items():
        result[s] = {
            "pnl_sum_bps": round(data["pnl_sum_bps"], 2),
            "trades": data["trades"],
            "hit_rate": round(data["hits"] / max(data["trades"], 1), 3),
            "agents": list(data["agents"]),
            "cvar_error_bps": round(cvar(data["errors"]), 2) if data["errors"] else None,
        }
    
    return result

def evaluate_strategy_thresholds(attribution: dict) -> list[dict]:
    """Check if any strategy breaches kill thresholds"""
    kill_list = load_kill_list()
    breaches = []
    
    for strategy, stats in attribution.items():
        config = kill_list.get(strategy, {})
        if config.get("status") == "DISABLED":
            continue
        
        max_dd = config.get("max_drawdown_bps", -500)
        min_hit = config.get("min_hit_rate", 0.30)
        
        max_cvar = config.get("max_cvar_error_bps", 120)
        
        reasons = []
        if stats["pnl_sum_bps"] < max_dd:
            reasons.append(f"PnL {stats['pnl_sum_bps']} < {max_dd} bps")
        if stats["hit_rate"] < min_hit and stats["trades"] >= 10:
            reasons.append(f"Hit rate {stats['hit_rate']} < {min_hit}")
        if stats.get("cvar_error_bps") is not None and stats["cvar_error_bps"] > max_cvar:
            reasons.append(f"CVaR error {stats['cvar_error_bps']} > {max_cvar}")
        
        if reasons:
            breaches.append({
                "strategy": strategy,
                "agents": stats["agents"],
                "pnl_sum_bps": stats["pnl_sum_bps"],
                "hit_rate": stats["hit_rate"],
                "reasons": reasons,
            })
    
    return breaches

def disable_strategy(strategy: str, reason: str):
    """Disable a strategy class"""
    kill_list = load_kill_list()
    if strategy in kill_list:
        kill_list[strategy]["status"] = "DISABLED"
        kill_list[strategy]["reason"] = reason
        kill_list[strategy]["disabled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        kill_list[strategy] = {
            "status": "DISABLED",
            "reason": reason,
            "disabled_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    save_kill_list(kill_list)

def run() -> dict:
    """Run strategy attribution analysis"""
    recon = [r for r in load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == 24]
    
    attribution = strategy_attribution(recon)
    breaches = evaluate_strategy_thresholds(attribution)
    
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "attribution": attribution,
        "breaches": breaches,
        "strategies_evaluated": len(attribution),
        "strategies_breached": len(breaches),
    }
    
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    
    return result

if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
