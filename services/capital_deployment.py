"""
Capital Deployment Logic for Distressed Real Estate

This module controls how capital is actually deployed based on:
- Macro gate status (GREEN / YELLOW / RED)
- Portfolio drawdown
- Regime classification
- Margin-of-safety requirements

Agents don't trade - capital does.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CapitalDecision:
    """Result of capital deployment calculation."""
    base_commitment: float
    adjusted_commitment: float
    max_capital_pct: float
    mos_multiplier: float
    gate: str
    regime: str
    drawdown: float
    reason: str


def real_estate_capital_target(
    base_commitment: float,
    macro_meta: Dict[str, Any]
) -> float:
    """
    Calculate adjusted capital commitment based on macro conditions.
    
    Args:
        base_commitment: Normal deal size (e.g., $2M)
        macro_meta: From DistressedMacroGateAgent.metadata
        
    Returns:
        Adjusted capital commitment
    """
    max_pct = macro_meta.get("max_capital_pct", 1.0)
    return base_commitment * max_pct


def required_mos(base_mos: float, macro_meta: Dict[str, Any]) -> float:
    """
    Calculate required margin-of-safety based on macro conditions.
    
    Args:
        base_mos: Normal margin-of-safety (e.g., 1.0 = 100%)
        macro_meta: From DistressedMacroGateAgent.metadata
        
    Returns:
        Required margin-of-safety multiplier
    """
    multiplier = macro_meta.get("mos_multiplier", 1.0)
    return base_mos * multiplier


def compute_capital_decision(
    base_commitment: float,
    base_mos: float,
    macro_meta: Dict[str, Any]
) -> CapitalDecision:
    """
    Compute full capital deployment decision.
    
    Args:
        base_commitment: Normal deal size
        base_mos: Normal margin-of-safety requirement
        macro_meta: From DistressedMacroGateAgent.metadata
        
    Returns:
        CapitalDecision with all parameters
    """
    gate = macro_meta.get("gate", "GREEN")
    regime = macro_meta.get("regime", "unknown")
    drawdown = macro_meta.get("portfolio_drawdown", 0.0)
    max_pct = macro_meta.get("max_capital_pct", 1.0)
    mos_mult = macro_meta.get("mos_multiplier", 1.0)
    
    adjusted = base_commitment * max_pct
    
    reasons = []
    if gate == "RED":
        reasons.append(f"Capital preservation mode (DD: {drawdown:.1%})")
    elif gate == "YELLOW":
        reasons.append(f"Reduced deployment ({regime} regime)")
    else:
        reasons.append("Normal deployment conditions")
    
    return CapitalDecision(
        base_commitment=base_commitment,
        adjusted_commitment=adjusted,
        max_capital_pct=max_pct,
        mos_multiplier=mos_mult,
        gate=gate,
        regime=regime,
        drawdown=drawdown,
        reason=" | ".join(reasons),
    )


def validate_deal_economics(
    deal: Dict[str, Any],
    macro_meta: Dict[str, Any],
    base_mos: float = 1.0
) -> Dict[str, Any]:
    """
    Validate deal economics against macro conditions.
    
    Args:
        deal: Deal data with irr, mos, target_irr fields
        macro_meta: From DistressedMacroGateAgent.metadata
        base_mos: Baseline margin-of-safety requirement (default 1.0 = 100%)
        
    Returns:
        Validation result with pass/fail and reasons
    """
    gate = macro_meta.get("gate", "GREEN")
    mos_multiplier = macro_meta.get("mos_multiplier", 1.0)
    
    irr = deal.get("irr", 0.0)
    target_irr = deal.get("target_irr", 0.15)
    mos = deal.get("mos", 1.0)
    
    issues = []
    
    required_mos_val = required_mos(base_mos, macro_meta)
    if mos < required_mos_val:
        issues.append(f"MOS {mos:.0%} below required {required_mos_val:.0%}")
    
    if gate == "RED":
        irr_buffer = irr - target_irr
        if irr_buffer < 0.03:
            issues.append(f"IRR buffer {irr_buffer:.1%} below 300bps minimum in RED gate")
    
    if gate == "YELLOW":
        irr_buffer = irr - target_irr
        if irr_buffer < 0.02:
            issues.append(f"IRR buffer {irr_buffer:.1%} below 200bps minimum in YELLOW gate")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "deal_irr": irr,
        "target_irr": target_irr,
        "deal_mos": mos,
        "required_mos": required_mos_val,
        "base_mos": base_mos,
        "mos_multiplier": mos_multiplier,
        "gate": gate,
    }


def get_deployment_summary(
    deals: list,
    macro_meta: Dict[str, Any],
    total_capital: float = 10_000_000.0
) -> Dict[str, Any]:
    """
    Get portfolio-level deployment summary.
    
    Args:
        deals: List of deal dicts with stage, asking_price fields
        macro_meta: From DistressedMacroGateAgent.metadata
        total_capital: Total available capital
        
    Returns:
        Deployment summary with exposure by stage
    """
    STAGE_WEIGHTS = {
        "screened": 0.0,
        "underwritten": 0.3,
        "loi": 0.6,
        "closed": 1.0,
        "dead": 0.0,
    }
    
    gate = macro_meta.get("gate", "GREEN")
    max_pct = macro_meta.get("max_capital_pct", 1.0)
    
    effective_capital = total_capital * max_pct
    
    by_stage = {}
    total_weighted = 0.0
    
    for deal in deals:
        stage = deal.get("stage", "screened")
        value = deal.get("asking_price", 0) or deal.get("offer_price", 0) or 0
        weight = STAGE_WEIGHTS.get(stage, 0.0)
        weighted = value * weight
        
        if stage not in by_stage:
            by_stage[stage] = {"count": 0, "value": 0, "weighted": 0}
        
        by_stage[stage]["count"] += 1
        by_stage[stage]["value"] += value
        by_stage[stage]["weighted"] += weighted
        total_weighted += weighted
    
    utilization = total_weighted / effective_capital if effective_capital > 0 else 0
    
    return {
        "gate": gate,
        "total_capital": total_capital,
        "effective_capital": effective_capital,
        "max_capital_pct": max_pct,
        "by_stage": by_stage,
        "total_weighted_exposure": total_weighted,
        "utilization": utilization,
        "headroom": max(0, effective_capital - total_weighted),
        "deployment_allowed": gate != "RED" or utilization < 0.15,
    }


def apply_macro_gate_to_finding(
    finding: "Finding",
    macro_meta: Dict[str, Any]
) -> None:
    """
    Apply macro gate info to a Finding record.
    
    Args:
        finding: Finding model instance
        macro_meta: From DistressedMacroGateAgent.metadata
    """
    finding.regime = macro_meta.get("regime")
    finding.drawdown = macro_meta.get("portfolio_drawdown")
    finding.capital_gate = macro_meta.get("gate")
