"""
Macro regime classification using Bridgewater's four-box framework.

Classifies the current macro environment into:
  - Rising growth / Rising inflation
  - Rising growth / Falling inflation
  - Falling growth / Rising inflation
  - Falling growth / Falling inflation

Plus volatility overlays (high/low) that modify sub-orchestrator behaviour.
Routes capital to appropriate strategies based on regime.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from shared.state_schema import MarketRegime

logger = logging.getLogger(__name__)


@dataclass
class RegimeIndicator:
    """A single macro indicator used for regime classification."""
    name: str
    value: float
    trend: str = "flat"  # "rising", "falling", "flat"
    z_score: float = 0.0
    source: str = ""
    timestamp: Optional[datetime] = None


@dataclass
class RegimeClassification:
    """Result of regime detection."""
    regime: MarketRegime
    confidence: float  # 0.0 to 1.0
    growth_score: float  # negative = falling, positive = rising
    inflation_score: float  # negative = falling, positive = rising
    volatility_score: float  # 0 = low, 100 = high
    indicators_used: List[RegimeIndicator] = field(default_factory=list)
    recommended_allocations: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime.value,
            "confidence": self.confidence,
            "growth_score": self.growth_score,
            "inflation_score": self.inflation_score,
            "volatility_score": self.volatility_score,
            "recommended_allocations": self.recommended_allocations,
            "timestamp": self.timestamp.isoformat(),
        }


# Default Bridgewater-style allocation templates
REGIME_ALLOCATIONS = {
    MarketRegime.RISING_GROWTH_RISING_INFLATION: {
        "bonds": 0.10,
        "crypto": 0.25,
        "real_estate": 0.35,
        "distressed": 0.30,
    },
    MarketRegime.RISING_GROWTH_FALLING_INFLATION: {
        "bonds": 0.30,
        "crypto": 0.20,
        "real_estate": 0.30,
        "distressed": 0.20,
    },
    MarketRegime.FALLING_GROWTH_RISING_INFLATION: {
        "bonds": 0.15,
        "crypto": 0.10,
        "real_estate": 0.15,
        "distressed": 0.60,
    },
    MarketRegime.FALLING_GROWTH_FALLING_INFLATION: {
        "bonds": 0.45,
        "crypto": 0.10,
        "real_estate": 0.20,
        "distressed": 0.25,
    },
    MarketRegime.HIGH_VOLATILITY: {
        "bonds": 0.30,
        "crypto": 0.05,
        "real_estate": 0.15,
        "distressed": 0.50,
    },
    MarketRegime.RISK_ON: {
        "bonds": 0.15,
        "crypto": 0.30,
        "real_estate": 0.30,
        "distressed": 0.25,
    },
    MarketRegime.RISK_OFF: {
        "bonds": 0.50,
        "crypto": 0.05,
        "real_estate": 0.15,
        "distressed": 0.30,
    },
}


class MacroRegimeDetector:
    """
    Classifies the current macro environment using multiple indicators.

    Indicators tracked:
    - GDP growth rate (real)
    - PMI (manufacturing + services)
    - Employment / unemployment claims
    - CPI / PCE inflation
    - Fed funds rate / yield curve slope
    - VIX / credit spreads
    - Dollar index (DXY)
    """

    # Thresholds for growth/inflation scoring
    GROWTH_INDICATORS = {
        "gdp_growth": {"weight": 0.3, "neutral": 2.0},
        "pmi": {"weight": 0.25, "neutral": 50.0},
        "unemployment_claims": {"weight": 0.15, "neutral": 250000, "inverted": True},
        "retail_sales_yoy": {"weight": 0.15, "neutral": 3.0},
        "industrial_production_yoy": {"weight": 0.15, "neutral": 1.0},
    }

    INFLATION_INDICATORS = {
        "cpi_yoy": {"weight": 0.30, "neutral": 2.5},
        "pce_yoy": {"weight": 0.25, "neutral": 2.0},
        "fed_funds_rate": {"weight": 0.20, "neutral": 3.0},
        "breakeven_inflation_5y": {"weight": 0.15, "neutral": 2.2},
        "commodity_index_yoy": {"weight": 0.10, "neutral": 0.0},
    }

    VOLATILITY_INDICATORS = {
        "vix": {"weight": 0.40, "threshold_high": 25, "threshold_critical": 35},
        "credit_spread_hy": {"weight": 0.30, "threshold_high": 500, "threshold_critical": 800},
        "move_index": {"weight": 0.30, "threshold_high": 120, "threshold_critical": 160},
    }

    def __init__(self):
        self._indicators: Dict[str, RegimeIndicator] = {}
        self._history: List[RegimeClassification] = []

    def update_indicator(
        self,
        name: str,
        value: float,
        source: str = "",
        trend: str = "flat",
    ) -> None:
        """Update a macro indicator value."""
        self._indicators[name] = RegimeIndicator(
            name=name,
            value=value,
            trend=trend,
            source=source,
            timestamp=datetime.utcnow(),
        )

    def update_indicators_bulk(self, data: Dict[str, float]) -> None:
        """Update multiple indicators at once."""
        for name, value in data.items():
            self.update_indicator(name, value)

    def _score_dimension(
        self,
        indicator_config: Dict[str, Dict],
    ) -> Tuple[float, float]:
        """
        Score a dimension (growth or inflation).
        Returns (score, confidence) where score is positive for rising,
        negative for falling.
        """
        weighted_sum = 0.0
        total_weight = 0.0

        for name, config in indicator_config.items():
            indicator = self._indicators.get(name)
            if indicator is None:
                continue

            weight = config["weight"]
            neutral = config["neutral"]
            inverted = config.get("inverted", False)

            # Normalize: deviation from neutral
            deviation = indicator.value - neutral
            if inverted:
                deviation = -deviation

            # Scale roughly to [-1, 1] range
            if neutral != 0:
                normalized = deviation / abs(neutral)
            else:
                normalized = deviation / 10.0  # arbitrary scaling for zero-neutral

            normalized = max(-2.0, min(2.0, normalized))

            weighted_sum += weight * normalized
            total_weight += weight

        if total_weight == 0:
            return 0.0, 0.0

        score = weighted_sum / total_weight
        confidence = total_weight / sum(c["weight"] for c in indicator_config.values())
        return score, confidence

    def _score_volatility(self) -> float:
        """Score volatility on a 0-100 scale."""
        scores = []
        for name, config in self.VOLATILITY_INDICATORS.items():
            indicator = self._indicators.get(name)
            if indicator is None:
                continue

            threshold_high = config["threshold_high"]
            threshold_critical = config["threshold_critical"]

            if indicator.value >= threshold_critical:
                score = 100.0
            elif indicator.value >= threshold_high:
                # Linear interpolation between high and critical
                pct = (indicator.value - threshold_high) / (threshold_critical - threshold_high)
                score = 50.0 + pct * 50.0
            else:
                # Below high threshold
                score = (indicator.value / threshold_high) * 50.0

            scores.append(score * config["weight"])

        if not scores:
            return 50.0  # unknown -> neutral
        total_weight = sum(
            self.VOLATILITY_INDICATORS[n]["weight"]
            for n in self.VOLATILITY_INDICATORS
            if n in self._indicators
        )
        return sum(scores) / total_weight if total_weight > 0 else 50.0

    def classify(self) -> RegimeClassification:
        """
        Run regime classification on current indicators.
        Returns a RegimeClassification with regime, confidence, and
        recommended allocations.
        """
        growth_score, growth_conf = self._score_dimension(self.GROWTH_INDICATORS)
        inflation_score, inflation_conf = self._score_dimension(self.INFLATION_INDICATORS)
        volatility_score = self._score_volatility()

        # Determine regime from four-box
        if volatility_score >= 75:
            regime = MarketRegime.HIGH_VOLATILITY
        elif growth_score > 0 and inflation_score > 0:
            regime = MarketRegime.RISING_GROWTH_RISING_INFLATION
        elif growth_score > 0 and inflation_score <= 0:
            regime = MarketRegime.RISING_GROWTH_FALLING_INFLATION
        elif growth_score <= 0 and inflation_score > 0:
            regime = MarketRegime.FALLING_GROWTH_RISING_INFLATION
        else:
            regime = MarketRegime.FALLING_GROWTH_FALLING_INFLATION

        overall_confidence = (growth_conf + inflation_conf) / 2.0

        allocations = REGIME_ALLOCATIONS.get(regime, REGIME_ALLOCATIONS[MarketRegime.RISK_OFF])

        classification = RegimeClassification(
            regime=regime,
            confidence=overall_confidence,
            growth_score=growth_score,
            inflation_score=inflation_score,
            volatility_score=volatility_score,
            indicators_used=list(self._indicators.values()),
            recommended_allocations=allocations,
        )

        self._history.append(classification)
        logger.info(
            f"Regime: {regime.value} (conf={overall_confidence:.2f}, "
            f"growth={growth_score:.2f}, inflation={inflation_score:.2f}, "
            f"vol={volatility_score:.1f})"
        )
        return classification

    def get_history(self, n: int = 10) -> List[RegimeClassification]:
        return self._history[-n:]
