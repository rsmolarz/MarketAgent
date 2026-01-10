"""
Automated Deal Kill Rules Engine

Kill conditions:
- No IC activity in 14 days -> Auto-PASS
- Underwriting > 30 days -> Flag
- LOI unsigned > 21 days -> PASS
- Missing critical docs -> PASS
- Market regime flips risk-off -> Freeze
- Macro gate RED -> Capital preservation mode
- Insufficient IRR buffer in drawdown -> KILL

Regime-aware rules:
+------------------+-------------------+-------------------+-------------------+
| Regime/Drawdown  | Screen->Underwrite| Underwrite->LOI   | LOI->Close        |
+------------------+-------------------+-------------------+-------------------+
| Trend / Calm     | Normal            | Normal            | Normal            |
| Transition       | Extra IC review   | +10% MOS          | Slower close      |
| Volatility       | Only severe       | +20% MOS          | Capital cap       |
| DD >= 10%        | Freeze marginal   | Kill if IRR low   | Board approval    |
| DD >= 20%        | Screen only       | No LOIs           | Emergency only    |
+------------------+-------------------+-------------------+-------------------+

Logged for audit trail.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

from flask import current_app

logger = logging.getLogger(__name__)


class DealStage(Enum):
    SCREENED = "screened"
    UNDERWRITTEN = "underwritten"
    LOI = "loi"
    CLOSED = "closed"
    DEAD = "dead"


@dataclass
class KillDecision:
    action: str  # "ALLOW", "KILL", "HOLD", "ESCALATE"
    reason: str
    required_approval: Optional[str] = None  # "IC", "BOARD", None


STAGE_TIMEOUT_DAYS = {
    "screened": 14,
    "underwritten": 30,
    "loi": 21,
}

HARD_REQUIRED_DOCS = [
    "rent_roll",
    "trailing_12",
    "property_condition_report",
    "title_prelim",
    "insurance_loss_run",
]


def check_timeout_kill(deal, now: Optional[datetime] = None) -> Optional[str]:
    """Check if deal has timed out in current stage."""
    now = now or datetime.utcnow()
    
    if deal.stage not in STAGE_TIMEOUT_DAYS:
        return None
    
    max_days = STAGE_TIMEOUT_DAYS[deal.stage]
    
    last_activity = deal.updated_at or deal.created_at
    if deal.stage_history:
        try:
            last_stage_change = max(
                datetime.fromisoformat(h["at"]) for h in deal.stage_history
            )
            last_activity = max(last_activity, last_stage_change)
        except (KeyError, ValueError):
            pass
    
    days_in_stage = (now - last_activity).days
    
    if days_in_stage > max_days:
        return f"timeout:{deal.stage}:{days_in_stage}d"
    
    return None


def check_ic_inactivity_kill(deal, now: Optional[datetime] = None, inactivity_days: int = 14) -> Optional[str]:
    """Check if no IC activity for too long."""
    now = now or datetime.utcnow()
    
    from models import ICVote
    
    latest_vote = ICVote.query.filter_by(deal_id=deal.id).order_by(
        ICVote.created_at.desc()
    ).first()
    
    if latest_vote is None:
        days_since_creation = (now - deal.created_at).days
        if days_since_creation > inactivity_days:
            return f"no_ic_activity:{days_since_creation}d"
    else:
        days_since_vote = (now - latest_vote.created_at).days
        if days_since_vote > inactivity_days:
            return f"ic_inactive:{days_since_vote}d"
    
    return None


def check_missing_docs_kill(deal, grace_days: int = 10) -> Optional[str]:
    """Check for missing critical documentation."""
    metadata = deal.deal_metadata or {}
    missing_docs = metadata.get("missing_docs", [])
    
    if not missing_docs:
        return None
    
    missing_critical = [d for d in missing_docs if d in HARD_REQUIRED_DOCS]
    
    if missing_critical:
        days_since_creation = (datetime.utcnow() - deal.created_at).days
        if days_since_creation > grace_days:
            return f"missing_docs:{','.join(missing_critical)}"
    
    return None


def check_regime_freeze(deal, current_regime: Optional[str] = None) -> Optional[str]:
    """Check if market regime suggests freezing deals."""
    if current_regime is None:
        try:
            from scheduler import _cached_regime
            current_regime = _cached_regime.get("label", "unknown")
        except Exception:
            current_regime = "unknown"
    
    if current_regime in ("risk_off", "crisis"):
        if deal.stage in ("screened", "underwritten"):
            return f"regime_freeze:{current_regime}"
    
    return None


def check_regime_normalization_kill(deal, kill_eval: Optional[Dict] = None) -> Optional[str]:
    """Check if distress regime is normalizing (compression of discount)."""
    if not kill_eval:
        return None
    
    if kill_eval.get("kill") is True:
        if deal.stage in ("loi", "closed"):
            return None
        
        reasons = kill_eval.get("reasons", [])
        return f"regime_normalized:{';'.join(reasons[:2])}" if reasons else "regime_normalized"
    
    return None


def evaluate_deal_kill_suite(deal, kill_eval: Optional[Dict] = None) -> Dict:
    """
    Run all kill rules against a deal.
    
    Returns:
        {
            "kill": bool,
            "freeze": bool,
            "reasons": [str],
            "action": "pass" | "freeze" | "flag" | None
        }
    """
    reasons = []
    freeze = False
    
    timeout = check_timeout_kill(deal)
    if timeout:
        if "underwritten" in timeout and deal.stage == "underwritten":
            reasons.append(f"FLAG: {timeout}")
        else:
            reasons.append(timeout)
    
    ic_inactivity = check_ic_inactivity_kill(deal)
    if ic_inactivity:
        reasons.append(ic_inactivity)
    
    missing_docs = check_missing_docs_kill(deal)
    if missing_docs:
        reasons.append(missing_docs)
    
    regime = check_regime_freeze(deal)
    if regime:
        freeze = True
        reasons.append(regime)
    
    if kill_eval:
        norm_kill = check_regime_normalization_kill(deal, kill_eval)
        if norm_kill:
            reasons.append(norm_kill)
    
    kill = any(not r.startswith("FLAG:") and not r.startswith("regime_freeze") for r in reasons)
    
    action = None
    if freeze:
        action = "freeze"
    elif kill:
        action = "pass"
    elif any(r.startswith("FLAG:") for r in reasons):
        action = "flag"
    
    return {
        "kill": kill,
        "freeze": freeze,
        "reasons": reasons,
        "action": action,
    }


def run_deal_kill_sweep():
    """
    Cron-safe sweep of all active deals to apply kill rules.
    Returns summary of actions taken.
    """
    from models import db, DistressedDeal
    
    active_deals = DistressedDeal.query.filter(
        DistressedDeal.stage.in_(["screened", "underwritten", "loi"])
    ).all()
    
    summary = {
        "scanned": len(active_deals),
        "passed": 0,
        "frozen": 0,
        "flagged": 0,
        "details": [],
    }
    
    for deal in active_deals:
        result = evaluate_deal_kill_suite(deal)
        
        if result["action"] == "pass":
            old_stage = deal.stage
            deal.stage = "dead"
            deal.add_stage_history(old_stage, "dead", notes=f"Auto-killed: {', '.join(result['reasons'])}")
            
            metadata = deal.deal_metadata or {}
            metadata["kill_reason"] = result["reasons"]
            metadata["kill_at"] = datetime.utcnow().isoformat()
            deal.deal_metadata = metadata
            
            summary["passed"] += 1
            summary["details"].append({
                "deal_id": deal.id,
                "address": deal.property_address,
                "action": "pass",
                "reasons": result["reasons"],
            })
            logger.info(f"Auto-killed deal {deal.id} ({deal.property_address}): {result['reasons']}")
        
        elif result["action"] == "freeze":
            metadata = deal.deal_metadata or {}
            metadata["frozen"] = True
            metadata["freeze_reason"] = result["reasons"]
            metadata["freeze_at"] = datetime.utcnow().isoformat()
            deal.deal_metadata = metadata
            
            summary["frozen"] += 1
            summary["details"].append({
                "deal_id": deal.id,
                "address": deal.property_address,
                "action": "freeze",
                "reasons": result["reasons"],
            })
            logger.info(f"Froze deal {deal.id} ({deal.property_address}): {result['reasons']}")
        
        elif result["action"] == "flag":
            metadata = deal.deal_metadata or {}
            metadata["flagged"] = True
            metadata["flag_reasons"] = result["reasons"]
            deal.deal_metadata = metadata
            
            summary["flagged"] += 1
            summary["details"].append({
                "deal_id": deal.id,
                "address": deal.property_address,
                "action": "flag",
                "reasons": result["reasons"],
            })
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Failed to commit kill sweep: {e}")
        raise
    
    return summary


def macro_gate_kill_rules(deal: Dict, macro_meta: Dict) -> KillDecision:
    """
    Kill rule engine using DistressedMacroGateAgent output.
    
    deal: dict with fields {stage, irr, target_irr, mos, docs_complete, days_in_stage}
    macro_meta: from DistressedMacroGateAgent.metadata
    """
    gate = macro_meta.get("gate", "GREEN")
    drawdown = macro_meta.get("portfolio_drawdown", 0.0)
    regime = macro_meta.get("regime", "unknown")
    mos_multiplier = macro_meta.get("mos_multiplier", 1.0)
    
    stage = deal.get("stage", "screened")
    irr = deal.get("irr", 0.0)
    target_irr = deal.get("target_irr", 0.15)
    mos = deal.get("mos", 1.0)
    docs_complete = deal.get("docs_complete", False)
    days_in_stage = deal.get("days_in_stage", 0)
    
    if gate == "RED":
        if stage == "loi":
            return KillDecision("KILL", "Macro RED - no new commitments allowed")
        if irr < target_irr + 0.03:
            return KillDecision("KILL", "Insufficient IRR buffer in drawdown (need +300bps)")
    
    if days_in_stage > 45 and not docs_complete:
        return KillDecision("KILL", "Stalled deal - 45+ days without complete docs")
    
    if drawdown <= -0.20:
        if stage in ("underwritten", "loi"):
            return KillDecision("HOLD", "Severe drawdown - no new LOIs", required_approval="BOARD")
    
    if drawdown <= -0.10:
        if stage == "loi":
            return KillDecision("ESCALATE", "Drawdown band - requires board approval", required_approval="BOARD")
        if irr < target_irr + 0.03:
            return KillDecision("HOLD", "Marginal IRR in drawdown - freeze until conditions improve")
    
    if regime == "volatility":
        if stage == "screened" and mos < 1.20:
            return KillDecision("HOLD", "Volatility regime - only severe distress advances")
        if stage == "underwritten":
            required_mos = 1.20
            if mos < required_mos:
                return KillDecision("HOLD", f"Volatility regime - need MOS >= {required_mos}")
    
    if regime == "transition":
        if stage == "screened":
            return KillDecision("ESCALATE", "Transition regime - extra IC review required", required_approval="IC")
    
    return KillDecision("ALLOW", "Deal passes kill rules")


def stage_progression_allowed(
    current_stage: str,
    target_stage: str,
    deal: Dict,
    macro_meta: Dict
) -> KillDecision:
    """
    Check if a deal can progress from current_stage to target_stage.
    """
    gate = macro_meta.get("gate", "GREEN")
    drawdown = macro_meta.get("portfolio_drawdown", 0.0)
    regime = macro_meta.get("regime", "unknown")
    mos_multiplier = macro_meta.get("mos_multiplier", 1.0)
    
    if current_stage == "screened" and target_stage == "underwritten":
        if drawdown <= -0.20:
            return KillDecision("KILL", "Severe drawdown - screen only, no underwriting")
        if gate == "RED":
            if deal.get("mos", 1.0) < 1.30:
                return KillDecision("HOLD", "RED gate - only exceptional distress advances")
        return KillDecision("ALLOW", "Progression allowed")
    
    if current_stage == "underwritten" and target_stage == "loi":
        if drawdown <= -0.20:
            return KillDecision("KILL", "Severe drawdown - no LOIs allowed")
        if drawdown <= -0.10:
            irr_buffer = deal.get("irr", 0.0) - deal.get("target_irr", 0.15)
            if irr_buffer < 0.03:
                return KillDecision("KILL", "Insufficient IRR buffer for LOI in drawdown")
        
        required_mos = deal.get("base_mos", 1.0) * mos_multiplier
        if deal.get("mos", 1.0) < required_mos:
            return KillDecision("HOLD", f"Insufficient MOS - need {required_mos:.0%}")
        
        return KillDecision("ALLOW", "Progression allowed")
    
    if current_stage == "loi" and target_stage == "closed":
        if drawdown <= -0.20:
            return KillDecision("ESCALATE", "Emergency only - board approval required", required_approval="BOARD")
        if drawdown <= -0.10:
            return KillDecision("ESCALATE", "Drawdown band - board approval required", required_approval="BOARD")
        if regime == "transition":
            return KillDecision("ESCALATE", "Transition regime - slower close, IC approval", required_approval="IC")
        return KillDecision("ALLOW", "Progression allowed")
    
    return KillDecision("ALLOW", "Progression allowed")


def get_stage_timeout_days_macro(stage: str, regime: str, gate: str) -> int:
    """
    Get maximum days allowed in a stage before kill rule triggers.
    Adjusted for regime and gate conditions.
    """
    base_timeouts = {
        "screened": 14,
        "underwritten": 30,
        "loi": 21,
    }
    
    base = base_timeouts.get(stage, 30)
    
    if gate == "RED":
        return int(base * 0.7)
    if regime == "volatility":
        return int(base * 0.8)
    if regime == "transition":
        return int(base * 0.9)
    
    return base


def evaluate_deal_health_with_macro(deal: Dict, macro_meta: Dict) -> Dict:
    """
    Comprehensive deal health check with macro gate integration.
    """
    kill_decision = macro_gate_kill_rules(deal, macro_meta)
    
    stage = deal.get("stage", "screened")
    regime = macro_meta.get("regime", "unknown")
    gate = macro_meta.get("gate", "GREEN")
    timeout = get_stage_timeout_days_macro(stage, regime, gate)
    days_remaining = timeout - deal.get("days_in_stage", 0)
    
    health_score = 1.0
    warnings = []
    
    if kill_decision.action == "KILL":
        health_score = 0.0
    elif kill_decision.action == "HOLD":
        health_score = 0.3
    elif kill_decision.action == "ESCALATE":
        health_score = 0.6
    
    if days_remaining < 7:
        health_score *= 0.7
        warnings.append(f"Stage timeout in {days_remaining} days")
    
    if not deal.get("docs_complete", False):
        health_score *= 0.8
        warnings.append("Docs incomplete")
    
    irr_buffer = deal.get("irr", 0.0) - deal.get("target_irr", 0.15)
    if irr_buffer < 0.02:
        health_score *= 0.8
        warnings.append("Thin IRR buffer")
    
    return {
        "health_score": round(health_score, 2),
        "kill_decision": kill_decision.action,
        "kill_reason": kill_decision.reason,
        "required_approval": kill_decision.required_approval,
        "days_remaining_in_stage": days_remaining,
        "stage_timeout_days": timeout,
        "gate": gate,
        "regime": regime,
        "warnings": warnings,
    }


def get_deal_exposure_by_stage() -> Dict:
    """
    Get portfolio-level exposure by deal stage.
    
    Exposure weights:
    - SCREENED: 0.0 (no capital at risk)
    - UNDERWRITING: 0.3 (DD costs, legal prep)
    - LOI: 0.6 (earnest money, deal room)
    - CLOSED: 1.0 (full investment)
    """
    from models import db, DistressedDeal
    from sqlalchemy import func
    
    EXPOSURE_WEIGHTS = {
        "screened": 0.0,
        "underwritten": 0.3,
        "loi": 0.6,
        "closed": 1.0,
        "dead": 0.0,
    }
    
    stage_counts = db.session.query(
        DistressedDeal.stage,
        func.count(DistressedDeal.id).label("count"),
        func.sum(DistressedDeal.asking_price).label("total_value"),
    ).group_by(DistressedDeal.stage).all()
    
    result = {
        "stages": {},
        "total_deals": 0,
        "total_value": 0,
        "weighted_exposure": 0,
    }
    
    for stage, count, total_value in stage_counts:
        weight = EXPOSURE_WEIGHTS.get(stage, 0.0)
        stage_value = total_value or 0
        weighted = stage_value * weight
        
        result["stages"][stage] = {
            "count": count,
            "value": stage_value,
            "weight": weight,
            "weighted_exposure": weighted,
        }
        result["total_deals"] += count
        result["total_value"] += stage_value
        result["weighted_exposure"] += weighted
    
    return result
