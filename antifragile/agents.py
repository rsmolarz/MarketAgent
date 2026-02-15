"""
Antifragile Board Agents

Four specialized agents that integrate with the existing BaseAgent pattern
and can be scheduled alongside the platform's other market agents.

Each agent produces findings through its specific cognitive framework,
and the BoardCoordinator orchestrates the full Council Protocol.
"""

import logging
import math
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime

from agents.base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
from antifragile.tools import (
    FragilityScorer,
    GeometricSimulator,
    PatternDetector,
    FactorAnalyzer,
    AmbiguityScorer,
)
from antifragile.council import CouncilProtocol, quick_deliberate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared market data helper
# ---------------------------------------------------------------------------

def _fetch_market_snapshot(yahoo: YahooFinanceClient) -> Dict[str, Any]:
    """Fetch current market conditions for all advisors."""
    snapshot = {}
    symbols = {
        "SPY": "S&P 500",
        "^VIX": "VIX",
        "^TNX": "10Y Treasury",
        "QQQ": "NASDAQ",
        "IWM": "Russell 2000",
        "GLD": "Gold",
        "TLT": "Long Bonds",
        "BTC-USD": "Bitcoin",
    }

    for symbol, label in symbols.items():
        try:
            data = yahoo.get_price_data(symbol, period="3mo")
            if data is not None and len(data) > 20:
                current = float(data["Close"].iloc[-1])
                prev = float(data["Close"].iloc[-2])
                month_ago = float(data["Close"].iloc[-21]) if len(data) > 21 else current
                three_month_ago = float(data["Close"].iloc[0])

                snapshot[label] = {
                    "symbol": symbol,
                    "price": round(current, 2),
                    "daily_change_pct": round((current / prev - 1) * 100, 2),
                    "monthly_change_pct": round((current / month_ago - 1) * 100, 2),
                    "quarterly_change_pct": round((current / three_month_ago - 1) * 100, 2),
                }

                # Add volatility for relevant assets
                returns = data["Close"].pct_change().dropna()
                snapshot[label]["annualized_vol"] = round(
                    float(returns.std()) * math.sqrt(252) * 100, 2
                )
        except Exception as e:
            logger.warning(f"Failed to fetch {symbol}: {e}")

    return snapshot


# ---------------------------------------------------------------------------
# Taleb Agent: Fragility Detection
# ---------------------------------------------------------------------------

