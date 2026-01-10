"""
Automated Deal Kill Rules Engine

Kill conditions:
- No IC activity in 14 days -> Auto-PASS
- Underwriting > 30 days -> Flag
- LOI unsigned > 21 days -> PASS
- Missing critical docs -> PASS
- Market regime flips risk-off -> Freeze

Logged for audit trail.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from flask import current_app

logger = logging.getLogger(__name__)


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
