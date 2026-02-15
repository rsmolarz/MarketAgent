"""
Tier 2: Distressed Debt Sub-Orchestrator

Event-driven, triggered by PACER filings, rating downgrades, and CDS spread
spikes. Manages specialized agents for:
- Recovery analysis (waterfall modeling, seniority analysis)
- Legal/restructuring (PACER monitoring, Ch.7 vs Ch.11)
- Vulture investing (identifies securities trading >1000bps over Treasuries)

Risk output: expected recovery rate, probability of default, time-to-resolution.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from shared.state_schema import AssetClass, DealAnalysis, RiskMetrics
from sub_orchestrators.base_sub_orchestrator import BaseSubOrchestrator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Specialized distressed debt agents
# ---------------------------------------------------------------------------

async def recovery_analysis_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recovery waterfall modeling and seniority analysis.

    Computes:
    - Enterprise value distribution by seniority
    - Fulcrum security identification
    - Recovery rates per tranche
    - Scenario analysis (Chapter 7 liquidation vs Chapter 11 restructuring)
    """
    deal = data.get("deal_data", {})
    enterprise_value = deal.get("enterprise_value", 500_000_000)
    senior_secured = deal.get("senior_secured_debt", 200_000_000)
    senior_unsecured = deal.get("senior_unsecured_debt", 150_000_000)
    subordinated = deal.get("subordinated_debt", 100_000_000)
    total_debt = senior_secured + senior_unsecured + subordinated

    # Waterfall computation
    remaining = enterprise_value

    # Senior secured recovery
    sr_secured_recovery = min(remaining, senior_secured)
    remaining -= sr_secured_recovery
    sr_secured_pct = sr_secured_recovery / senior_secured if senior_secured > 0 else 0

    # Senior unsecured recovery
    sr_unsecured_recovery = min(remaining, senior_unsecured)
    remaining -= sr_unsecured_recovery
    sr_unsecured_pct = sr_unsecured_recovery / senior_unsecured if senior_unsecured > 0 else 0

    # Subordinated recovery
    sub_recovery = min(remaining, subordinated)
    sub_pct = sub_recovery / subordinated if subordinated > 0 else 0

    # Identify fulcrum security
    if sr_secured_pct < 1.0:
        fulcrum = "senior_secured"
    elif sr_unsecured_pct < 1.0:
        fulcrum = "senior_unsecured"
    elif sub_pct < 1.0:
        fulcrum = "subordinated"
    else:
        fulcrum = "equity"

    # Overall attractiveness score
    blended_recovery = enterprise_value / total_debt if total_debt > 0 else 0
    if blended_recovery > 0.8:
        score = 70
    elif blended_recovery > 0.6:
        score = 60
    elif blended_recovery > 0.4:
        score = 50
    elif blended_recovery > 0.2:
        score = 40
    else:
        score = 25

    return {
        "indicator": "recovery_analysis",
        "score": score,
        "confidence": 0.70,
        "signals": {
            "enterprise_value": enterprise_value,
            "total_debt": total_debt,
            "senior_secured_recovery_pct": round(sr_secured_pct, 4),
            "senior_unsecured_recovery_pct": round(sr_unsecured_pct, 4),
            "subordinated_recovery_pct": round(sub_pct, 4),
            "fulcrum_security": fulcrum,
            "blended_recovery": round(blended_recovery, 4),
        },
    }


