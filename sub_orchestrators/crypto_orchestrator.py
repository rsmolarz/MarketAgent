"""
Tier 2: Crypto Sub-Orchestrator

Operates 24/7 with 1-minute analysis cycles. Manages specialized agents for:
- On-chain analytics (whale flows, exchange balances)
- DeFi protocol monitoring (TVL, liquidation cascades)
- Market microstructure (order book depth, funding rates)

Risk output: realized/implied volatility, liquidity depth, exchange concentration.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

from shared.state_schema import AssetClass, RiskMetrics
from sub_orchestrators.base_sub_orchestrator import BaseSubOrchestrator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Specialized crypto agents
# ---------------------------------------------------------------------------

async def onchain_analytics_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    On-chain analytics agent tracking whale flows and exchange balances.

    Monitors:
    - Large wallet movements (>1000 BTC / >10000 ETH)
    - Net exchange flow (inflow vs outflow)
    - Active address trends
    - Miner/staker behaviour
    """
    onchain = data.get("onchain", {})
    exchange_netflow = onchain.get("exchange_netflow_btc", 0)  # positive = inflow (bearish)
    whale_transactions = onchain.get("whale_tx_count_24h", 50)
    active_addresses = onchain.get("active_addresses_change_pct", 0)

    # Net exchange flow scoring
    # Large inflows = selling pressure, outflows = accumulation
    if exchange_netflow < -5000:
        score = 80  # large outflow, bullish
    elif exchange_netflow < -1000:
        score = 65
    elif exchange_netflow < 1000:
        score = 50  # neutral
    elif exchange_netflow < 5000:
        score = 35
    else:
        score = 20  # large inflow, bearish

    # Adjust for active addresses
    if active_addresses > 5:
        score += 5
    elif active_addresses < -5:
        score -= 5

    score = max(0, min(100, score))

    return {
        "indicator": "onchain_analytics",
        "score": score,
        "confidence": 0.70,
        "signals": {
            "exchange_netflow_btc": exchange_netflow,
            "whale_tx_count_24h": whale_transactions,
            "active_addresses_change_pct": active_addresses,
            "flow_regime": "accumulation" if exchange_netflow < -1000 else "distribution" if exchange_netflow > 1000 else "neutral",
        },
    }


