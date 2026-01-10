import json
from pathlib import Path
from math import sqrt
from meta_supervisor.confidence_decay import get_confidence_multiplier
from meta_supervisor.strategy_cvar import run as strategy_cvar_run
from meta_supervisor.regime_policy import regime_cap

ALLOCATION_STATE = Path("meta_supervisor/state/allocation.json")

MAX_WEIGHT = 0.25
MIN_CONF = 0.50
CVAR_PENALTY_K = 0.015
DD_PENALTY_K = 0.01

def _safe(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d

def compute_weights(agent_stats: dict) -> dict:
    raw = {}

    strategy_cvar = strategy_cvar_run(horizon_hours=24)

    for name, s in agent_stats.items():
        pnl = _safe(s.get("pnl_sum_bps"))
        hit = _safe(s.get("hit_rate"))
        err = _safe(s.get("error_rate"))
        avg_abs_err = _safe(s.get("avg_abs_error_bps"), 999)
        strategy = s.get("strategy", "unclassified")

        if err > 0.15:
            continue
        if pnl <= 0:
            continue

        q = sqrt(max(pnl, 0)) * (0.6 + hit)

        conf_mult = get_confidence_multiplier(name)
        q *= conf_mult

        sim_penalty = 1.0 / (1.0 + avg_abs_err / 75.0)
        q *= sim_penalty

        strat_cvar = _safe(strategy_cvar.get(strategy, {}).get("gap_cvar95_bps", 0))
        if strat_cvar < 0:
            q *= max(0.25, 1.0 + strat_cvar * CVAR_PENALTY_K)

        dd = _safe(s.get("max_drawdown_bps", 0))
        if dd < 0:
            q *= max(0.4, 1.0 + dd * DD_PENALTY_K)

        if q > 0:
            raw[name] = q

    total = sum(raw.values())
    if total <= 0:
        return {}

    weights = {k: v / total for k, v in raw.items()}

    capped = {}
    excess = 0.0
    for k, w in weights.items():
        if w > MAX_WEIGHT:
            capped[k] = MAX_WEIGHT
            excess += w - MAX_WEIGHT
        else:
            capped[k] = w

    if excess > 0:
        free = sum(v for v in capped.values() if v < MAX_WEIGHT)
        if free > 0:
            for k in capped:
                if capped[k] < MAX_WEIGHT:
                    capped[k] += excess * (capped[k] / free)

    try:
        from meta_supervisor.state.fleet_state import get_current_regime
        current_reg = get_current_regime()
    except Exception:
        current_reg = None

    cap = regime_cap(current_reg)
    if cap < 0.999:
        capped = {k: v * cap for k, v in capped.items()}
        s = sum(capped.values()) or 1.0
        capped = {k: v / s for k, v in capped.items()}

    return {k: round(v, 6) for k, v in capped.items()}

def save_weights(weights: dict):
    ALLOCATION_STATE.parent.mkdir(parents=True, exist_ok=True)
    ALLOCATION_STATE.write_text(json.dumps(weights, indent=2))

def main(agent_stats: dict):
    w = compute_weights(agent_stats)
    save_weights(w)
    return w
