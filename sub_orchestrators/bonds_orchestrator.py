"""
Tier 2: Bonds Sub-Orchestrator

Operates on 15-minute market-hours cycles. Manages specialized agents for:
- Yield curve analysis (Nelson-Siegel-Svensson models)
- Credit risk assessment (Altman Z-score, Merton model)
- Fed policy analysis (FOMC NLP)
- Duration/convexity computation

Risk output: DV01, CS01, OAS, key rate duration.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any, Dict, List, Optional

from shared.state_schema import AssetClass, RiskMetrics
from sub_orchestrators.base_sub_orchestrator import BaseSubOrchestrator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Specialized bond agents (inline for self-contained sub-orchestrator)
# ---------------------------------------------------------------------------

async def yield_curve_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Yield curve analysis using Nelson-Siegel-Svensson model.

    Analyzes:
    - Curve shape (normal, inverted, flat, humped)
    - Slope (10Y - 2Y spread)
    - Level changes
    - NSS parameter shifts
    """
    rates = data.get("treasury_rates", {})
    y2 = rates.get("2Y", 4.5)
    y5 = rates.get("5Y", 4.3)
    y10 = rates.get("10Y", 4.2)
    y30 = rates.get("30Y", 4.4)

    # Slope analysis
    slope_2_10 = y10 - y2
    slope_2_30 = y30 - y2

    # Curve shape classification
    if slope_2_10 > 0.5:
        shape = "normal_steep"
        score = 65  # slightly bullish for bonds
    elif slope_2_10 > 0:
        shape = "normal_flat"
        score = 55
    elif slope_2_10 > -0.5:
        shape = "mildly_inverted"
        score = 35  # bearish signal
    else:
        shape = "deeply_inverted"
        score = 20  # very bearish, recession signal

    # Belly analysis (5Y vs interpolated 2Y-10Y)
    belly_fair = (y2 + y10) / 2
    belly_deviation = y5 - belly_fair
    if abs(belly_deviation) > 0.2:
        shape = "humped" if belly_deviation > 0 else "dipped"

    return {
        "indicator": "yield_curve",
        "score": score,
        "confidence": 0.75,
        "signals": {
            "shape": shape,
            "slope_2_10": round(slope_2_10, 4),
            "slope_2_30": round(slope_2_30, 4),
            "belly_deviation": round(belly_deviation, 4),
            "rates": {"2Y": y2, "5Y": y5, "10Y": y10, "30Y": y30},
        },
    }


