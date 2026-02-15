"""
Dynamic risk budget allocation across asset classes.

Combines regime-based allocation templates with conviction signals
from sub-orchestrators and risk constraints to produce final
capital allocation targets.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.state_schema import AssetClass
from shared.signal_schema import SignalBundle, PortfolioSignal

logger = logging.getLogger(__name__)


@dataclass
class AllocationTarget:
    """Target allocation for a single asset class."""
    asset_class: str
    target_pct: float
    min_pct: float = 0.0
    max_pct: float = 1.0
    current_pct: float = 0.0
    regime_base_pct: float = 0.0
    conviction_adjustment: float = 0.0
    risk_adjustment: float = 0.0

    @property
    def delta(self) -> float:
        return self.target_pct - self.current_pct


@dataclass
class AllocationPlan:
    """Complete portfolio allocation plan."""
    allocations: List[AllocationTarget]
    regime: str = "unknown"
    total_allocated: float = 0.0
    cash_reserve: float = 0.0
    rebalance_needed: bool = False
    rebalance_urgency: str = "none"  # "none", "low", "medium", "high"
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allocations": {a.asset_class: a.target_pct for a in self.allocations},
            "regime": self.regime,
            "total_allocated": self.total_allocated,
            "cash_reserve": self.cash_reserve,
            "rebalance_needed": self.rebalance_needed,
            "rebalance_urgency": self.rebalance_urgency,
            "details": [
                {
                    "asset_class": a.asset_class,
                    "target_pct": a.target_pct,
                    "current_pct": a.current_pct,
                    "delta": a.delta,
                    "regime_base": a.regime_base_pct,
                    "conviction_adj": a.conviction_adjustment,
                    "risk_adj": a.risk_adjustment,
                }
                for a in self.allocations
            ],
        }


class CapitalAllocator:
    """
    Dynamic capital allocation across asset classes.

    Process:
    1. Start with regime-based allocation template (from regime detector).
    2. Adjust based on conviction signals from each sub-orchestrator.
    3. Apply risk constraints (max exposure, correlation limits).
    4. Ensure total allocation <= 1.0 (remainder = cash).
    5. Determine rebalancing urgency based on drift from targets.
    """

    DEFAULT_CONSTRAINTS = {
        "bonds": {"min": 0.05, "max": 0.60},
        "crypto": {"min": 0.00, "max": 0.35},
        "real_estate": {"min": 0.05, "max": 0.45},
        "distressed": {"min": 0.05, "max": 0.65},
    }

    REBALANCE_THRESHOLDS = {
        "low": 0.03,     # 3% drift -> low urgency
        "medium": 0.07,  # 7% drift -> medium urgency
        "high": 0.12,    # 12% drift -> high urgency
    }

    def __init__(
        self,
        constraints: Optional[Dict[str, Dict[str, float]]] = None,
        conviction_weight: float = 0.3,
        max_total_allocation: float = 0.95,
    ):
        self.constraints = constraints or dict(self.DEFAULT_CONSTRAINTS)
        self.conviction_weight = conviction_weight
        self.max_total_allocation = max_total_allocation
        self._current_allocations: Dict[str, float] = {}
        self._history: List[AllocationPlan] = []

    def set_current_allocations(self, allocations: Dict[str, float]) -> None:
        self._current_allocations = allocations

    def allocate(
        self,
        regime_allocations: Dict[str, float],
        signal_bundles: Optional[List[SignalBundle]] = None,
        risk_breaches: Optional[List[str]] = None,
        regime: str = "unknown",
    ) -> AllocationPlan:
        """
        Compute target allocations.

        Args:
            regime_allocations: Base allocations from regime detector.
            signal_bundles: Conviction signals from sub-orchestrators.
            risk_breaches: List of breached risk limits.
            regime: Current regime name.
        """
        targets = []

        # Step 1: Start with regime base allocations
        raw_allocations = dict(regime_allocations)

        # Step 2: Adjust for conviction signals
        conviction_adjustments = {}
        if signal_bundles:
            for bundle in signal_bundles:
                ac = bundle.asset_class.value if hasattr(bundle.asset_class, 'value') else str(bundle.asset_class)
                avg_conv = bundle.avg_conviction
                # Scale conviction to allocation adjustment
                adjustment = avg_conv * self.conviction_weight
                conviction_adjustments[ac] = adjustment
                raw_allocations[ac] = raw_allocations.get(ac, 0) + adjustment

        # Step 3: Apply risk constraints
        risk_adjustments = {}
        if risk_breaches:
            for breach in risk_breaches:
                if "crypto" in breach.lower():
                    raw_allocations["crypto"] = min(
                        raw_allocations.get("crypto", 0),
                        self.constraints.get("crypto", {}).get("max", 0.35) * 0.5,
                    )
                    risk_adjustments["crypto"] = -0.05

        # Step 4: Enforce min/max constraints
        for ac, alloc in raw_allocations.items():
            constraint = self.constraints.get(ac, {"min": 0.0, "max": 1.0})
            raw_allocations[ac] = max(constraint["min"], min(constraint["max"], alloc))

        # Step 5: Normalize to max_total_allocation
        total = sum(raw_allocations.values())
        if total > self.max_total_allocation:
            scale = self.max_total_allocation / total
            raw_allocations = {ac: alloc * scale for ac, alloc in raw_allocations.items()}
            total = sum(raw_allocations.values())

        # Ensure non-negative
        raw_allocations = {ac: max(0, alloc) for ac, alloc in raw_allocations.items()}
        total = sum(raw_allocations.values())

        # Build allocation targets
        max_drift = 0.0
        for ac, target_pct in raw_allocations.items():
            current = self._current_allocations.get(ac, 0)
            drift = abs(target_pct - current)
            max_drift = max(max_drift, drift)

            targets.append(AllocationTarget(
                asset_class=ac,
                target_pct=round(target_pct, 4),
                min_pct=self.constraints.get(ac, {}).get("min", 0),
                max_pct=self.constraints.get(ac, {}).get("max", 1),
                current_pct=current,
                regime_base_pct=regime_allocations.get(ac, 0),
                conviction_adjustment=conviction_adjustments.get(ac, 0),
                risk_adjustment=risk_adjustments.get(ac, 0),
            ))

        # Determine rebalancing urgency
        if max_drift >= self.REBALANCE_THRESHOLDS["high"]:
            urgency = "high"
        elif max_drift >= self.REBALANCE_THRESHOLDS["medium"]:
            urgency = "medium"
        elif max_drift >= self.REBALANCE_THRESHOLDS["low"]:
            urgency = "low"
        else:
            urgency = "none"

        plan = AllocationPlan(
            allocations=targets,
            regime=regime,
            total_allocated=round(total, 4),
            cash_reserve=round(1.0 - total, 4),
            rebalance_needed=urgency != "none",
            rebalance_urgency=urgency,
        )

        self._history.append(plan)
        logger.info(
            f"Allocation plan: {', '.join(f'{a.asset_class}={a.target_pct:.1%}' for a in targets)} "
            f"cash={plan.cash_reserve:.1%} urgency={urgency}"
        )
        return plan

    def get_history(self, n: int = 10) -> List[AllocationPlan]:
        return self._history[-n:]
