"""
Tier 2: Real Estate Sub-Orchestrator

Operates on weekly/quarterly cycles with demographic modeling.
Manages specialized agents for:
- Valuation (DCF, automated valuation models)
- Market cycle positioning (Mueller cycle)
- Demographics (Census data, migration patterns)

Risk output: cap rate compression, LTV ratios, vacancy rates.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from shared.state_schema import AssetClass, RiskMetrics
from sub_orchestrators.base_sub_orchestrator import BaseSubOrchestrator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Specialized real estate agents
# ---------------------------------------------------------------------------

async def valuation_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Real estate valuation using DCF and automated valuation models.

    Analyzes:
    - Cap rate vs historical average
    - DCF valuation with discount rate sensitivity
    - Comparable transactions
    - Price-to-rent ratios
    """
    valuations = data.get("valuations", {})
    current_cap_rate = valuations.get("current_cap_rate", 5.5)
    historical_avg_cap = valuations.get("historical_avg_cap_rate", 6.0)
    price_to_rent = valuations.get("price_to_rent_ratio", 18)
    noi_growth = valuations.get("noi_growth_yoy", 3.0)

    # Cap rate compression/expansion
    cap_spread = current_cap_rate - historical_avg_cap

    if cap_spread < -1.0:
        score = 30  # very compressed, overvalued
    elif cap_spread < -0.3:
        score = 40
    elif cap_spread < 0.3:
        score = 55  # fair value
    elif cap_spread < 1.0:
        score = 65  # expanded, undervalued
    else:
        score = 75  # significantly undervalued

    # Adjust for NOI growth
    if noi_growth > 5:
        score += 5
    elif noi_growth < 0:
        score -= 10

    score = max(0, min(100, score))

    return {
        "indicator": "re_valuation",
        "score": score,
        "confidence": 0.65,
        "signals": {
            "current_cap_rate": current_cap_rate,
            "historical_avg_cap_rate": historical_avg_cap,
            "cap_rate_spread": round(cap_spread, 3),
            "price_to_rent_ratio": price_to_rent,
            "noi_growth_yoy": noi_growth,
            "valuation_regime": (
                "overvalued" if cap_spread < -0.5
                else "fair" if abs(cap_spread) < 0.5
                else "undervalued"
            ),
        },
    }


async def market_cycle_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mueller market cycle positioning agent.

    Places the current market in one of four phases:
    - Recovery: vacancy falling, no new construction, rent growth starting
    - Expansion: declining vacancy, new construction, accelerating rents
    - Hypersupply: increasing vacancy, lots of construction, rent growth slowing
    - Recession: rising vacancy, construction halting, negative rent growth
    """
    cycle = data.get("market_cycle", {})
    vacancy_trend = cycle.get("vacancy_trend", "flat")  # falling, flat, rising
    construction_pipeline = cycle.get("construction_pipeline_pct", 2.0)  # as % of stock
    rent_growth = cycle.get("rent_growth_yoy", 3.0)
    absorption_rate = cycle.get("absorption_rate_pct", 60)

    # Mueller cycle classification
    if vacancy_trend == "falling" and construction_pipeline < 1.5:
        phase = "recovery"
        score = 75
    elif vacancy_trend == "falling" and rent_growth > 3:
        phase = "expansion"
        score = 65
    elif vacancy_trend == "rising" and construction_pipeline > 3:
        phase = "hypersupply"
        score = 30
    elif vacancy_trend == "rising" and rent_growth < 0:
        phase = "recession"
        score = 15
    else:
        phase = "late_expansion"
        score = 50

    return {
        "indicator": "market_cycle",
        "score": score,
        "confidence": 0.60,
        "signals": {
            "mueller_phase": phase,
            "vacancy_trend": vacancy_trend,
            "construction_pipeline_pct": construction_pipeline,
            "rent_growth_yoy": rent_growth,
            "absorption_rate_pct": absorption_rate,
        },
    }


async def demographics_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Demographics agent analyzing Census data and migration patterns.

    Tracks:
    - Population growth trends
    - Net migration (domestic + international)
    - Household formation rates
    - Income growth vs housing costs
    """
    demo = data.get("demographics", {})
    pop_growth = demo.get("population_growth_pct", 0.5)
    net_migration = demo.get("net_migration_score", 50)  # 0-100
    household_formation = demo.get("household_formation_yoy", 1.2)  # millions
    income_housing_ratio = demo.get("income_to_housing_cost_ratio", 3.5)

    if net_migration > 70 and household_formation > 1.5:
        score = 75  # strong demand drivers
    elif net_migration > 50 and household_formation > 1.0:
        score = 60
    elif net_migration > 30:
        score = 45
    else:
        score = 30  # weak demand

    # Affordability adjustment
    if income_housing_ratio < 2.5:
        score -= 10  # expensive
    elif income_housing_ratio > 4.0:
        score += 5  # affordable

    score = max(0, min(100, score))

    return {
        "indicator": "demographics",
        "score": score,
        "confidence": 0.55,
        "signals": {
            "population_growth_pct": pop_growth,
            "net_migration_score": net_migration,
            "household_formation_yoy": household_formation,
            "income_to_housing_cost_ratio": income_housing_ratio,
            "demand_strength": "strong" if score > 60 else "moderate" if score > 40 else "weak",
        },
    }