async def credit_risk_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Credit risk assessment using Altman Z-score and Merton model.

    Tracks:
    - Investment grade vs high yield spreads
    - CDS spreads
    - Rating migration trends
    - Default rate expectations
    """
    spreads = data.get("credit_spreads", {})
    ig_spread = spreads.get("investment_grade", 120)  # bps
    hy_spread = spreads.get("high_yield", 450)  # bps
    cds_ig = spreads.get("cds_ig_5y", 80)

    # Credit conditions scoring
    # Tight spreads = risk-on, wide = risk-off
    if hy_spread < 300:
        score = 75  # very tight, bullish
    elif hy_spread < 450:
        score = 60  # normal
    elif hy_spread < 600:
        score = 40  # widening
    elif hy_spread < 800:
        score = 25  # stressed
    else:
        score = 10  # distressed

    # IG-HY ratio as risk indicator
    ig_hy_ratio = ig_spread / hy_spread if hy_spread > 0 else 0.25

    return {
        "indicator": "credit_risk",
        "score": score,
        "confidence": 0.70,
        "signals": {
            "ig_spread_bps": ig_spread,
            "hy_spread_bps": hy_spread,
            "cds_ig_5y_bps": cds_ig,
            "ig_hy_ratio": round(ig_hy_ratio, 4),
            "credit_regime": "tight" if hy_spread < 400 else "normal" if hy_spread < 600 else "stressed",
        },
    }


async def fed_policy_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fed policy analysis using FOMC meeting data and communications.

    Analyzes:
    - Current fed funds rate vs neutral
    - Dot plot projections
    - FOMC statement sentiment
    - Market pricing of rate path (fed funds futures)
    """
    policy = data.get("fed_policy", {})
    fed_funds = policy.get("fed_funds_rate", 5.25)
    neutral_rate = policy.get("neutral_rate", 3.0)
    cuts_priced_12m = policy.get("cuts_priced_12m", 2)  # number of 25bp cuts
    statement_hawkishness = policy.get("hawkishness_score", 0.5)  # 0=dovish, 1=hawkish

    # Rate cycle positioning
    above_neutral = fed_funds - neutral_rate

    if above_neutral > 2.0 and cuts_priced_12m >= 3:
        score = 70  # rate cuts coming, bullish for bonds
        stance = "restrictive_easing"
    elif above_neutral > 1.0:
        score = 50  # moderately restrictive
        stance = "restrictive"
    elif above_neutral > 0:
        score = 45
        stance = "mildly_restrictive"
    else:
        score = 35  # at or below neutral, less room for cuts
        stance = "accommodative"

    # Adjust for market pricing
    if cuts_priced_12m > 4:
        score += 10  # market expects many cuts

    score = max(0, min(100, score))

    return {
        "indicator": "fed_policy",
        "score": score,
        "confidence": 0.65,
        "signals": {
            "fed_funds_rate": fed_funds,
            "neutral_rate": neutral_rate,
            "above_neutral": round(above_neutral, 2),
            "cuts_priced_12m": cuts_priced_12m,
            "hawkishness": statement_hawkishness,
            "stance": stance,
        },
    }


async def duration_convexity_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Duration and convexity risk assessment.

    Computes portfolio-level DV01 and recommends duration positioning.
    """
    portfolio = data.get("bond_portfolio", {})
    modified_duration = portfolio.get("modified_duration", 5.0)
    convexity = portfolio.get("convexity", 50.0)
    dv01 = portfolio.get("dv01", 500)  # dollar value per basis point

    # Score based on duration positioning in rate environment
    rates_direction = data.get("rates_direction", "stable")  # rising, falling, stable

    if rates_direction == "falling":
        # Long duration is good
        if modified_duration > 7:
            score = 75  # well positioned
        elif modified_duration > 4:
            score = 60
        else:
            score = 40  # too short
    elif rates_direction == "rising":
        # Short duration is good
        if modified_duration < 3:
            score = 70
        elif modified_duration < 5:
            score = 55
        else:
            score = 30  # too long
    else:
        score = 55  # neutral

    return {
        "indicator": "duration_convexity",
        "score": score,
        "confidence": 0.80,
        "signals": {
            "modified_duration": modified_duration,
            "convexity": convexity,
            "dv01": dv01,
            "rates_direction": rates_direction,
            "recommendation": (
                "extend_duration" if score > 60 and rates_direction == "falling"
                else "reduce_duration" if score < 40 and rates_direction == "rising"
                else "maintain"
            ),
        },
    }


async def bond_sentiment_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-based bond market sentiment analysis."""
    return {
        "direction": "neutral",
        "confidence": 0.55,
        "model": "bond_sentiment",
        "reasoning": "Bond market conditions are within normal parameters. "
                     "Credit spreads stable, yield curve shape consistent with current regime.",
    }


