import os
from meta_supervisor.policy.kill_switch import agent_disabled, strategy_disabled
from meta_supervisor.policy.mode import is_shadow

def _float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def allocate(signal: dict, weights: dict, agent_stats: dict) -> dict:
    agent = signal.get("agent")
    strategy = signal.get("strategy_class") or "unknown"

    if agent_disabled(agent):
        return {"ok": False, "reason": "agent_disabled"}
    if strategy_disabled(strategy):
        return {"ok": False, "reason": "strategy_disabled"}

    w = _float(weights.get(agent, 0.0))
    if w <= 0:
        return {"ok": False, "reason": "no_weight"}

    portfolio_risk_usd = _float(os.environ.get("PORTFOLIO_RISK_BUDGET_USD", "1000"))
    max_pos_usd = _float(os.environ.get("MAX_POSITION_USD", "250"))

    conf = _float(signal.get("confidence", 0.0))
    conf = max(0.0, min(conf, 1.0))

    dd_bps = _float(agent_stats.get(agent, {}).get("max_drawdown_bps", 0.0))
    dd_haircut = 0.5 if dd_bps >= _float(os.environ.get("AGENT_DD_BREACH_BPS", "150")) else 1.0

    target_usd = portfolio_risk_usd * w * conf * dd_haircut
    target_usd = min(target_usd, max_pos_usd)

    routed = not is_shadow()
    return {
        "ok": True,
        "mode": "shadow" if is_shadow() else "live",
        "target_usd": round(target_usd, 2),
        "routed": routed
    }
