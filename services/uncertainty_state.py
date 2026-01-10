import logging

logger = logging.getLogger(__name__)


def current_uncertainty_multiplier() -> float:
    """
    Get current uncertainty multiplier for capital allocation and cadence modulation.
    
    Returns:
        Multiplier between 0.6 (high uncertainty) and 1.0 (normal)
    """
    try:
        from models import UncertaintyEvent
        e = UncertaintyEvent.query.order_by(UncertaintyEvent.timestamp.desc()).first()
        if not e:
            return 1.0
        if e.spike:
            return 0.6
        if e.score >= 0.6:
            return 0.8
        return 1.0
    except Exception as ex:
        logger.debug(f"Could not get uncertainty multiplier: {ex}")
        return 1.0


def get_uncertainty_status() -> dict:
    """
    Get full uncertainty status for dashboard/API.
    
    Returns:
        {"score": float, "label": str, "spike": bool, "multiplier": float}
    """
    try:
        from models import UncertaintyEvent
        e = UncertaintyEvent.query.order_by(UncertaintyEvent.timestamp.desc()).first()
        if not e:
            return {"score": 0.0, "label": "calm", "spike": False, "multiplier": 1.0}
        
        mult = 0.6 if e.spike else (0.8 if e.score >= 0.6 else 1.0)
        return {
            "score": e.score,
            "label": e.label,
            "spike": e.spike,
            "multiplier": mult
        }
    except Exception as ex:
        logger.debug(f"Could not get uncertainty status: {ex}")
        return {"score": 0.0, "label": "calm", "spike": False, "multiplier": 1.0}