class TalebFragilityAgent(BaseAgent):
    """
    Epistemologist of Risk - identifies structural fragility, Black Swan exposure,
    and violations of the Lindy Effect across the market.
    """

    def __init__(self):
        super().__init__(name="TalebFragilityAgent")
        self.yahoo = YahooFinanceClient()
        self.scorer = FragilityScorer()

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []
        snapshot = _fetch_market_snapshot(self.yahoo)

        # 1. VIX-based fragility assessment
        findings.extend(self._check_vix_fragility(snapshot))

        # 2. Concentration risk in indices
        findings.extend(self._check_concentration_risk(snapshot))

        # 3. Leverage in the system (credit spreads proxy)
        findings.extend(self._check_system_leverage(snapshot))

        # 4. Fat-tail detection in recent returns
        findings.extend(self._check_fat_tails())

        return findings

    def _check_vix_fragility(self, snapshot: Dict) -> List[Dict]:
        findings = []
        vix = snapshot.get("VIX", {})
        if not vix:
            return findings

        vix_level = vix.get("price", 0)

        if vix_level < 13:
            findings.append(self.create_finding(
                title="Dangerous Complacency: VIX Below 13",
                description=(
                    f"VIX at {vix_level:.1f} indicates extreme complacency. "
                    "Low VIX is not safety - it is the calm before the storm. "
                    "Cheap tail protection should be accumulated now. "
                    "The market is pricing in Mediocristan when we live in Extremistan."
                ),
                severity="high",
                confidence=0.8,
                symbol="^VIX",
                market_type="volatility",
                metadata={"vix_level": vix_level, "framework": "taleb", "signal": "complacency"},
            ))
        elif vix_level > 35:
            findings.append(self.create_finding(
                title="Crisis Mode: VIX Signals Extremistan",
                description=(
                    f"VIX at {vix_level:.1f}. This is Extremistan territory. "
                    "Correlations are spiking to 1, diversification is failing. "
                    "Only explicit convex hedges protect here. "
                    "Activate via negativa: remove all fragile positions immediately."
                ),
                severity="critical",
                confidence=0.9,
                symbol="^VIX",
                market_type="volatility",
                metadata={"vix_level": vix_level, "framework": "taleb", "signal": "extremistan"},
            ))

        return findings

    def _check_concentration_risk(self, snapshot: Dict) -> List[Dict]:
        findings = []
        spy = snapshot.get("S&P 500", {})
        qqq = snapshot.get("NASDAQ", {})
        iwm = snapshot.get("Russell 2000", {})

        if spy and qqq and iwm:
            spy_q = spy.get("quarterly_change_pct", 0)
            qqq_q = qqq.get("quarterly_change_pct", 0)
            iwm_q = iwm.get("quarterly_change_pct", 0)

            # Divergence between mega-cap and small-cap = concentration
            divergence = abs(qqq_q - iwm_q)
            if divergence > 10:
                findings.append(self.create_finding(
                    title="Concentration Risk: Mega-Cap vs Small-Cap Divergence",
                    description=(
                        f"NASDAQ 3-month return: {qqq_q:.1f}% vs Russell 2000: {iwm_q:.1f}%. "
                        f"Divergence of {divergence:.1f}% indicates extreme concentration in mega-caps. "
                        "This is a fragility signal - the market's health depends on a handful of names. "
                        "A rotation or single-company event could cascade."
                    ),
                    severity="high",
                    confidence=0.75,
                    market_type="equity",
                    metadata={
                        "qqq_return": qqq_q, "iwm_return": iwm_q,
                        "divergence": divergence, "framework": "taleb",
                    },
                ))

        return findings

    def _check_system_leverage(self, snapshot: Dict) -> List[Dict]:
        findings = []
        bonds = snapshot.get("Long Bonds", {})
        gold = snapshot.get("Gold", {})

        if bonds and gold:
            bond_change = bonds.get("monthly_change_pct", 0)
            gold_change = gold.get("monthly_change_pct", 0)

            # If bonds are falling AND gold is rising = stress
            if bond_change < -3 and gold_change > 2:
                findings.append(self.create_finding(
                    title="System Stress: Bond Sell-off with Gold Rally",
                    description=(
                        f"Long bonds down {bond_change:.1f}% while gold up {gold_change:.1f}% this month. "
                        "This divergence suggests systemic stress: the market is fleeing "
                        "financial assets (bonds) into real assets (gold). "
                        "Historical precedent for deleveraging events."
                    ),
                    severity="high",
                    confidence=0.7,
                    market_type="macro",
                    metadata={
                        "bond_change": bond_change, "gold_change": gold_change,
                        "framework": "taleb", "signal": "deleveraging",
                    },
                ))

        return findings

    def _check_fat_tails(self) -> List[Dict]:
        findings = []
        try:
            data = self.yahoo.get_price_data("SPY", period="1y")
            if data is None or len(data) < 60:
                return findings

            returns = data["Close"].pct_change().dropna()
            # Kurtosis > 3 indicates fat tails (leptokurtic)
            kurtosis = float(returns.kurtosis())
            skew = float(returns.skew())

            if kurtosis > 5:
                findings.append(self.create_finding(
                    title="Fat Tails Detected: Gaussian Models Are Dangerous",
                    description=(
                        f"SPY return distribution has kurtosis of {kurtosis:.1f} (normal = 3). "
                        f"Skewness: {skew:.2f}. "
                        "This confirms Extremistan dynamics. "
                        "Any risk model using normal distribution assumptions "
                        "is systematically underpricing tail risk."
                    ),
                    severity="medium",
                    confidence=0.85,
                    symbol="SPY",
                    market_type="equity",
                    metadata={
                        "kurtosis": kurtosis, "skew": skew,
                        "framework": "taleb", "signal": "fat_tails",
                    },
                ))

        except Exception as e:
            logger.warning(f"Fat tail check failed: {e}")

        return findings


