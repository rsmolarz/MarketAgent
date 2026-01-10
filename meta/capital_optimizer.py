from typing import Dict
import logging

logger = logging.getLogger(__name__)


def normalize(w: Dict[str, float]) -> Dict[str, float]:
    """Normalize weights to sum to 1.0."""
    s = sum(max(0.0, v) for v in w.values())
    if s <= 0:
        return {k: 0.0 for k in w}
    return {k: max(0.0, v) / s for k, v in w.items()}


def capital_allocate(
    base_weights: Dict[str, float],
    regime_weights: Dict[str, float],
    allocator_scores: Dict[str, float] | None = None,
    uncertainty_mult: float = 1.0,
    drawdown_mult: float = 1.0,
    total_notional: float = 100000.0,
    min_ticket: float = 0.0
) -> Dict[str, float]:
    """
    Convert weights into notional dollar allocations.
    
    Args:
        base_weights: agent_schedule.json weights
        regime_weights: current regime rotation weights
        allocator_scores: optional allocator scores per agent
        uncertainty_mult: uncertainty multiplier (0.6 on spikes, else 1.0)
        drawdown_mult: drawdown governor multiplier (0-1)
        total_notional: total portfolio notional
        min_ticket: minimum ticket size (drop allocations below this)
    
    Returns:
        {agent: notional_usd}
    """
    allocator_scores = allocator_scores or {}

    combined = {}
    for a, bw in base_weights.items():
        rw = float(regime_weights.get(a, 0.0))
        score_boost = 1.0 + max(-0.5, min(0.5, float(allocator_scores.get(a, 0.0))))
        combined[a] = float(bw) * rw * score_boost

    combined = {a: v * uncertainty_mult * drawdown_mult for a, v in combined.items()}
    combined = normalize(combined)

    notional = {a: combined[a] * total_notional for a in combined}
    
    if min_ticket > 0:
        notional = {a: (v if v >= min_ticket else 0.0) for a, v in notional.items()}
        notional = normalize(notional)
        notional = {a: notional[a] * total_notional for a in notional}

    return notional


def get_regime_allocation_summary(notional_map: Dict[str, float], top_n: int = 5) -> str:
    """Get a summary of top allocations."""
    sorted_allocs = sorted(notional_map.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return ", ".join([f"{a}: ${v:.0f}" for a, v in sorted_allocs])
