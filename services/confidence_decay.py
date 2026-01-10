from datetime import datetime, timezone


def parse_iso_z(s: str) -> datetime:
    """
    Parse ISO format datetime string, handling Z suffix.
    """
    if not s:
        return datetime.now(timezone.utc)
    
    if isinstance(s, datetime):
        if s.tzinfo is None:
            return s.replace(tzinfo=timezone.utc)
        return s
    
    s = str(s)
    if s.endswith("Z"):
        s = s[:-1]
    
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)


def decay(confidence: float, created_at: str, half_life_hours: float = 48.0) -> float:
    """
    Apply exponential decay to confidence score based on age.
    After half_life_hours, confidence halves.
    
    Args:
        confidence: Initial confidence score (0.0 to 1.0)
        created_at: ISO format datetime string when vote was created
        half_life_hours: Time in hours for confidence to halve (default 48h)
    
    Returns:
        Decayed confidence score
    """
    c0 = max(0.0, min(1.0, float(confidence or 0)))
    t0 = parse_iso_z(created_at)
    now = datetime.now(timezone.utc)
    
    hours = max(0.0, (now - t0).total_seconds() / 3600.0)
    factor = 0.5 ** (hours / half_life_hours)
    
    return round(c0 * factor, 4)


def is_stale(confidence: float, created_at: str, threshold: float = 0.55, half_life_hours: float = 48.0) -> bool:
    """
    Check if a vote's effective confidence has decayed below threshold.
    """
    effective = decay(confidence, created_at, half_life_hours)
    return effective < threshold


def hours_until_stale(confidence: float, created_at: str, threshold: float = 0.55, half_life_hours: float = 48.0) -> float:
    """
    Calculate hours until vote becomes stale (effective confidence < threshold).
    Returns 0 if already stale, or float('inf') if will never be stale.
    """
    if confidence <= 0:
        return 0.0
    if threshold <= 0:
        return float('inf')
    
    effective = decay(confidence, created_at, half_life_hours)
    if effective < threshold:
        return 0.0
    
    import math
    ratio_needed = threshold / confidence
    if ratio_needed <= 0 or ratio_needed >= 1:
        return float('inf')
    
    hours_to_threshold = half_life_hours * math.log2(1 / ratio_needed)
    
    t0 = parse_iso_z(created_at)
    now = datetime.now(timezone.utc)
    hours_elapsed = (now - t0).total_seconds() / 3600.0
    
    remaining = hours_to_threshold - hours_elapsed
    return max(0.0, remaining)