# ---------------------------------------------------------------------------
# Spitznagel Agent: Safe Haven & Drawdown Protection
# ---------------------------------------------------------------------------

class SpitznagelSafeHavenAgent(BaseAgent):
    """
    Safe Haven Practitioner - monitors drawdown risk, geometric return drag,
    and the cost-effectiveness of tail protection instruments.
    """

    def __init__(self):
        super().__init__(name="SpitznagelSafeHavenAgent")
        self.yahoo = YahooFinanceClient()
        self.simulator = GeometricSimulator()

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        # 1. Current drawdown analysis
        findings.extend(self._check_drawdown_risk())

        # 2. Volatility drain assessment
        findings.extend(self._check_volatility_drain())

        # 3. Safe haven cost-effectiveness
        findings.extend(self._check_haven_instruments())

        # 4. Bernoulli Falls warning
        findings.extend(self._check_bernoulli_falls())

        return findings

    def _check_drawdown_risk(self) -> List[Dict]:
        findings = []
        try:
            data = self.yahoo.get_price_data("SPY", period="1y")
            if data is None or len(data) < 60:
                return findings

            prices = data["Close"]
            peak = prices.expanding().max()
            drawdown = (prices - peak) / peak
            current_dd = float(drawdown.iloc[-1])
            max_dd = float(drawdown.min())

            if current_dd < -0.10:
                recovery = self.simulator.bernoulli_falls(abs(current_dd))
                findings.append(self.create_finding(
                    title=f"Active Drawdown: SPY Down {abs(current_dd)*100:.1f}% from Peak",
                    description=(
                        f"SPY is {abs(current_dd)*100:.1f}% below its 1-year peak. "
                        f"Recovery requires a {recovery['recovery_needed_pct']*100:.1f}% gain. "
                        f"At 10% annual returns, recovery takes ~{recovery['years_to_recover_at_10pct']} years. "
                        "This is the Bernoulli Falls in action - geometric returns punish losses."
                    ),
                    severity="high" if current_dd < -0.15 else "medium",
                    confidence=0.9,
                    symbol="SPY",
                    market_type="equity",
                    metadata={
                        "current_drawdown": current_dd,
                        "max_drawdown_1y": max_dd,
                        "recovery_needed": recovery["recovery_needed_pct"],
                        "framework": "spitznagel",
                    },
                ))
            elif current_dd > -0.03 and max_dd < -0.05:
                findings.append(self.create_finding(
                    title="Drawdown Recovery Window: Optimal for Protection Purchase",
                    description=(
                        f"SPY is near its peak (only {abs(current_dd)*100:.1f}% off highs). "
                        "This is the optimal time to purchase convex tail protection: "
                        "it is cheap when no one wants it. "
                        "Allocate ~3% to safe haven instruments now."
                    ),
                    severity="low",
                    confidence=0.7,
                    symbol="SPY",
                    market_type="equity",
                    metadata={
                        "current_drawdown": current_dd,
                        "framework": "spitznagel",
                        "signal": "protection_window",
                    },
                ))

        except Exception as e:
            logger.warning(f"Drawdown check failed: {e}")

        return findings

    def _check_volatility_drain(self) -> List[Dict]:
        findings = []
        try:
            data = self.yahoo.get_price_data("SPY", period="1y")
            if data is None or len(data) < 60:
                return findings

            monthly_returns = data["Close"].resample("ME").last().pct_change().dropna().tolist()
            if len(monthly_returns) < 6:
                return findings

            drain = self.simulator.volatility_drain(monthly_returns)
            vol_drain = drain.get("volatility_drain", 0)

            if vol_drain > 0.005:  # More than 0.5% annual drag
                findings.append(self.create_finding(
                    title=f"Volatility Drain: {vol_drain*100:.2f}% Annual CAGR Drag",
                    description=(
                        f"Arithmetic mean return: {drain['arithmetic_mean']*100:.2f}%. "
                        f"Geometric mean return: {drain['geometric_mean']*100:.2f}%. "
                        f"The gap of {vol_drain*100:.2f}% is the hidden tax of volatility. "
                        "Reducing portfolio volatility (via safe haven allocation) "
                        "directly increases long-term compound growth."
                    ),
                    severity="medium",
                    confidence=0.8,
                    symbol="SPY",
                    market_type="equity",
                    metadata={
                        "arithmetic_mean": drain["arithmetic_mean"],
                        "geometric_mean": drain["geometric_mean"],
                        "volatility_drain": vol_drain,
                        "framework": "spitznagel",
                    },
                ))

        except Exception as e:
            logger.warning(f"Volatility drain check failed: {e}")

        return findings

    def _check_haven_instruments(self) -> List[Dict]:
        findings = []
        havens = {"^VIX": "VIX (volatility)", "GLD": "Gold", "TLT": "Long Treasury Bonds"}

        for symbol, label in havens.items():
            try:
                data = self.yahoo.get_price_data(symbol, period="3mo")
                if data is None or len(data) < 20:
                    continue

                spy_data = self.yahoo.get_price_data("SPY", period="3mo")
                if spy_data is None or len(spy_data) < 20:
                    continue

                # Check correlation with SPY (negative = good hedge)
                min_len = min(len(data), len(spy_data))
                haven_returns = data["Close"].pct_change().dropna().tail(min_len - 1)
                spy_returns = spy_data["Close"].pct_change().dropna().tail(min_len - 1)

                if len(haven_returns) > 10 and len(spy_returns) > 10:
                    aligned_len = min(len(haven_returns), len(spy_returns))
                    correlation = float(np.corrcoef(
                        haven_returns.values[-aligned_len:],
                        spy_returns.values[-aligned_len:]
                    )[0, 1])

                    if correlation < -0.3:
                        findings.append(self.create_finding(
                            title=f"Effective Safe Haven: {label} (correlation: {correlation:.2f})",
                            description=(
                                f"{label} shows strong negative correlation ({correlation:.2f}) with SPY. "
                                "This makes it an effective convex hedge. "
                                "Consider a small allocation for crash protection."
                            ),
                            severity="low",
                            confidence=0.7,
                            symbol=symbol,
                            market_type="hedge",
                            metadata={
                                "correlation_with_spy": correlation,
                                "framework": "spitznagel",
                                "signal": "effective_haven",
                            },
                        ))

            except Exception as e:
                logger.warning(f"Haven check failed for {symbol}: {e}")

        return findings

    def _check_bernoulli_falls(self) -> List[Dict]:
        """Check historical drawdown severity for Bernoulli Falls illustration."""
        findings = []
        try:
            data = self.yahoo.get_price_data("SPY", period="5y")
            if data is None or len(data) < 252:
                return findings

            prices = data["Close"]
            peak = prices.expanding().max()
            drawdown = (prices - peak) / peak
            max_dd = float(drawdown.min())

            if max_dd < -0.20:
                recovery = self.simulator.bernoulli_falls(abs(max_dd))
                findings.append(self.create_finding(
                    title=f"Bernoulli Falls: Max 5Y Drawdown of {abs(max_dd)*100:.1f}%",
                    description=(
                        f"SPY experienced a {abs(max_dd)*100:.1f}% peak-to-trough drawdown in the past 5 years. "
                        f"Recovery required: {recovery['recovery_needed_pct']*100:.1f}%. "
                        f"Estimated {recovery['years_to_recover_at_10pct']} years to recover at 10% annual returns. "
                        "A 3% safe haven allocation would have dramatically reduced this drawdown."
                    ),
                    severity="medium",
                    confidence=0.85,
                    symbol="SPY",
                    market_type="equity",
                    metadata={
                        "max_drawdown_5y": max_dd,
                        "recovery_needed": recovery["recovery_needed_pct"],
                        "framework": "spitznagel",
                        "signal": "bernoulli_falls",
                    },
                ))

        except Exception as e:
            logger.warning(f"Bernoulli Falls check failed: {e}")

        return findings


