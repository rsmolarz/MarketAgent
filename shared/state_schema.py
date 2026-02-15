"""
State schemas for the LangGraph-based multi-agent orchestration system.

Defines typed state dictionaries and Pydantic models for all agent I/O,
ensuring type safety and validation across the three-tier hierarchy.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AssetClass(str, enum.Enum):
    BONDS = "bonds"
    CRYPTO = "crypto"
    REAL_ESTATE = "real_estate"
    DISTRESSED = "distressed"


class MarketRegime(str, enum.Enum):
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    RISING_GROWTH_RISING_INFLATION = "rising_growth_rising_inflation"
    RISING_GROWTH_FALLING_INFLATION = "rising_growth_falling_inflation"
    FALLING_GROWTH_RISING_INFLATION = "falling_growth_rising_inflation"
    FALLING_GROWTH_FALLING_INFLATION = "falling_growth_falling_inflation"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"


class EvaluationStatus(str, enum.Enum):
    PENDING = "pending"
    AGENTS_RUNNING = "agents_running"
    BARRIER_WAIT = "barrier_wait"
    ACTION_NEEDED = "action_needed"
    DEGRADED = "degraded"
    COMPLETED = "completed"
    FAILED = "failed"


class Direction(str, enum.Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Pydantic models for agent outputs
# ---------------------------------------------------------------------------

class TAScore(BaseModel):
    """Technical analysis numerical score output."""
    agent_name: str
    indicator: str
    score: float = Field(ge=0, le=100, description="TA score 0-100")
    confidence: float = Field(ge=0.0, le=1.0)
    signals: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LLMOpinion(BaseModel):
    """LLM council agent directional opinion."""
    agent_name: str
    model: str = ""
    direction: Direction
    reasoning: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConvictionScore(BaseModel):
    """Final conviction score combining TA and LLM tracks."""
    ticker: str
    ta_weighted_score: float = Field(ge=0, le=100)
    llm_consensus: Direction
    llm_agreement_ratio: float = Field(ge=0.0, le=1.0)
    combined_score: float = Field(ge=-1.0, le=1.0, description="-1 strong bear to +1 strong bull")
    ta_weight: float = Field(default=0.6)
    llm_weight: float = Field(default=0.4)
    participating_agents: List[str] = Field(default_factory=list)
    missing_agents: List[str] = Field(default_factory=list)
    is_degraded: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CodeGuardianReport(BaseModel):
    """Validation report from the code guardian."""
    passed: bool
    layer1_results: Dict[str, Any] = Field(default_factory=dict, description="Rule-based checks")
    layer2_results: Dict[str, Any] = Field(default_factory=dict, description="LLM semantic checks")
    layer3_results: Dict[str, Any] = Field(default_factory=dict, description="Statistical drift")
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    quarantined_outputs: List[str] = Field(default_factory=list)
    manual_review_required: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DealAnalysis(BaseModel):
    """Distressed debt deal analysis output."""
    company_name: str
    ticker: Optional[str] = None
    deal_type: str = ""
    recovery_waterfall: Dict[str, Any] = Field(default_factory=dict)
    credit_metrics: Dict[str, Any] = Field(default_factory=dict)
    comparable_transactions: List[Dict[str, Any]] = Field(default_factory=list)
    legal_status: Dict[str, Any] = Field(default_factory=dict)
    opportunity_score: float = Field(ge=0, le=100)
    probability_of_default: float = Field(ge=0.0, le=1.0)
    expected_recovery_rate: float = Field(ge=0.0, le=1.0)
    time_to_resolution_months: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RiskMetrics(BaseModel):
    """Unified risk metrics across asset classes."""
    asset_class: AssetClass
    var_95: Optional[float] = None
    cvar_95: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    # Bond-specific
    dv01: Optional[float] = None
    cs01: Optional[float] = None
    oas: Optional[float] = None
    key_rate_duration: Optional[Dict[str, float]] = None
    # Crypto-specific
    realized_volatility: Optional[float] = None
    implied_volatility: Optional[float] = None
    liquidity_depth: Optional[float] = None
    exchange_concentration: Optional[float] = None
    # Real estate-specific
    cap_rate: Optional[float] = None
    ltv_ratio: Optional[float] = None
    vacancy_rate: Optional[float] = None
    # Distressed-specific
    expected_recovery: Optional[float] = None
    prob_default: Optional[float] = None
    time_to_resolution: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PositionRecommendation(BaseModel):
    """Position sizing recommendation from a sub-orchestrator."""
    asset_class: AssetClass
    ticker: str
    direction: Direction
    conviction: float = Field(ge=-1.0, le=1.0)
    recommended_size_pct: float = Field(ge=0.0, le=1.0)
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    risk_metrics: RiskMetrics
    confidence_interval: tuple[float, float] = (0.0, 0.0)
    data_freshness_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# LangGraph State TypedDicts
# ---------------------------------------------------------------------------

class MarketAgentState(TypedDict, total=False):
    """Master state for the portfolio orchestrator LangGraph."""
    # Identifiers
    run_id: str
    ticker: str
    asset_class: str
    timestamp: str

    # Input data
    market_data: Dict[str, Any]
    macro_data: Dict[str, Any]

    # Regime
    regime: str
    regime_confidence: float

    # Agent outputs
    ta_analysis: Dict[str, Any]
    sentiment_analysis: Dict[str, Any]
    fundamental_analysis: Dict[str, Any]

    # Consensus
    agent_completion_mask: int
    council_votes: List[Dict[str, Any]]
    consensus_decision: str
    conviction_score: Dict[str, Any]

    # Code guardian
    code_guardian_report: Dict[str, Any]
    guardian_approved: bool

    # Deal analysis (parallel branch)
    deal_analysis: Dict[str, Any]

    # Risk
    risk_metrics: Dict[str, Any]
    position_recommendations: List[Dict[str, Any]]

    # Final output
    final_recommendation: Dict[str, Any]

    # Meta
    status: str
    errors: List[str]
    degraded_agents: List[str]
    retry_count: int


class SubOrchestratorState(TypedDict, total=False):
    """State for asset-class sub-orchestrator LangGraph."""
    run_id: str
    asset_class: str
    tickers: List[str]
    timestamp: str

    # Data
    market_data: Dict[str, Any]
    supplementary_data: Dict[str, Any]

    # Agent outputs (keyed by agent name)
    agent_outputs: Dict[str, Any]
    agent_completion_mask: int

    # Consensus
    ta_scores: List[Dict[str, Any]]
    llm_opinions: List[Dict[str, Any]]
    conviction_scores: Dict[str, Dict[str, Any]]

    # Validation
    guardian_report: Dict[str, Any]
    guardian_approved: bool

    # Risk
    risk_metrics: Dict[str, Any]
    position_recommendations: List[Dict[str, Any]]

    # Meta
    status: str
    errors: List[str]
    degraded_agents: List[str]
