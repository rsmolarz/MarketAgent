import json
from pathlib import Path
from datetime import datetime, timezone

RECON = Path("alpha/reconciled.jsonl")
STATE = Path("meta_supervisor/state/regime_multipliers.json")

REGIME_BASE = {
    "TRENDING": 1.0,
    "RANGING": 0.8,
    "VOLATILE": 0.6,
    "MIXED": 0.7,
    "UNKNOWN": 0.5,
}

DRAWDOWN_THRESHOLDS = [
    (-500, 0.3),
    (-300, 0.5),
    (-150, 0.7),
    (-50, 0.9),
    (0, 1.0),
]

def load_jsonl(p: Path):
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def load_state():
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}

def save_state(state: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))

def drawdown_multiplier(cumulative_pnl_bps: float) -> float:
    """Compute drawdown-aware multiplier based on cumulative PnL"""
    for threshold, mult in DRAWDOWN_THRESHOLDS:
        if cumulative_pnl_bps <= threshold:
            return mult
    return 1.0

def compute_regime_multipliers(horizon_hours: int = 24) -> dict:
    """
    Compute regime multipliers with drawdown awareness.
    
    Returns dict of regime -> multiplier
    """
    recon = [r for r in load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == horizon_hours]
    
    by_regime = {}
    for r in recon:
        regime = r.get("regime", "UNKNOWN") or "UNKNOWN"
        pnl = float(r.get("realized_pnl_bps", 0))
        by_regime.setdefault(regime, []).append(pnl)
    
    multipliers = {}
    for regime, pnls in by_regime.items():
        base = REGIME_BASE.get(regime, 0.5)
        
        cumulative = sum(pnls)
        dd_mult = drawdown_multiplier(cumulative)
        
        hit_rate = sum(1 for p in pnls if p > 0) / max(len(pnls), 1)
        hit_adj = 0.8 + (hit_rate * 0.4)
        
        final = round(base * dd_mult * hit_adj, 4)
        final = max(0.1, min(final, 1.2))
        
        multipliers[regime] = {
            "multiplier": final,
            "base": base,
            "drawdown_adj": dd_mult,
            "hit_adj": round(hit_adj, 4),
            "cumulative_pnl_bps": round(cumulative, 2),
            "trades": len(pnls),
            "hit_rate": round(hit_rate, 3),
        }
    
    state = {
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "horizon_hours": horizon_hours,
        "regimes": multipliers,
    }
    save_state(state)
    
    return multipliers

def get_regime_multiplier(regime: str) -> float:
    """Get multiplier for a specific regime"""
    state = load_state()
    regimes = state.get("regimes", {})
    return float(regimes.get(regime, {}).get("multiplier", REGIME_BASE.get(regime, 0.5)))

if __name__ == "__main__":
    print(json.dumps(compute_regime_multipliers(), indent=2))