# ---------------------------------------------------------------------------
# Simons Agent: Pattern Recognition
# ---------------------------------------------------------------------------

class SimonsPatternAgent(BaseAgent):
    """
    High-Frequency Quant - detects non-random statistical patterns,
    mean reversion signals, and regime changes in market data.
    """

    def __init__(self):
        super().__init__(name="SimonsPatternAgent")
        self.yahoo = YahooFinanceClient()
        self.detector = PatternDetector()

    # Instruments to scan for patterns
    SCAN_UNIVERSE = [
        "SPY", "QQQ", "IWM", "EEM",  # Indices
        "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL",  # Mega-caps
        "GLD", "TLT", "^VIX",  # Alternatives
        "BTC-USD", "ETH-USD",  # Crypto
    ]

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        for symbol in self.SCAN_UNIVERSE:
            try:
                data = self.yahoo.get_price_data(symbol, period="6mo")
                if data is None or len(data) < 60:
                    continue

                prices = data["Close"]
                returns = prices.pct_change().dropna()

                # Mean reversion detection
                mr_result = self.detector.detect_mean_reversion(prices)
                if mr_result.get("signal") in ("overextended_long", "overextended_short"):
                    findings.append(self._mean_reversion_finding(symbol, mr_result))

                # Autocorrelation detection
                ac_result = self.detector.detect_autocorrelation(returns)
                if ac_result.get("exploitable"):
                    findings.append(self._autocorrelation_finding(symbol, ac_result))

                # Regime change detection
                rc_result = self.detector.detect_regime_change(prices)
                if rc_result.get("regime_change"):
                    findings.append(self._regime_change_finding(symbol, rc_result))

            except Exception as e:
                logger.warning(f"Pattern scan failed for {symbol}: {e}")

        return findings

    def _mean_reversion_finding(self, symbol: str, result: Dict) -> Dict:
        signal = result["signal"]
        z = result["current_z_score"]
        direction = "short" if signal == "overextended_long" else "long"

        return self.create_finding(
            title=f"Mean Reversion Signal: {symbol} ({direction.upper()})",
            description=(
                f"Z-score: {z:.2f} (threshold: {result['z_threshold']}). "
                f"Signal: {signal}. "
                f"Half-life: {result.get('half_life_periods', 'N/A')} periods. "
                "Statistical evidence of price deviation from mean. "
                "No narrative explanation required - pattern is the signal."
            ),
            severity="medium",
            confidence=min(0.9, 0.5 + abs(z) * 0.1),
            symbol=symbol,
            market_type="equity" if not symbol.endswith("-USD") else "crypto",
            metadata={**result, "framework": "simons", "signal_type": "mean_reversion"},
        )

    def _autocorrelation_finding(self, symbol: str, result: Dict) -> Dict:
        lags = result["significant_lags"]
        return self.create_finding(
            title=f"Autocorrelation Detected: {symbol} (lags: {lags})",
            description=(
                f"Statistically significant serial correlation at lags {lags}. "
                f"Strongest: {result['strongest_lag']}. "
                "This non-randomness suggests exploitable pattern. "
                "Returns are not independently distributed as EMH assumes."
            ),
            severity="medium",
            confidence=0.7,
            symbol=symbol,
            market_type="equity" if not symbol.endswith("-USD") else "crypto",
            metadata={**result, "framework": "simons", "signal_type": "autocorrelation"},
        )

    def _regime_change_finding(self, symbol: str, result: Dict) -> Dict:
        cross = result["crossover_type"]
        return self.create_finding(
            title=f"Regime Change: {symbol} ({cross.upper()} Crossover)",
            description=(
                f"Moving average crossover detected: {cross}. "
                f"Volatility regime: {result['vol_regime']} "
                f"(recent vol: {result['recent_volatility']:.1%}, "
                f"historical: {result['historical_volatility']:.1%}). "
                "Regime transitions are where most alpha is captured or lost."
            ),
            severity="high" if result["vol_regime"] == "high" else "medium",
            confidence=0.75,
            symbol=symbol,
            market_type="equity" if not symbol.endswith("-USD") else "crypto",
            metadata={**result, "framework": "simons", "signal_type": "regime_change"},
        )