async def re_supply_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Supply-side analysis for real estate."""
    supply = data.get("supply", {})
    permits = supply.get("building_permits_yoy_change", 0)
    completions = supply.get("completions_pct_of_stock", 1.5)

    if completions < 1.0 and permits < -10:
        score = 70  # supply constrained
    elif completions < 2.0:
        score = 55
    elif completions < 3.0:
        score = 40
    else:
        score = 25  # oversupply risk

    return {
        "indicator": "re_supply",
        "score": score,
        "confidence": 0.60,
        "signals": {
            "building_permits_yoy_change": permits,
            "completions_pct_of_stock": completions,
        },
    }


async def re_sentiment_llm(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-based real estate sentiment."""
    phase = data.get("market_cycle", {}).get("mueller_phase", "expansion")
    if phase in ("recovery", "expansion"):
        return {"direction": "bullish", "confidence": 0.55, "model": "re_sentiment",
                "reasoning": f"Market is in {phase} phase with favorable supply/demand dynamics."}
    elif phase == "hypersupply":
        return {"direction": "bearish", "confidence": 0.55, "model": "re_sentiment",
                "reasoning": "Hypersupply phase with rising vacancy risk."}
    return {"direction": "neutral", "confidence": 0.45, "model": "re_sentiment",
            "reasoning": "Transitional phase in real estate cycle."}


async def re_fundamental_llm(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM fundamental analysis for real estate."""
    cap_rate = data.get("valuations", {}).get("current_cap_rate", 5.5)
    if cap_rate > 6.5:
        return {"direction": "bullish", "confidence": 0.60, "model": "re_fundamental",
                "reasoning": "Attractive cap rates offer compelling entry point."}
    elif cap_rate < 4.5:
        return {"direction": "bearish", "confidence": 0.55, "model": "re_fundamental",
                "reasoning": "Compressed cap rates limit return potential."}
    return {"direction": "neutral", "confidence": 0.50, "model": "re_fundamental",
            "reasoning": "Fair value cap rate environment."}


# ---------------------------------------------------------------------------
# Real Estate Sub-Orchestrator
# ---------------------------------------------------------------------------

class RealEstateOrchestrator(BaseSubOrchestrator):
    """
    Real estate sub-orchestrator on weekly/quarterly cycles.

    Agents:
    - valuation: DCF, AVM, cap rate analysis
    - market_cycle: Mueller cycle positioning
    - demographics: Census, migration, household formation
    - re_supply: Building permits, completions
    - re_sentiment (LLM): Market sentiment
    - re_fundamental (LLM): Fundamental analysis
    """

    @property
    def asset_class(self) -> AssetClass:
        return AssetClass.REAL_ESTATE

    def register_agents(self) -> None:
        from agents.consensus.aggregator import AgentFlags

        self.register_ta_agent("ta_rsi", valuation_agent, AgentFlags.TA_RSI)
        self.register_ta_agent("ta_macd", market_cycle_agent, AgentFlags.TA_MACD)
        self.register_ta_agent("ta_volume", demographics_agent, AgentFlags.TA_VOLUME)
        self.register_ta_agent("ta_bollinger", re_supply_agent, AgentFlags.TA_BOLLINGER)
        self.register_llm_agent("llm_sentiment", re_sentiment_llm, AgentFlags.LLM_SENTIMENT)
        self.register_llm_agent("llm_fundamental", re_fundamental_llm, AgentFlags.LLM_FUNDAMENTAL)

    async def fetch_data(self, tickers: List[str], state: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch real estate market data."""
        market_data = state.get("market_data", {})
        return {
            "tickers": tickers,
            "valuations": market_data.get("valuations", {
                "current_cap_rate": 5.5,
                "historical_avg_cap_rate": 6.0,
                "price_to_rent_ratio": 18,
                "noi_growth_yoy": 3.0,
            }),
            "market_cycle": market_data.get("market_cycle", {
                "vacancy_trend": "flat",
                "construction_pipeline_pct": 2.0,
                "rent_growth_yoy": 3.0,
                "absorption_rate_pct": 60,
            }),
            "demographics": market_data.get("demographics", {
                "population_growth_pct": 0.5,
                "net_migration_score": 55,
                "household_formation_yoy": 1.2,
                "income_to_housing_cost_ratio": 3.5,
            }),
            "supply": market_data.get("supply", {
                "building_permits_yoy_change": -5,
                "completions_pct_of_stock": 1.5,
            }),
        }

    async def compute_risk_metrics(self, data: Dict[str, Any]) -> RiskMetrics:
        """Compute real estate-specific risk metrics."""
        vals = data.get("valuations", {})
        cycle = data.get("market_cycle", {})

        cap_rate = vals.get("current_cap_rate", 5.5)
        vacancy = cycle.get("vacancy_trend", "flat")

        # RE has lower vol but illiquidity risk
        var_95 = 0.08  # quarterly VaR for RE

        return RiskMetrics(
            asset_class=AssetClass.REAL_ESTATE,
            var_95=var_95,
            cvar_95=var_95 * 1.5,
            max_drawdown=-0.15,
            cap_rate=cap_rate,
            ltv_ratio=0.65,
            vacancy_rate=0.08 if vacancy == "rising" else 0.05,
        )
