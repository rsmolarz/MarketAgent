"""
Uncertainty Decay Curve

Capital fades back in gradually after uncertainty clears.
Avoids binary on/off behavior with exponential recovery.

Behavior:
| Time after uncertainty | Exposure |
|------------------------|----------|
| During spike           | 60%      |
| +30 min                | ~80%     |
| +60 min                | ~90%     |
| Stable                 | 100%     |

No cliff risk. No whipsaw.
"""

from datetime import datetime
from typing import Optional
from meta.uncertainty_state import UncertaintyState

DECAY_HALF_LIFE_MIN = 30  # capital recovers halfway every 30 min
MIN_MULTIPLIER = 0.6      # worst-case exposure during uncertainty

_last_clear_time: Optional[datetime] = None


def uncertainty_multiplier(now: Optional[datetime] = None) -> float:
    """
    Compute exposure multiplier based on uncertainty state.
    
    Returns:
        Float between MIN_MULTIPLIER and 1.0
        - MIN_MULTIPLIER (0.6) during active uncertainty
        - Gradually recovers to 1.0 after uncertainty clears
    """
    global _last_clear_time
    
    if now is None:
        now = datetime.utcnow()

    if UncertaintyState.active:
        _last_clear_time = None
        return MIN_MULTIPLIER

    if UncertaintyState.last_update is None:
        return 1.0

    if _last_clear_time is None:
        _last_clear_time = UncertaintyState.last_update

    dt_min = (now - _last_clear_time).total_seconds() / 60
    
    if dt_min <= 0:
        return MIN_MULTIPLIER
    
    recovery = 1 - (0.5 ** (dt_min / DECAY_HALF_LIFE_MIN))

    return min(1.0, MIN_MULTIPLIER + recovery * (1.0 - MIN_MULTIPLIER))


def get_decay_status(now: Optional[datetime] = None) -> dict:
    """Get current decay status for logging/API."""
    if now is None:
        now = datetime.utcnow()
    
    multiplier = uncertainty_multiplier(now)
    
    return {
        "multiplier": round(multiplier, 4),
        "uncertainty_active": UncertaintyState.active,
        "min_multiplier": MIN_MULTIPLIER,
        "half_life_min": DECAY_HALF_LIFE_MIN,
        "last_clear_time": _last_clear_time.isoformat() if _last_clear_time else None,
        "recovery_pct": round((multiplier - MIN_MULTIPLIER) / (1.0 - MIN_MULTIPLIER) * 100, 1) if multiplier > MIN_MULTIPLIER else 0,
    }