# ---------------------------------------------------------------------------
# Asness Agent: Factor Analysis
# ---------------------------------------------------------------------------

class AssnessFactorAgent(BaseAgent):
    """
    Disciplined Contrarian - evaluates markets through Value and Momentum
    factor lenses, identifies behavioral biases, and enforces systematic discipline.
    """

    def __init__(self):
        super().__init__(name="AssnessFactorAgent")
        self.yahoo = YahooFinanceClient()
        self.factor_analyzer = FactorAnalyzer()

    FACTOR_UNIVERSE = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
        "JPM", "V", "JNJ", "PG", "XOM", "CVX", "BAC",
    ]

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        # 1. Individual stock factor analysis
        findings.extend(self._scan_factor_universe())

        # 2. Value-Momentum spread analysis
        findings.extend(self._check_value_momentum_spread())

        # 3. Behavioral bias detection (market-level)
        findings.extend(self._detect_behavioral_biases())

        return findings

    def _scan_factor_universe(self) -> List[Dict]:
        findings = []

        for symbol in self.FACTOR_UNIVERSE:
            try:
                info = self.yahoo.get_ticker_info(symbol)
                if info is None:
                    continue

                # Value analysis
                value_result = self.factor_analyzer.value_score(
                    pe_ratio=info.get("pe_ratio"),
                    dividend_yield=info.get("dividend_yield") if info.get("dividend_yield") else None,
                )
                if "error" in value_result:
                    continue

                # Momentum analysis
                price_data = self.yahoo.get_price_data(symbol, period="1y")
                if price_data is None or len(price_data) < 252:
                    continue

                mom_result = self.factor_analyzer.momentum_score(price_data["Close"])
                if "error" in mom_result:
                    continue

                # Combined analysis
                spread = self.factor_analyzer.value_momentum_spread(
                    value_result["composite_value_score"],
                    mom_result["momentum_return"],
                )

                # Only report interesting cases
                if spread["regime"] in ("VALUE_MOMENTUM_ALIGNED", "VALUE_TRAP_RISK"):
                    severity = "high" if spread["regime"] == "VALUE_MOMENTUM_ALIGNED" else "medium"
                    findings.append(self.create_finding(
                        title=f"Factor Signal: {symbol} - {spread['regime']}",
                        description=(
                            f"Value: {value_result['classification']} "
                            f"(score: {value_result['composite_value_score']:.2f}). "
                            f"Momentum: {mom_result['classification']} "
                            f"(12-1: {mom_result['momentum_return']:.1%}). "
                            f"Combined regime: {spread['regime']}. "
                            f"Conviction: {spread['conviction']}."
                        ),
                        severity=severity,
                        confidence=0.7 if spread["conviction"] == "high" else 0.5,
                        symbol=symbol,
                        market_type="equity",
                        metadata={
                            "value": value_result,
                            "momentum": mom_result,
                            "spread": spread,
                            "framework": "asness",
                        },
                    ))

            except Exception as e:
                logger.warning(f"Factor scan failed for {symbol}: {e}")

        return findings

    def _check_value_momentum_spread(self) -> List[Dict]:
        """Check the broad Value vs Growth spread."""
        findings = []
        try:
            # IWD (value) vs IWF (growth)
            value_data = self.yahoo.get_price_data("IWD", period="1y")
            growth_data = self.yahoo.get_price_data("IWF", period="1y")

            if value_data is None or growth_data is None:
                return findings
            if len(value_data) < 252 or len(growth_data) < 252:
                return findings

            value_return = float(value_data["Close"].iloc[-1] / value_data["Close"].iloc[0]) - 1
            growth_return = float(growth_data["Close"].iloc[-1] / growth_data["Close"].iloc[0]) - 1
            spread = value_return - growth_return

            if abs(spread) > 0.10:
                leader = "Value" if spread > 0 else "Growth"
                findings.append(self.create_finding(
                    title=f"Value-Growth Spread: {leader} Leading by {abs(spread)*100:.1f}%",
                    description=(
                        f"Value (IWD) 1Y return: {value_return*100:.1f}%. "
                        f"Growth (IWF) 1Y return: {growth_return*100:.1f}%. "
                        f"Spread: {spread*100:.1f}%. "
                        "Wide spreads historically mean-revert. "
                        "Consider tilting toward the lagging factor."
                    ),
                    severity="medium",
                    confidence=0.7,
                    market_type="equity",
                    metadata={
                        "value_return": value_return,
                        "growth_return": growth_return,
                        "spread": spread,
                        "framework": "asness",
                        "signal": "value_growth_spread",
                    },
                ))

        except Exception as e:
            logger.warning(f"Value-momentum spread check failed: {e}")

        return findings

    def _detect_behavioral_biases(self) -> List[Dict]:
        """Detect market-level behavioral biases."""
        findings = []
        try:
            spy_data = self.yahoo.get_price_data("SPY", period="6mo")
            if spy_data is None or len(spy_data) < 60:
                return findings

            returns = spy_data["Close"].pct_change().dropna()

            # Check for herding (low dispersion = everyone doing the same thing)
            recent_vol = float(returns.tail(10).std()) * math.sqrt(252)
            historical_vol = float(returns.std()) * math.sqrt(252)

            if recent_vol < historical_vol * 0.5:
                findings.append(self.create_finding(
                    title="Behavioral Alert: Herding Detected (Low Dispersion)",
                    description=(
                        f"Recent 10-day volatility ({recent_vol:.1%}) is less than half "
                        f"of 6-month volatility ({historical_vol:.1%}). "
                        "This compression suggests herding behavior. "
                        "Markets in herding mode are vulnerable to sharp reversals "
                        "when the consensus breaks."
                    ),
                    severity="medium",
                    confidence=0.65,
                    symbol="SPY",
                    market_type="equity",
                    metadata={
                        "recent_vol": recent_vol,
                        "historical_vol": historical_vol,
                        "framework": "asness",
                        "signal": "herding",
                    },
                ))

            # Check for momentum crash risk (extreme momentum = vulnerable)
            mom_12m = float(spy_data["Close"].iloc[-1] / spy_data["Close"].iloc[0]) - 1
            if mom_12m > 0.25:
                findings.append(self.create_finding(
                    title="Behavioral Alert: Momentum Crash Risk Elevated",
                    description=(
                        f"SPY 6-month momentum: {mom_12m*100:.1f}%. "
                        "Extended momentum runs historically end with sharp reversals. "
                        "This is not a timing signal - but a discipline check. "
                        "Ensure positions are sized for a momentum crash scenario."
                    ),
                    severity="medium",
                    confidence=0.6,
                    symbol="SPY",
                    market_type="equity",
                    metadata={
                        "momentum_6m": mom_12m,
                        "framework": "asness",
                        "signal": "momentum_crash_risk",
                    },
                ))

        except Exception as e:
            logger.warning(f"Behavioral bias detection failed: {e}")

        return findings