async def legal_restructuring_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Legal and restructuring analysis agent.

    Monitors:
    - PACER filings and docket activity
    - Chapter 7 vs Chapter 11 assessment
    - DIP financing availability
    - Creditor committee formation
    - Plan of Reorganization progress
    """
    legal = data.get("legal", {})
    chapter = legal.get("chapter", 11)
    dip_secured = legal.get("dip_financing_secured", True)
    days_in_bankruptcy = legal.get("days_in_bankruptcy", 0)
    creditor_committee = legal.get("creditor_committee_formed", False)
    plan_filed = legal.get("plan_of_reorg_filed", False)

    # Score based on restructuring progress
    if chapter == 7:
        score = 35  # liquidation, limited upside
    elif plan_filed and dip_secured:
        score = 70  # clear path to emergence
    elif dip_secured and creditor_committee:
        score = 55  # progressing
    elif dip_secured:
        score = 45
    else:
        score = 30  # uncertain

    # Time pressure
    if days_in_bankruptcy > 365:
        score -= 10  # protracted case
    elif days_in_bankruptcy > 180:
        score -= 5

    score = max(0, min(100, score))

    return {
        "indicator": "legal_restructuring",
        "score": score,
        "confidence": 0.65,
        "signals": {
            "chapter": chapter,
            "dip_financing_secured": dip_secured,
            "days_in_bankruptcy": days_in_bankruptcy,
            "creditor_committee_formed": creditor_committee,
            "plan_of_reorg_filed": plan_filed,
            "restructuring_stage": (
                "plan_filed" if plan_filed
                else "committee_formed" if creditor_committee
                else "early_stage"
            ),
        },
    }


async def vulture_investing_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Vulture investing agent identifying deep-discount opportunities.

    Identifies securities trading >1000bps over Treasuries, distressed
    exchanges, and potential par recovery situations.
    """
    pricing = data.get("pricing", {})
    spread_bps = pricing.get("spread_to_treasury_bps", 800)
    price_cents = pricing.get("price_cents_on_dollar", 60)
    cds_spread = pricing.get("cds_spread_bps", 1500)
    days_since_downgrade = pricing.get("days_since_last_downgrade", 30)

    # Deep discount scoring
    if spread_bps > 2000:
        score = 80  # extreme distress, high potential return
    elif spread_bps > 1500:
        score = 70
    elif spread_bps > 1000:
        score = 60
    elif spread_bps > 500:
        score = 40  # stressed but not deeply distressed
    else:
        score = 25  # not distressed enough

    # Price discount adjustment
    if price_cents < 30:
        score += 5  # deep discount
    elif price_cents > 80:
        score -= 10  # limited upside

    score = max(0, min(100, score))

    return {
        "indicator": "vulture_investing",
        "score": score,
        "confidence": 0.60,
        "signals": {
            "spread_to_treasury_bps": spread_bps,
            "price_cents_on_dollar": price_cents,
            "cds_spread_bps": cds_spread,
            "days_since_last_downgrade": days_since_downgrade,
            "opportunity_tier": (
                "deep_value" if spread_bps > 1500
                else "distressed" if spread_bps > 1000
                else "stressed" if spread_bps > 500
                else "watch"
            ),
        },
    }


async def credit_metrics_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Credit metrics agent computing Altman Z-score and related measures.
    """
    financials = data.get("financials", {})
    working_capital = financials.get("working_capital", 50_000_000)
    total_assets = financials.get("total_assets", 1_000_000_000)
    retained_earnings = financials.get("retained_earnings", -200_000_000)
    ebit = financials.get("ebit", 80_000_000)
    market_cap = financials.get("market_cap", 100_000_000)
    total_liabilities = financials.get("total_liabilities", 800_000_000)
    revenue = financials.get("revenue", 500_000_000)

    # Altman Z-score components
    if total_assets > 0:
        x1 = working_capital / total_assets
        x2 = retained_earnings / total_assets
        x3 = ebit / total_assets
        x5 = revenue / total_assets
    else:
        x1 = x2 = x3 = x5 = 0

    x4 = market_cap / total_liabilities if total_liabilities > 0 else 0

    z_score = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

    # Interest coverage
    interest_expense = financials.get("interest_expense", 60_000_000)
    coverage = ebit / interest_expense if interest_expense > 0 else 0

    # Debt/EBITDA
    ebitda = financials.get("ebitda", 120_000_000)
    total_debt = financials.get("total_debt", 500_000_000)
    leverage = total_debt / ebitda if ebitda > 0 else 999

    # Score based on Z-score
    if z_score > 2.99:
        score = 70  # safe zone
    elif z_score > 1.81:
        score = 50  # grey zone
    else:
        score = 30  # distress zone

    return {
        "indicator": "credit_metrics",
        "score": score,
        "confidence": 0.75,
        "signals": {
            "altman_z_score": round(z_score, 3),
            "interest_coverage": round(coverage, 2),
            "debt_to_ebitda": round(leverage, 2),
            "z_score_zone": "safe" if z_score > 2.99 else "grey" if z_score > 1.81 else "distress",
        },
    }


async def distressed_sentiment_llm(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM sentiment analysis for distressed situations."""
    spread = data.get("pricing", {}).get("spread_to_treasury_bps", 800)
    chapter = data.get("legal", {}).get("chapter", 11)

    if chapter == 11 and spread > 1000:
        return {
            "direction": "bullish",
            "confidence": 0.55,
            "model": "distressed_sentiment",
            "reasoning": "Chapter 11 restructuring with wide spreads suggests potential recovery opportunity.",
        }
    return {
        "direction": "neutral",
        "confidence": 0.45,
        "model": "distressed_sentiment",
        "reasoning": "Insufficient information to form strong directional view.",
    }


