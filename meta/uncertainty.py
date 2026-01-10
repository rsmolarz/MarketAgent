from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func


def agent_uncertainty(agent_name: str, lookback_days: int = 14) -> float:
    """
    Returns mean uncertainty in [0,1] for agent over lookback window.
    If no data, returns 0 (no penalty).
    """
    from models import db, LLMCouncilResult
    
    since = datetime.utcnow() - timedelta(days=lookback_days)
    
    q = (
        db.session.query(func.avg(LLMCouncilResult.uncertainty))
        .filter(LLMCouncilResult.agent_name == agent_name)
        .filter(LLMCouncilResult.created_at >= since)
        .scalar()
    )
    
    return float(q) if q is not None else 0.0


def all_agent_uncertainties(lookback_days: int = 14) -> Dict[str, float]:
    """
    Returns dict of {agent_name: mean_uncertainty} for all agents with council data.
    """
    from models import db, LLMCouncilResult
    
    since = datetime.utcnow() - timedelta(days=lookback_days)
    
    results = (
        db.session.query(
            LLMCouncilResult.agent_name,
            func.avg(LLMCouncilResult.uncertainty)
        )
        .filter(LLMCouncilResult.created_at >= since)
        .group_by(LLMCouncilResult.agent_name)
        .all()
    )
    
    return {r[0]: float(r[1]) if r[1] is not None else 0.0 for r in results}


def uncertainty_from_consensus(consensus: dict) -> float:
    """
    Convert LLM council consensus into uncertainty score.
    Returns uncertainty in [0, 1]:
    - High disagreement + low confidence -> near 1.0
    - Full agreement + high confidence -> near 0.0
    """
    if not consensus:
        return 0.5
    
    if consensus.get("disagreement"):
        return min(1.0, 1.0 - consensus.get("confidence", 0.5))
    return max(0.0, 0.3 - consensus.get("confidence", 0.0))


def compute_controls(state: Dict[str, Any], prev: Dict[str, Any] | None) -> Dict[str, Any]:
    score = float(state.get("score", 0.0))
    label = state.get("label", "calm")
    spike = bool(state.get("spike", False))

    if label == "shock":
        cadence = 3.0
        decay = 0.35
    elif label == "transition":
        cadence = 2.0
        decay = 0.55
    elif label == "risk_off":
        cadence = 1.7
        decay = 0.65
    else:
        cadence = 1.0
        decay = 1.0

    cadence = min(cadence, 1.0 + 2.0 * score)

    if prev:
        prev_decay = float(prev.get("decay_multiplier", 1.0))
        prev_cad = float(prev.get("cadence_multiplier", 1.0))

        if not spike and score < 0.35:
            decay = min(1.0, prev_decay + 0.10)
            cadence = max(1.0, prev_cad - 0.15)

        if spike and score > 0.75:
            decay = max(0.25, min(decay, prev_decay * 0.90))

    return {
        **state,
        "cadence_multiplier": float(cadence),
        "decay_multiplier": float(decay),
        "asof": datetime.utcnow().isoformat()
    }
