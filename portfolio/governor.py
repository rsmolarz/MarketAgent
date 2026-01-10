from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
import numpy as np

@dataclass
class DrawdownBands:
    warn: float = -0.05
    risk_off: float = -0.10
    max_risk_off: float = -0.20

@dataclass
class GovernorState:
    dd: float
    band: str
    multiplier: float
    reason: str

class PortfolioDrawdownGovernor:
    """
    Caps portfolio gross exposure based on current drawdown.
    Exposure multiplier is applied AFTER signal sizing (i.e., last gate).
    """
    def __init__(self, bands: DrawdownBands = DrawdownBands()):
        self.bands = bands

    def compute(self, current_drawdown: float) -> GovernorState:
        dd = float(current_drawdown)
        if dd <= self.bands.max_risk_off:
            return GovernorState(dd, "max_risk_off", 0.15, "Deep drawdown band")
        if dd <= self.bands.risk_off:
            return GovernorState(dd, "risk_off", 0.35, "Correction drawdown band")
        if dd <= self.bands.warn:
            return GovernorState(dd, "warn", 0.70, "Warning drawdown band")
        return GovernorState(dd, "normal", 1.00, "No drawdown constraint")

def findings_to_risk_signal(findings: List[Dict[str, Any]]) -> float:
    """
    Collapse findings into a single risk score (0..1).
    High/critical increase risk-off pressure.
    """
    if not findings:
        return 0.0
    w = {"low": 0.10, "medium": 0.25, "high": 0.55, "critical": 0.85}
    scores = []
    for f in findings:
        sev = str(f.get("severity", "medium")).lower()
        conf = float(f.get("confidence", 0.5))
        scores.append(w.get(sev, 0.25) * conf)
    raw = float(np.clip(sum(scores), 0.0, 2.0))
    return float(1.0 - np.exp(-raw))

def regime_multiplier(regime: str, vol_label: str) -> float:
    """
    Optional: dampen risk-on sizing in volatility/transition regimes.
    """
    r = (regime or "unknown").lower()
    v = (vol_label or "elevated").lower()

    if r == "volatility":
        return 0.50
    if r == "transition":
        return 0.70
    if r == "mean_reversion" and v == "high":
        return 0.65
    return 1.00

def allocate_exposure(
    base_target: float,
    risk_signal: float,
    regime: str,
    vol_label: str,
    governor: GovernorState,
) -> Dict[str, Any]:
    """
    Example policy:
      - base_target: your normal gross exposure (e.g., 1.0)
      - risk_signal: 0..1 where 1 = strong risk-off
      - final exposure = base_target * (1 - 0.8*risk_signal) * regime_mult * dd_mult
    """
    base = float(base_target)
    rs = float(risk_signal)
    rs_mult = float(max(0.10, 1.0 - 0.80 * rs))
    reg_mult = float(regime_multiplier(regime, vol_label))
    dd_mult = float(governor.multiplier)

    final = base * rs_mult * reg_mult * dd_mult
    return {
        "base_target": base,
        "risk_signal": rs,
        "risk_multiplier": rs_mult,
        "regime": regime,
        "vol_label": vol_label,
        "regime_multiplier": reg_mult,
        "drawdown": governor.dd,
        "drawdown_band": governor.band,
        "drawdown_multiplier": dd_mult,
        "final_target_exposure": final,
        "reason": governor.reason,
    }