async def distressed_fundamental_llm(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM fundamental analysis for distressed debt."""
    z_score = data.get("financials", {}).get("altman_z_score", 1.5)
    recovery = data.get("deal_data", {}).get("blended_recovery", 0.5)

    if recovery and recovery > 0.6:
        return {
            "direction": "bullish",
            "confidence": 0.60,
            "model": "distressed_fundamental",
            "reasoning": "Adequate asset coverage supports above-average recovery expectations.",
        }
    return {
        "direction": "bearish",
        "confidence": 0.55,
        "model": "distressed_fundamental",
        "reasoning": "Low asset coverage raises concerns about recovery rates.",
    }


# ---------------------------------------------------------------------------
# Distressed Debt Sub-Orchestrator
# ---------------------------------------------------------------------------

class DistressedOrchestrator(BaseSubOrchestrator):
    """
    Distressed debt sub-orchestrator, event-driven.

    Triggered by: PACER filings, rating downgrades, CDS spread spikes.

    Agents:
    - recovery_analysis: Waterfall modeling, seniority analysis
    - legal_restructuring: PACER monitoring, Chapter assessment
    - vulture_investing: Deep discount identification
    - credit_metrics: Altman Z-score, leverage ratios
    - distressed_sentiment (LLM): Situation sentiment
    - distressed_fundamental (LLM): Fundamental analysis
    """

    @property
    def asset_class(self) -> AssetClass:
        return AssetClass.DISTRESSED

    def register_agents(self) -> None:
        from agents.consensus.aggregator import AgentFlags

        self.register_ta_agent("ta_rsi", recovery_analysis_agent, AgentFlags.TA_RSI)
        self.register_ta_agent("ta_macd", legal_restructuring_agent, AgentFlags.TA_MACD)
        self.register_ta_agent("ta_volume", vulture_investing_agent, AgentFlags.TA_VOLUME)
        self.register_ta_agent("ta_bollinger", credit_metrics_agent, AgentFlags.TA_BOLLINGER)
        self.register_llm_agent("llm_sentiment", distressed_sentiment_llm, AgentFlags.LLM_SENTIMENT)
        self.register_llm_agent("llm_fundamental", distressed_fundamental_llm, AgentFlags.LLM_FUNDAMENTAL)

    async def fetch_data(self, tickers: List[str], state: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch distressed debt data from SEC EDGAR, PACER, and market sources."""
        market_data = state.get("market_data", {})
        return {
            "tickers": tickers,
            "deal_data": market_data.get("deal_data", {
                "enterprise_value": 500_000_000,
                "senior_secured_debt": 200_000_000,
                "senior_unsecured_debt": 150_000_000,
                "subordinated_debt": 100_000_000,
            }),
            "legal": market_data.get("legal", {
                "chapter": 11,
                "dip_financing_secured": True,
                "days_in_bankruptcy": 90,
                "creditor_committee_formed": True,
                "plan_of_reorg_filed": False,
            }),
            "pricing": market_data.get("pricing", {
                "spread_to_treasury_bps": 1200,
                "price_cents_on_dollar": 55,
                "cds_spread_bps": 1500,
                "days_since_last_downgrade": 45,
            }),
            "financials": market_data.get("financials", {
                "working_capital": 50_000_000,
                "total_assets": 1_000_000_000,
                "retained_earnings": -200_000_000,
                "ebit": 80_000_000,
                "market_cap": 100_000_000,
                "total_liabilities": 800_000_000,
                "revenue": 500_000_000,
                "interest_expense": 60_000_000,
                "ebitda": 120_000_000,
                "total_debt": 500_000_000,
            }),
        }

    async def compute_risk_metrics(self, data: Dict[str, Any]) -> RiskMetrics:
        """Compute distressed-specific risk metrics."""
        deal = data.get("deal_data", {})
        pricing = data.get("pricing", {})

        ev = deal.get("enterprise_value", 500_000_000)
        total_debt = sum([
            deal.get("senior_secured_debt", 0),
            deal.get("senior_unsecured_debt", 0),
            deal.get("subordinated_debt", 0),
        ])
        recovery = ev / total_debt if total_debt > 0 else 0

        spread_bps = pricing.get("spread_to_treasury_bps", 1200)
        # Implied probability of default from spread (simplified)
        lgd = 1 - recovery
        prob_default = (spread_bps / 10000) / lgd if lgd > 0 else 0.5

        return RiskMetrics(
            asset_class=AssetClass.DISTRESSED,
            var_95=0.15,  # distressed has high var
            cvar_95=0.25,
            max_drawdown=-0.30,
            expected_recovery=min(1.0, recovery),
            prob_default=min(1.0, prob_default),
            time_to_resolution=18.0,  # months
        )

    async def run(self, parent_state: Dict[str, Any]) -> Dict[str, Any]:
        """Override to add deal analysis to the output."""
        result = await super().run(parent_state)

        # Build deal analysis summary
        deal_data = parent_state.get("market_data", {}).get("deal_data", {})
        if deal_data:
            ev = deal_data.get("enterprise_value", 0)
            total_debt = sum([
                deal_data.get("senior_secured_debt", 0),
                deal_data.get("senior_unsecured_debt", 0),
                deal_data.get("subordinated_debt", 0),
            ])
            result["deal_analysis"] = {
                "enterprise_value": ev,
                "total_debt": total_debt,
                "blended_recovery": ev / total_debt if total_debt > 0 else 0,
                "conviction_scores": result.get("conviction_scores", {}),
            }

        return result