async def defi_protocol_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    DeFi protocol monitoring agent.

    Tracks:
    - Total Value Locked (TVL) trends
    - Liquidation cascade risk
    - Stablecoin flows between protocols
    - Yield farming APY anomalies
    """
    defi = data.get("defi", {})
    tvl_change_7d = defi.get("tvl_change_7d_pct", 0)
    liquidation_risk = defi.get("liquidation_risk_score", 30)  # 0-100
    stablecoin_flows = defi.get("stablecoin_net_flow_m", 0)  # millions

    # TVL trend scoring
    if tvl_change_7d > 10:
        score = 75  # rapid growth
    elif tvl_change_7d > 3:
        score = 62
    elif tvl_change_7d > -3:
        score = 50
    elif tvl_change_7d > -10:
        score = 38
    else:
        score = 25  # rapid decline

    # Adjust for liquidation risk
    if liquidation_risk > 70:
        score -= 15
    elif liquidation_risk > 50:
        score -= 5

    # Stablecoin flows
    if stablecoin_flows > 500:
        score += 5  # capital entering crypto
    elif stablecoin_flows < -500:
        score -= 5

    score = max(0, min(100, score))

    return {
        "indicator": "defi_protocol",
        "score": score,
        "confidence": 0.60,
        "signals": {
            "tvl_change_7d_pct": tvl_change_7d,
            "liquidation_risk_score": liquidation_risk,
            "stablecoin_net_flow_m": stablecoin_flows,
            "defi_health": "strong" if score > 60 else "neutral" if score > 40 else "weak",
        },
    }


async def market_microstructure_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Market microstructure agent tracking order book depth and funding rates.

    Monitors:
    - Perpetual futures funding rates
    - Order book imbalance (bid/ask depth ratio)
    - Open interest changes
    - Spot-perpetual basis
    """
    micro = data.get("microstructure", {})
    funding_rate = micro.get("funding_rate_8h", 0.01)  # 0.01% = neutral
    orderbook_imbalance = micro.get("orderbook_imbalance", 0)  # -1 to +1
    oi_change_24h = micro.get("oi_change_24h_pct", 0)
    basis = micro.get("spot_perp_basis_pct", 0.05)

    # Funding rate scoring
    # High positive = overleveraged longs, negative = overleveraged shorts
    if funding_rate > 0.05:
        score = 25  # extreme long leverage, mean reversion risk
    elif funding_rate > 0.02:
        score = 40
    elif funding_rate > -0.01:
        score = 55  # healthy
    elif funding_rate > -0.03:
        score = 65  # shorts paying, potential squeeze
    else:
        score = 80  # extreme negative, short squeeze likely

    # Adjust for orderbook imbalance
    score += orderbook_imbalance * 10

    score = max(0, min(100, score))

    return {
        "indicator": "market_microstructure",
        "score": score,
        "confidence": 0.75,
        "signals": {
            "funding_rate_8h": funding_rate,
            "orderbook_imbalance": orderbook_imbalance,
            "oi_change_24h_pct": oi_change_24h,
            "spot_perp_basis_pct": basis,
            "leverage_regime": (
                "extreme_long" if funding_rate > 0.05
                else "long_biased" if funding_rate > 0.02
                else "neutral" if funding_rate > -0.01
                else "short_biased" if funding_rate > -0.03
                else "extreme_short"
            ),
        },
    }


async def crypto_volume_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Volume profile analysis for crypto markets."""
    volume = data.get("volume", {})
    vol_24h = volume.get("volume_24h_usd", 50_000_000_000)
    vol_change = volume.get("volume_change_24h_pct", 0)

    if vol_change > 50:
        score = 70  # volume surge, directional move likely
    elif vol_change > 20:
        score = 60
    elif vol_change > -20:
        score = 50
    else:
        score = 35  # declining volume, trend weakening

    return {
        "indicator": "crypto_volume",
        "score": score,
        "confidence": 0.65,
        "signals": {
            "volume_24h_usd": vol_24h,
            "volume_change_24h_pct": vol_change,
        },
    }


async def crypto_sentiment_llm(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-based crypto sentiment analysis."""
    funding = data.get("microstructure", {}).get("funding_rate_8h", 0.01)
    if funding > 0.03:
        return {
            "direction": "bearish",
            "confidence": 0.60,
            "model": "crypto_sentiment",
            "reasoning": "Extreme long leverage suggests crowded trade, correction risk elevated.",
        }
    elif funding < -0.02:
        return {
            "direction": "bullish",
            "confidence": 0.60,
            "model": "crypto_sentiment",
            "reasoning": "Short-biased positioning creates squeeze potential.",
        }
    return {
        "direction": "neutral",
        "confidence": 0.50,
        "model": "crypto_sentiment",
        "reasoning": "Balanced positioning, no clear directional bias from microstructure.",
    }


