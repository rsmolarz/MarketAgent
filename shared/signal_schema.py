"""
Standardized cross-asset signal schema.

Defines the Signal object used for communication between tiers in the
three-tier hierarchical architecture. Every agent output is wrapped in
a Signal before being passed to the next tier, ensuring uniform validation
and auditing across all asset classes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from shared.state_schema import AssetClass, Direction


class Signal(BaseModel):
    """
    Standardized signal object for cross-tier communication.

    All sub-orchestrators emit Signals to the portfolio orchestrator.
    Contains conviction scores, position sizing, risk metrics, confidence
    intervals, and data freshness indicators.
    """
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str
    source_tier: int = Field(ge=1, le=3, description="1=portfolio, 2=sub-orch, 3=agent")
    asset_class: AssetClass
    ticker: str
    direction: Direction
    conviction: float = Field(ge=-1.0, le=1.0, description="-1.0 strong bear to +1.0 strong bull")
    position_size_pct: float = Field(ge=0.0, le=1.0, description="Recommended as fraction of capital")
    risk_metrics: Dict[str, float] = Field(default_factory=dict)
    confidence_interval_low: float = 0.0
    confidence_interval_high: float = 0.0
    data_freshness_seconds: float = Field(ge=0, description="Age of underlying data in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("conviction")
    @classmethod
    def validate_conviction(cls, v: float) -> float:
        if not -1.0 <= v <= 1.0:
            raise ValueError(f"Conviction must be between -1.0 and 1.0, got {v}")
        return round(v, 6)

    @field_validator("position_size_pct")
    @classmethod
    def validate_position_size(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Position size must be between 0.0 and 1.0, got {v}")
        return round(v, 6)

    def is_stale(self, max_age_seconds: float = 300.0) -> bool:
        """Check if the signal data is stale."""
        return self.data_freshness_seconds > max_age_seconds

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class SignalBundle(BaseModel):
    """
    Collection of signals from a sub-orchestrator, representing a complete
    analysis cycle for one asset class.
    """
    bundle_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_class: AssetClass
    signals: List[Signal] = Field(default_factory=list)
    regime: str = "unknown"
    regime_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    is_degraded: bool = False
    degraded_agents: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def avg_conviction(self) -> float:
        if not self.signals:
            return 0.0
        return sum(s.conviction for s in self.signals) / len(self.signals)

    @property
    def max_conviction(self) -> float:
        if not self.signals:
            return 0.0
        return max(s.conviction for s in self.signals, key=lambda s: abs(s.conviction))

    def get_signals_for_ticker(self, ticker: str) -> List[Signal]:
        return [s for s in self.signals if s.ticker == ticker]


class PortfolioSignal(BaseModel):
    """
    Aggregated signal at the portfolio level, combining outputs from
    all sub-orchestrators into a unified allocation recommendation.
    """
    portfolio_signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bundles: List[SignalBundle] = Field(default_factory=list)
    regime: str = "unknown"
    cross_asset_correlations: Dict[str, float] = Field(default_factory=dict)
    total_risk_budget: float = Field(ge=0.0, le=1.0, default=1.0)
    allocations: Dict[str, float] = Field(
        default_factory=dict,
        description="Asset class -> allocation fraction"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("allocations")
    @classmethod
    def validate_allocations(cls, v: Dict[str, float]) -> Dict[str, float]:
        if v:
            total = sum(v.values())
            if total > 1.01:  # small tolerance for float rounding
                raise ValueError(f"Allocations sum to {total}, must be <= 1.0")
        return v
