"""
Regime Transition Early-Warning Detector
Detects uncertainty spikes BEFORE regime flips occur.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def detect_transition(
    window_minutes: int = 60,
    spike_threshold: float = 0.5,
    critical_level: float = 0.67
) -> Dict[str, Any]:
    """
    Detect if a regime transition is imminent based on uncertainty spikes.
    
    Analyzes recent UncertaintyEvents to identify:
    1. Large delta in uncertainty level over the window
    2. Current uncertainty at critical levels
    3. Sustained elevated uncertainty
    
    Args:
        window_minutes: How far back to look for uncertainty events
        spike_threshold: Delta threshold for flagging transition
        critical_level: Absolute level triggering transition warning
    
    Returns:
        {
            "ok": bool,
            "transition": bool,
            "delta": float,
            "current": float,
            "n": int,
            "reason": str,
            "severity": str  # "low", "medium", "high"
        }
    """
    from models import UncertaintyEvent
    
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        evs = (
            UncertaintyEvent.query
            .filter(UncertaintyEvent.timestamp >= cutoff)
            .order_by(UncertaintyEvent.timestamp.asc())
            .all()
        )
        
        if len(evs) < 3:
            return {
                "ok": True,
                "transition": False,
                "reason": "insufficient_events",
                "delta": 0.0,
                "current": 0.0,
                "n": len(evs),
                "severity": "low"
            }
        
        levels = [float(e.score or 0.0) for e in evs]
        current = levels[-1]
        min_level = min(levels)
        max_level = max(levels)
        delta = max_level - min_level
        
        avg_early = sum(levels[:len(levels)//2]) / max(1, len(levels)//2)
        avg_late = sum(levels[len(levels)//2:]) / max(1, len(levels) - len(levels)//2)
        trend = avg_late - avg_early
        
        reasons = []
        severity = "low"
        transition = False
        
        if delta >= spike_threshold:
            transition = True
            reasons.append(f"delta_spike({delta:.2f}>={spike_threshold})")
            severity = "medium"
        
        if current >= critical_level:
            transition = True
            reasons.append(f"critical_level({current:.2f}>={critical_level})")
            severity = "high"
        
        if trend > 0.3 and current > 0.5:
            transition = True
            reasons.append(f"rising_trend({trend:.2f})")
            if severity == "low":
                severity = "medium"
        
        spike_count = sum(1 for e in evs if e.spike)
        if spike_count >= 2:
            transition = True
            reasons.append(f"multiple_spikes({spike_count})")
            severity = "high"
        
        return {
            "ok": True,
            "transition": transition,
            "delta": float(delta),
            "current": float(current),
            "trend": float(trend),
            "n": len(levels),
            "reason": ", ".join(reasons) if reasons else "stable",
            "severity": severity,
            "spike_count": spike_count
        }
        
    except Exception as e:
        logger.error(f"Error detecting regime transition: {e}")
        return {
            "ok": False,
            "transition": False,
            "reason": f"error: {str(e)}",
            "delta": 0.0,
            "current": 0.0,
            "n": 0,
            "severity": "low"
        }


def get_transition_history(hours: int = 24) -> List[Dict[str, Any]]:
    """
    Get recent transition warnings for analysis.
    """
    from models import UncertaintyEvent
    
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        evs = (
            UncertaintyEvent.query
            .filter(UncertaintyEvent.timestamp >= cutoff)
            .order_by(UncertaintyEvent.timestamp.desc())
            .limit(100)
            .all()
        )
        
        return [e.to_dict() for e in evs]
        
    except Exception as e:
        logger.error(f"Error getting transition history: {e}")
        return []