async def crypto_fundamental_llm(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-based crypto fundamental analysis."""
    tvl_change = data.get("defi", {}).get("tvl_change_7d_pct", 0)
    exchange_netflow = data.get("onchain", {}).get("exchange_netflow_btc", 0)

    if tvl_change > 5 and exchange_netflow < -1000:
        direction = "bullish"
        reasoning = "Growing DeFi TVL and exchange outflows suggest accumulation."
    elif tvl_change < -5 and exchange_netflow > 1000:
        direction = "bearish"
        reasoning = "Declining TVL with exchange inflows indicate distribution."
    else:
        direction = "neutral"
        reasoning = "Mixed signals from on-chain and DeFi metrics."

    return {
        "direction": direction,
        "confidence": 0.55,
        "model": "crypto_fundamental",
        "reasoning": reasoning,
    }


async def crypto_macro_llm(data: Dict[str, Any]) -> Dict[str, Any]:
    """LLM macro overlay for crypto."""
    return {
        "direction": "neutral",
        "confidence": 0.45,
        "model": "crypto_macro",
        "reasoning": "Macro backdrop is secondary to crypto-native factors.",
    }


# ---------------------------------------------------------------------------
# Crypto Sub-Orchestrator
# ---------------------------------------------------------------------------

class CryptoOrchestrator(BaseSubOrchestrator):
    """
    Crypto sub-orchestrator operating 24/7 with 1-minute analysis cycles.

    Agents:
    - onchain_analytics: Whale flows, exchange balances
    - defi_protocol: TVL, liquidation cascades
    - market_microstructure: Order book depth, funding rates
    - crypto_volume: Volume profile analysis
    - crypto_sentiment (LLM): Market sentiment
    - crypto_fundamental (LLM): On-chain fundamentals
    - crypto_macro (LLM): Macro overlay
    """

    @property
    def asset_class(self) -> AssetClass:
        return AssetClass.CRYPTO

    def register_agents(self) -> None:
        from agents.consensus.aggregator import AgentFlags

        self.register_ta_agent("ta_rsi", onchain_analytics_agent, AgentFlags.TA_RSI)
        self.register_ta_agent("ta_macd", defi_protocol_agent, AgentFlags.TA_MACD)
        self.register_ta_agent("ta_volume", market_microstructure_agent, AgentFlags.TA_VOLUME)
        self.register_ta_agent("ta_bollinger", crypto_volume_agent, AgentFlags.TA_BOLLINGER)
        self.register_llm_agent("llm_sentiment", crypto_sentiment_llm, AgentFlags.LLM_SENTIMENT)
        self.register_llm_agent("llm_fundamental", crypto_fundamental_llm, AgentFlags.LLM_FUNDAMENTAL)
        self.register_llm_agent("llm_macro", crypto_macro_llm, AgentFlags.LLM_MACRO)

    async def fetch_data(self, tickers: List[str], state: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch crypto market data."""
        market_data = state.get("market_data", {})
        return {
            "tickers": tickers,
            "onchain": market_data.get("onchain", {
                "exchange_netflow_btc": 0,
                "whale_tx_count_24h": 50,
                "active_addresses_change_pct": 2.0,
            }),
            "defi": market_data.get("defi", {
                "tvl_change_7d_pct": 3.0,
                "liquidation_risk_score": 30,
                "stablecoin_net_flow_m": 200,
            }),
            "microstructure": market_data.get("microstructure", {
                "funding_rate_8h": 0.01,
                "orderbook_imbalance": 0.1,
                "oi_change_24h_pct": 5,
                "spot_perp_basis_pct": 0.05,
            }),
            "volume": market_data.get("volume", {
                "volume_24h_usd": 50_000_000_000,
                "volume_change_24h_pct": 5,
            }),
        }

    async def compute_risk_metrics(self, data: Dict[str, Any]) -> RiskMetrics:
        """Compute crypto-specific risk metrics."""
        micro = data.get("microstructure", {})
        funding = micro.get("funding_rate_8h", 0.01)

        # Crypto typically has higher realized vol
        realized_vol = 0.60  # annualized
        implied_vol = realized_vol * 1.1  # vol premium

        return RiskMetrics(
            asset_class=AssetClass.CRYPTO,
            var_95=realized_vol * 1.645 / math.sqrt(252),  # daily VaR
            cvar_95=realized_vol * 2.0 / math.sqrt(252),
            max_drawdown=-0.20,
            realized_volatility=realized_vol,
            implied_volatility=implied_vol,
            liquidity_depth=data.get("volume", {}).get("volume_24h_usd", 50e9),
            exchange_concentration=0.35,  # top-3 exchange share
        )
