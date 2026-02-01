import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

EVENTS = Path("telemetry/events.jsonl")


def load_portfolio_equity(window_n: int = 5000) -> list:
    """Load equity curve from telemetry events."""
    if not EVENTS.exists():
        return []

    eq = 0.0
    curve = []
    try:
        lines = EVENTS.read_text().splitlines()[-window_n:]
        for ln in lines:
            try:
                e = json.loads(ln)
            except json.JSONDecodeError:
                logger.debug(f"Skipping malformed JSON line in events file")
                continue
            r = e.get("reward")
            ts = e.get("ts") or e.get("timestamp")
            if r is None:
                continue
            eq += float(r)
            curve.append({"t": ts, "equity": eq})
    except Exception as ex:
        logger.warning(f"Error loading equity curve: {ex}")
    return curve


def max_drawdown(curve: list) -> float:
    """Calculate maximum drawdown from equity curve."""
    peak = None
    mdd = 0.0
    for p in curve:
        x = p["equity"]
        if peak is None or x > peak:
            peak = x
        dd = x - peak
        if dd < mdd:
            mdd = dd
    return mdd


def drawdown_governor(dd_limit: float = -3.0) -> dict:
    """
    Portfolio drawdown governor.
    
    Args:
        dd_limit: drawdown limit in same units as reward-equity (e.g., bps or %)
    
    Returns:
        dict with:
            - ok (bool): whether portfolio is within limits
            - dd (float): current max drawdown
            - risk_multiplier (0..1): soft throttle multiplier
            - halt (bool): hard stop flag
    """
    curve = load_portfolio_equity()
    if len(curve) < 50:
        return {"ok": True, "dd": 0.0, "risk_multiplier": 1.0, "halt": False}

    dd = max_drawdown(curve)

    if dd <= dd_limit * 1.5:
        logger.warning(f"CATASTROPHIC drawdown: {dd:.2f} <= {dd_limit * 1.5:.2f}")
        return {"ok": False, "dd": dd, "risk_multiplier": 0.0, "halt": True}

    if dd <= dd_limit:
        span = abs(dd_limit * 0.5) or 1.0
        over = abs(dd) - abs(dd_limit)
        mult = max(0.2, 1.0 - (over / span))
        logger.warning(f"Drawdown breach: {dd:.2f}, multiplier={mult:.2f}")
        return {"ok": False, "dd": dd, "risk_multiplier": mult, "halt": False}

    return {"ok": True, "dd": dd, "risk_multiplier": 1.0, "halt": False}


def log_governance_event(event_type: str, details: dict) -> None:
    """Log a governance event to telemetry."""
    path = Path("telemetry/governance.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    
    event = {
        "ts": datetime.utcnow().isoformat(),
        "event_type": event_type,
        **details
    }
    
    with open(path, "a") as f:
        f.write(json.dumps(event) + "\n")


def compute_drawdown_state(dd_limit: float = -0.06, min_risk_mult: float = 0.35) -> dict:
    """
    Compute drawdown state for dashboard display.
    
    Args:
        dd_limit: drawdown limit as fraction (e.g., -0.06 = -6%)
        min_risk_mult: minimum risk multiplier floor
    
    Returns:
        Dict with dd, dd_limit, risk_multiplier, cadence_multiplier, block_new_act, reason
    """
    curve = load_portfolio_equity()
    
    if len(curve) < 50:
        return {
            "dd": 0.0,
            "dd_limit": dd_limit,
            "risk_multiplier": 1.0,
            "cadence_multiplier": 1.0,
            "block_new_act": False,
            "reason": "insufficient_history"
        }
    
    equities = [p["equity"] for p in curve]
    peak = equities[0]
    dd = 0.0
    for v in equities:
        if v > peak:
            peak = v
        if peak != 0:
            dd = min(dd, (v - peak) / abs(peak))
    
    if dd >= dd_limit:
        return {
            "dd": dd,
            "dd_limit": dd_limit,
            "risk_multiplier": 1.0,
            "cadence_multiplier": 1.0,
            "block_new_act": False,
            "reason": "ok"
        }
    
    severity = min(1.0, (abs(dd) - abs(dd_limit)) / max(abs(dd_limit), 1e-9))
    risk_mult = max(min_risk_mult, 1.0 - 0.65 * severity)
    cadence_mult = max(min_risk_mult, 1.0 - 0.50 * severity)
    
    return {
        "dd": dd,
        "dd_limit": dd_limit,
        "risk_multiplier": float(risk_mult),
        "cadence_multiplier": float(cadence_mult),
        "block_new_act": severity > 0.75,
        "reason": "drawdown_protection"
    }