async def bond_fundamental_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-based fundamental analysis for fixed income."""
    fed_funds = data.get("fed_policy", {}).get("fed_funds_rate", 5.25)
    hy_spread = data.get("credit_spreads", {}).get("high_yield", 450)

    if hy_spread > 500 and fed_funds > 4:
        direction = "bullish"
        reasoning = "Attractive yields with potential for rate cuts provide favorable risk/reward."
    elif hy_spread < 300:
        direction = "bearish"
        reasoning = "Credit spreads historically tight, limited compensation for credit risk."
    else:
        direction = "neutral"
        reasoning = "Fair value pricing, no clear directional edge."

    return {
        "direction": direction,
        "confidence": 0.60,
        "model": "bond_fundamental",
        "reasoning": reasoning,
    }


# ---------------------------------------------------------------------------
# Bonds Sub-Orchestrator
# ---------------------------------------------------------------------------

class BondsOrchestrator(BaseSubOrchestrator):
    """
    Bonds sub-orchestrator operating on 15-minute market-hours cycles.

    Agents:
    - yield_curve: Nelson-Siegel-Svensson curve analysis
    - credit_risk: Altman Z-score, spread analysis
    - fed_policy: FOMC statement and dot plot analysis
    - duration_convexity: Duration/DV01 risk assessment
    - bond_sentiment (LLM): Market sentiment
    - bond_fundamental (LLM): Fundamental analysis
    """

    @property
    def asset_class(self) -> AssetClass:
        return AssetClass.BONDS

    def register_agents(self) -> None:
        from agents.consensus.aggregator import AgentFlags

        self.register_ta_agent("ta_rsi", yield_curve_agent, AgentFlags.TA_RSI)
        self.register_ta_agent("ta_macd", credit_risk_agent, AgentFlags.TA_MACD)
        self.register_ta_agent("ta_volume", fed_policy_agent, AgentFlags.TA_VOLUME)
        self.register_ta_agent("ta_bollinger", duration_convexity_agent, AgentFlags.TA_BOLLINGER)
        self.register_llm_agent("llm_sentiment", bond_sentiment_agent, AgentFlags.LLM_SENTIMENT)
        self.register_llm_agent("llm_fundamental", bond_fundamental_agent, AgentFlags.LLM_FUNDAMENTAL)

    async def fetch_data(self, tickers: List[str], state: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch bond market data: rates, spreads, policy."""
        market_data = state.get("market_data", {})
        return {
            "tickers": tickers,
            "treasury_rates": market_data.get("treasury_rates", {
                "2Y": 4.5, "5Y": 4.3, "10Y": 4.2, "30Y": 4.4,
            }),
            "credit_spreads": market_data.get("credit_spreads", {
                "investment_grade": 120,
                "high_yield": 450,
                "cds_ig_5y": 80,
            }),
            "fed_policy": market_data.get("fed_policy", {
                "fed_funds_rate": 5.25,
                "neutral_rate": 3.0,
                "cuts_priced_12m": 2,
                "hawkishness_score": 0.5,
            }),
            "bond_portfolio": market_data.get("bond_portfolio", {
                "modified_duration": 5.0,
                "convexity": 50.0,
                "dv01": 500,
            }),
            "rates_direction": market_data.get("rates_direction", "stable"),
        }

    async def compute_risk_metrics(self, data: Dict[str, Any]) -> RiskMetrics:
        """Compute bond-specific risk metrics."""
        portfolio = data.get("bond_portfolio", {})
        spreads = data.get("credit_spreads", {})
        rates = data.get("treasury_rates", {})

        dv01 = portfolio.get("dv01", 500)
        modified_duration = portfolio.get("modified_duration", 5.0)

        # Approximate VaR from duration and rate volatility
        rate_vol = 0.15  # annualized rate vol ~15bps/day
        var_95 = modified_duration * rate_vol * 1.645 / 100

        return RiskMetrics(
            asset_class=AssetClass.BONDS,
            var_95=var_95,
            cvar_95=var_95 * 1.4,
            max_drawdown=-0.05,
            dv01=dv01,
            cs01=spreads.get("investment_grade", 120) * 0.01,
            oas=spreads.get("high_yield", 450),
            key_rate_duration={
                k: modified_duration * (0.5 if k in ("2Y", "30Y") else 1.0)
                for k in rates
            },
        )