# ---------------------------------------------------------------------------
# Board Coordinator: Full Council Protocol Orchestration
# ---------------------------------------------------------------------------

class AntifragileBoardAgent(BaseAgent):
    """
    Meta-agent that orchestrates the full Antifragile Board deliberation.

    When run as a scheduled agent, it:
    1. Collects findings from all four specialist agents
    2. Runs the Council Protocol (Divergence -> Convergence -> Synthesis)
    3. Produces a synthesized board report as a finding
    """

    def __init__(self):
        super().__init__(name="AntifragileBoardAgent")
        self.taleb = TalebFragilityAgent()
        self.spitznagel = SpitznagelSafeHavenAgent()
        self.simons = SimonsPatternAgent()
        self.asness = AssnessFactorAgent()

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        # Collect findings from all specialist agents
        all_specialist_findings = []
        for agent in [self.taleb, self.spitznagel, self.simons, self.asness]:
            try:
                agent_findings = agent.analyze()
                all_specialist_findings.extend(agent_findings)
                findings.extend(agent_findings)
            except Exception as e:
                logger.error(f"Specialist agent {agent.name} failed: {e}")

        # Build a summary for the Council Protocol
        if all_specialist_findings:
            summary = self._build_summary(all_specialist_findings)
            findings.append(self.create_finding(
                title="Antifragile Board Summary",
                description=summary,
                severity=self._aggregate_severity(all_specialist_findings),
                confidence=0.8,
                market_type="multi-asset",
                metadata={
                    "framework": "antifragile_board",
                    "specialist_count": 4,
                    "finding_count": len(all_specialist_findings),
                    "frameworks": ["taleb", "spitznagel", "simons", "asness"],
                },
            ))

        return findings

    def _build_summary(self, findings: List[Dict]) -> str:
        """Build a structured summary of all specialist findings."""
        by_framework = {}
        for f in findings:
            fw = f.get("metadata", {}).get("framework", "unknown")
            by_framework.setdefault(fw, []).append(f)

        parts = ["ANTIFRAGILE BOARD REPORT", "=" * 40]

        framework_labels = {
            "taleb": "TALEB (Risk Epistemology)",
            "spitznagel": "SPITZNAGEL (Safe Haven)",
            "simons": "SIMONS (Pattern Recognition)",
            "asness": "ASNESS (Factor Discipline)",
        }

        for fw, label in framework_labels.items():
            fw_findings = by_framework.get(fw, [])
            parts.append(f"\n{label}: {len(fw_findings)} signals")
            for f in fw_findings[:3]:  # Top 3 per framework
                parts.append(f"  - [{f.get('severity', '?').upper()}] {f.get('title', 'N/A')}")

        critical = [f for f in findings if f.get("severity") == "critical"]
        high = [f for f in findings if f.get("severity") == "high"]
        parts.append(f"\nOVERALL: {len(critical)} critical, {len(high)} high-severity signals")

        return "\n".join(parts)

    def _aggregate_severity(self, findings: List[Dict]) -> str:
        severities = [f.get("severity", "low") for f in findings]
        if "critical" in severities:
            return "critical"
        elif "high" in severities:
            return "high"
        elif "medium" in severities:
            return "medium"
        return "low"

    def deliberate(self, query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Run a full Council Protocol deliberation on a specific query.
        This is used by the API/UI, not the scheduled agent run.

        Args:
            query: Investment thesis or business model to evaluate
            context: Optional market data context

        Returns:
            Full deliberation results
        """
        return quick_deliberate(query, context, peer_review=True)
