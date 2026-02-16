"""
Specialized Financial Tools for the Antifragile Board

Provides analytical instruments for each board member persona:
- GeometricSimulator: Drawdown/CAGR impact analysis (Spitznagel)
- FragilityScorer: System fragility detection via concentration & leverage (Taleb)
- PatternDetector: Statistical anomaly & mean-reversion detection (Simons)
- FactorAnalyzer: Value/Momentum factor decomposition (Asness)
- AmbiguityScorer: Strategic ambiguity detection in text (cross-agent)
"""

import math
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Geometric Simulator (Spitznagel)
# ---------------------------------------------------------------------------

class GeometricSimulator:
    """
    Simulates the impact of drawdowns on compound growth (CAGR).
    Demonstrates the 'Bernoulli Falls' - how losses have a disproportionate
    impact on geometric returns vs arithmetic returns.
    """

    @staticmethod
    def bernoulli_falls(drawdown_pct: float) -> Dict[str, float]:
        """
        Calculate the recovery required and CAGR impact of a drawdown.

        Args:
            drawdown_pct: Drawdown as a decimal (e.g., 0.50 for 50% loss)

        Returns:
            Dict with recovery metrics
        """
        if drawdown_pct <= 0 or drawdown_pct >= 1.0:
            return {"error": "drawdown must be between 0 and 1 exclusive"}

        recovery_needed = (1.0 / (1.0 - drawdown_pct)) - 1.0
        # Years to recover at 10% annual return
        years_to_recover = math.log(1.0 / (1.0 - drawdown_pct)) / math.log(1.10)

        return {
            "drawdown_pct": drawdown_pct,
            "recovery_needed_pct": recovery_needed,
            "years_to_recover_at_10pct": round(years_to_recover, 1),
            "wealth_remaining": 1.0 - drawdown_pct,
            "volatility_drag": drawdown_pct ** 2 / 2,  # Approximation
        }

    @staticmethod
    def safe_haven_frontier(
        portfolio_return: float,
        portfolio_vol: float,
        haven_allocation: float = 0.03,
        haven_crash_payoff: float = 10.0,
        crash_probability: float = 0.05,
        crash_severity: float = -0.40,
        n_simulations: int = 10000,
    ) -> Dict[str, Any]:
        """
        Simulate the Safe Haven Frontier: a portfolio with a small allocation
        to convex crash-protection instruments.

        Args:
            portfolio_return: Expected annual return of the core portfolio
            portfolio_vol: Annual volatility of the core portfolio
            haven_allocation: Fraction allocated to safe haven (e.g., 0.03 = 3%)
            haven_crash_payoff: Multiple return of haven during crash
            crash_probability: Annual probability of a crash
            crash_severity: Return of core portfolio during crash
            n_simulations: Number of Monte Carlo paths

        Returns:
            Comparison of protected vs unprotected portfolio metrics
        """
        rng = np.random.default_rng(42)
        years = 10
        core_alloc = 1.0 - haven_allocation
        haven_annual_cost = -0.90  # Safe haven decays 90% in normal years

        # Simulate paths
        protected_terminal = []
        unprotected_terminal = []

        for _ in range(n_simulations):
            protected_wealth = 1.0
            unprotected_wealth = 1.0

            for _ in range(years):
                is_crash = rng.random() < crash_probability
                if is_crash:
                    core_return = crash_severity
                    haven_return = haven_crash_payoff
                else:
                    core_return = rng.normal(portfolio_return, portfolio_vol)
                    haven_return = haven_annual_cost

                # Unprotected
                unprotected_wealth *= (1.0 + core_return)

                # Protected (barbell)
                core_pnl = core_alloc * core_return
                haven_pnl = haven_allocation * haven_return
                protected_wealth *= (1.0 + core_pnl + haven_pnl)

            protected_terminal.append(protected_wealth)
            unprotected_terminal.append(unprotected_wealth)

        protected_arr = np.array(protected_terminal)
        unprotected_arr = np.array(unprotected_terminal)

        def _cagr(terminal_values: np.ndarray, years: int) -> float:
            median = float(np.median(terminal_values))
            if median <= 0:
                return -1.0
            return median ** (1.0 / years) - 1.0

        def _max_drawdown_estimate(terminal_values: np.ndarray) -> float:
            return float(1.0 - np.percentile(terminal_values, 5))

        return {
            "protected": {
                "median_terminal_wealth": float(np.median(protected_arr)),
                "cagr": _cagr(protected_arr, years),
                "worst_5pct": float(np.percentile(protected_arr, 5)),
                "best_5pct": float(np.percentile(protected_arr, 95)),
                "survival_rate": float(np.mean(protected_arr > 0.5)),
            },
            "unprotected": {
                "median_terminal_wealth": float(np.median(unprotected_arr)),
                "cagr": _cagr(unprotected_arr, years),
                "worst_5pct": float(np.percentile(unprotected_arr, 5)),
                "best_5pct": float(np.percentile(unprotected_arr, 95)),
                "survival_rate": float(np.mean(unprotected_arr > 0.5)),
            },
            "haven_allocation": haven_allocation,
            "years_simulated": years,
            "n_simulations": n_simulations,
        }

    @staticmethod
    def volatility_drain(returns: List[float]) -> Dict[str, float]:
        """
        Calculate the gap between arithmetic and geometric average returns,
        demonstrating the 'volatility tax'.

        Args:
            returns: List of periodic returns (e.g., annual)

        Returns:
            Dict with arithmetic mean, geometric mean, and the drain
        """
        if not returns:
            return {"error": "empty returns"}

        arithmetic_mean = sum(returns) / len(returns)

        # Geometric mean
        product = 1.0
        for r in returns:
            product *= (1.0 + r)
        geometric_mean = product ** (1.0 / len(returns)) - 1.0

        variance = sum((r - arithmetic_mean) ** 2 for r in returns) / len(returns)

        return {
            "arithmetic_mean": arithmetic_mean,
            "geometric_mean": geometric_mean,
            "volatility_drain": arithmetic_mean - geometric_mean,
            "variance": variance,
            "approx_drain": variance / 2,  # Theoretical approximation
        }


# ---------------------------------------------------------------------------
# Fragility Scorer (Taleb)
# ---------------------------------------------------------------------------

class FragilityScorer:
    """
    Evaluates the fragility of a business strategy, portfolio position, or
    system design using Taleb's principles: concentration risk, leverage,
    Lindy compliance, skin-in-the-game checks, and fat-tail exposure.
    """

    @staticmethod
    def score_fragility(
        leverage_ratio: float = 1.0,
        concentration_pct: float = 0.0,
        years_of_operation: int = 0,
        has_skin_in_game: bool = True,
        relies_on_forecasting: bool = False,
        revenue_sources: int = 1,
        debt_to_equity: float = 0.0,
        tail_exposure: str = "unknown",  # "long_tail", "short_tail", "neutral"
    ) -> Dict[str, Any]:
        """
        Compute a composite fragility score (0 = antifragile, 100 = extremely fragile).

        Returns:
            Dict with fragility score, breakdown, and recommendations
        """
        penalties = {}
        score = 0.0

        # Leverage penalty (exponential - fragility is convex to leverage)
        lev_penalty = min(30.0, (leverage_ratio - 1.0) ** 2 * 10) if leverage_ratio > 1 else 0
        penalties["leverage"] = lev_penalty
        score += lev_penalty

        # Concentration penalty
        conc_penalty = min(25.0, concentration_pct * 50)
        penalties["concentration"] = conc_penalty
        score += conc_penalty

        # Lindy penalty (newer = more fragile)
        if years_of_operation < 2:
            lindy_penalty = 15.0
        elif years_of_operation < 5:
            lindy_penalty = 10.0
        elif years_of_operation < 10:
            lindy_penalty = 5.0
        else:
            lindy_penalty = 0.0
        penalties["lindy_deficit"] = lindy_penalty
        score += lindy_penalty

        # Skin in the game
        if not has_skin_in_game:
            penalties["no_skin_in_game"] = 15.0
            score += 15.0
        else:
            penalties["no_skin_in_game"] = 0.0

        # Forecasting dependency
        if relies_on_forecasting:
            penalties["forecast_dependency"] = 10.0
            score += 10.0
        else:
            penalties["forecast_dependency"] = 0.0

        # Revenue diversification
        if revenue_sources == 1:
            div_penalty = 10.0
        elif revenue_sources <= 3:
            div_penalty = 5.0
        else:
            div_penalty = 0.0
        penalties["revenue_concentration"] = div_penalty
        score += div_penalty

        # Debt burden
        debt_penalty = min(15.0, max(0, debt_to_equity - 0.5) * 10)
        penalties["debt_burden"] = debt_penalty
        score += debt_penalty

        # Tail exposure
        tail_penalties = {"short_tail": 15.0, "neutral": 5.0, "long_tail": -5.0, "unknown": 10.0}
        tail_p = tail_penalties.get(tail_exposure, 10.0)
        penalties["tail_exposure"] = max(0, tail_p)
        score += tail_p

        score = max(0, min(100, score))

        # Classification
        if score >= 70:
            classification = "EXTREMELY FRAGILE"
        elif score >= 50:
            classification = "FRAGILE"
        elif score >= 30:
            classification = "ROBUST"
        elif score >= 15:
            classification = "RESILIENT"
        else:
            classification = "ANTIFRAGILE"

        recommendations = []
        if penalties.get("leverage", 0) > 10:
            recommendations.append("Reduce leverage - fragility is convex to debt")
        if penalties.get("concentration", 0) > 10:
            recommendations.append("Diversify exposure - single-point-of-failure risk")
        if not has_skin_in_game:
            recommendations.append("Require decision-makers to share downside risk")
        if relies_on_forecasting:
            recommendations.append("Replace forecasting with optionality-based strategies")
        if penalties.get("tail_exposure", 0) > 10:
            recommendations.append("Add convex hedges for tail risk protection")

        return {
            "fragility_score": round(score, 1),
            "classification": classification,
            "penalties": penalties,
            "recommendations": recommendations,
        }

    @staticmethod
    def lindy_check(concept: str, years_existed: int) -> Dict[str, Any]:
        """
        Apply the Lindy Effect: the longer something non-perishable has survived,
        the longer its remaining life expectancy.

        Args:
            concept: Name of the concept/strategy/technology
            years_existed: How long it has been in existence

        Returns:
            Lindy assessment
        """
        if years_existed <= 0:
            expected_remaining = 0
            confidence = "very_low"
        elif years_existed < 5:
            expected_remaining = years_existed
            confidence = "low"
        elif years_existed < 20:
            expected_remaining = years_existed
            confidence = "moderate"
        elif years_existed < 100:
            expected_remaining = years_existed
            confidence = "high"
        else:
            expected_remaining = years_existed
            confidence = "very_high"

        return {
            "concept": concept,
            "years_existed": years_existed,
            "expected_remaining_years": expected_remaining,
            "lindy_confidence": confidence,
            "lindy_compliant": years_existed >= 10,
        }


# ---------------------------------------------------------------------------
# Pattern Detector (Simons)
# ---------------------------------------------------------------------------

class PatternDetector:
    """
    Statistical pattern detection engine inspired by Renaissance Technologies.
    Identifies non-random patterns, mean reversion signals, and anomalies
    in market data without attempting to explain 'why'.
    """

    @staticmethod
    def detect_mean_reversion(
        prices: pd.Series,
        lookback: int = 20,
        z_threshold: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Detect mean reversion opportunities using z-score analysis.

        Args:
            prices: Price series
            lookback: Rolling window for mean/std
            z_threshold: Z-score threshold for signal generation

        Returns:
            Mean reversion signal data
        """
        if len(prices) < lookback + 5:
            return {"signal": "insufficient_data"}

        rolling_mean = prices.rolling(window=lookback).mean()
        rolling_std = prices.rolling(window=lookback).std()

        # Avoid division by zero
        rolling_std = rolling_std.replace(0, np.nan)

        z_scores = (prices - rolling_mean) / rolling_std
        current_z = float(z_scores.iloc[-1]) if not np.isnan(z_scores.iloc[-1]) else 0.0

        signal = "neutral"
        if current_z > z_threshold:
            signal = "overextended_long"
        elif current_z < -z_threshold:
            signal = "overextended_short"

        # Half-life of mean reversion (Ornstein-Uhlenbeck)
        try:
            log_prices = np.log(prices.dropna())
            lagged = log_prices.shift(1).dropna()
            current = log_prices.iloc[1:]
            if len(lagged) > 10 and len(current) > 10:
                lagged_aligned = lagged.iloc[:len(current)]
                delta = current.values - lagged_aligned.values
                from numpy.linalg import lstsq
                A = lagged_aligned.values.reshape(-1, 1)
                b = delta
                result = lstsq(A, b, rcond=None)
                theta = -result[0][0]
                half_life = math.log(2) / theta if theta > 0 else float('inf')
            else:
                half_life = float('inf')
        except Exception:
            half_life = float('inf')

        return {
            "signal": signal,
            "current_z_score": round(current_z, 3),
            "z_threshold": z_threshold,
            "half_life_periods": round(half_life, 1) if half_life != float('inf') else None,
            "mean_reverting": half_life < lookback * 2,
            "rolling_mean": float(rolling_mean.iloc[-1]) if not np.isnan(rolling_mean.iloc[-1]) else None,
            "rolling_std": float(rolling_std.iloc[-1]) if not np.isnan(rolling_std.iloc[-1]) else None,
        }

    @staticmethod
    def detect_autocorrelation(
        returns: pd.Series,
        max_lags: int = 10,
    ) -> Dict[str, Any]:
        """
        Detect serial autocorrelation in returns, which suggests
        non-random (exploitable) patterns.

        Args:
            returns: Return series
            max_lags: Maximum number of lags to test

        Returns:
            Autocorrelation analysis
        """
        if len(returns) < max_lags + 20:
            return {"exploitable": False, "reason": "insufficient_data"}

        autocorrelations = {}
        significant_lags = []
        threshold = 2.0 / math.sqrt(len(returns))  # 95% CI

        for lag in range(1, max_lags + 1):
            corr = float(returns.autocorr(lag=lag))
            autocorrelations[f"lag_{lag}"] = round(corr, 4)
            if abs(corr) > threshold:
                significant_lags.append(lag)

        return {
            "autocorrelations": autocorrelations,
            "significant_lags": significant_lags,
            "exploitable": len(significant_lags) > 0,
            "significance_threshold": round(threshold, 4),
            "strongest_lag": max(autocorrelations, key=lambda k: abs(autocorrelations[k]))
            if autocorrelations else None,
        }

    @staticmethod
    def detect_regime_change(
        prices: pd.Series,
        short_window: int = 10,
        long_window: int = 50,
    ) -> Dict[str, Any]:
        """
        Detect potential regime changes using dual moving average crossovers
        and volatility clustering.

        Args:
            prices: Price series
            short_window: Short-term MA window
            long_window: Long-term MA window

        Returns:
            Regime change analysis
        """
        if len(prices) < long_window + 10:
            return {"regime_change": False, "reason": "insufficient_data"}

        short_ma = prices.rolling(window=short_window).mean()
        long_ma = prices.rolling(window=long_window).mean()

        # Current state
        current_short = float(short_ma.iloc[-1])
        current_long = float(long_ma.iloc[-1])
        prev_short = float(short_ma.iloc[-2])
        prev_long = float(long_ma.iloc[-2])

        # Crossover detection
        bullish_cross = prev_short <= prev_long and current_short > current_long
        bearish_cross = prev_short >= prev_long and current_short < current_long

        # Volatility regime
        returns = prices.pct_change().dropna()
        recent_vol = float(returns.tail(short_window).std()) * math.sqrt(252)
        historical_vol = float(returns.tail(long_window).std()) * math.sqrt(252)
        vol_ratio = recent_vol / historical_vol if historical_vol > 0 else 1.0

        return {
            "regime_change": bullish_cross or bearish_cross,
            "crossover_type": "bullish" if bullish_cross else ("bearish" if bearish_cross else "none"),
            "trend_state": "bullish" if current_short > current_long else "bearish",
            "recent_volatility": round(recent_vol, 4),
            "historical_volatility": round(historical_vol, 4),
            "vol_ratio": round(vol_ratio, 3),
            "vol_regime": "high" if vol_ratio > 1.5 else ("low" if vol_ratio < 0.7 else "normal"),
        }


# ---------------------------------------------------------------------------
# Factor Analyzer (Asness)
# ---------------------------------------------------------------------------

class FactorAnalyzer:
    """
    Value/Momentum factor analysis inspired by AQR Capital Management.
    Computes factor exposures, identifies value traps vs genuine cheapness,
    and measures momentum persistence.
    """

    @staticmethod
    def value_score(
        pe_ratio: Optional[float] = None,
        pb_ratio: Optional[float] = None,
        dividend_yield: Optional[float] = None,
        fcf_yield: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Compute a composite value score. Lower = cheaper (more attractive).

        Returns:
            Value assessment with z-score style ranking
        """
        scores = {}
        weights = {}

        # Market medians for reference
        medians = {"pe": 20.0, "pb": 3.0, "div_yield": 0.02, "fcf_yield": 0.05}

        if pe_ratio is not None and pe_ratio > 0:
            pe_z = (pe_ratio - medians["pe"]) / medians["pe"]
            scores["pe_score"] = pe_z
            weights["pe_score"] = 0.3

        if pb_ratio is not None and pb_ratio > 0:
            pb_z = (pb_ratio - medians["pb"]) / medians["pb"]
            scores["pb_score"] = pb_z
            weights["pb_score"] = 0.2

        if dividend_yield is not None:
            div_z = -(dividend_yield - medians["div_yield"]) / medians["div_yield"]
            scores["dividend_score"] = div_z
            weights["dividend_score"] = 0.2

        if fcf_yield is not None:
            fcf_z = -(fcf_yield - medians["fcf_yield"]) / medians["fcf_yield"]
            scores["fcf_score"] = fcf_z
            weights["fcf_score"] = 0.3

        if not scores:
            return {"error": "no valid inputs"}

        # Weighted composite
        total_weight = sum(weights.values())
        composite = sum(scores[k] * weights[k] for k in scores) / total_weight

        if composite < -0.3:
            classification = "DEEP_VALUE"
        elif composite < 0:
            classification = "VALUE"
        elif composite < 0.3:
            classification = "FAIR"
        elif composite < 0.8:
            classification = "EXPENSIVE"
        else:
            classification = "EXTREMELY_EXPENSIVE"

        return {
            "composite_value_score": round(composite, 3),
            "classification": classification,
            "factor_scores": {k: round(v, 3) for k, v in scores.items()},
            "inputs": {
                "pe_ratio": pe_ratio,
                "pb_ratio": pb_ratio,
                "dividend_yield": dividend_yield,
                "fcf_yield": fcf_yield,
            },
        }

    @staticmethod
    def momentum_score(
        prices: pd.Series,
        lookback_months: int = 12,
        skip_recent: int = 1,
    ) -> Dict[str, Any]:
        """
        Compute momentum score (12-1 month momentum is the classic AQR factor).

        Args:
            prices: Daily price series
            lookback_months: Total lookback period in months
            skip_recent: Months to skip (avoids short-term reversal)

        Returns:
            Momentum analysis
        """
        if len(prices) < lookback_months * 21:
            return {"error": "insufficient price history"}

        total_days = lookback_months * 21
        skip_days = skip_recent * 21

        # 12-1 momentum: return from T-252 to T-21
        start_price = float(prices.iloc[-total_days])
        end_price = float(prices.iloc[-skip_days]) if skip_days > 0 else float(prices.iloc[-1])

        momentum_return = (end_price / start_price) - 1.0

        # Recent 1-month return (for reversal check)
        recent_price = float(prices.iloc[-1])
        month_ago_price = float(prices.iloc[-skip_days]) if skip_days > 0 else float(prices.iloc[-21])
        recent_return = (recent_price / month_ago_price) - 1.0

        # Momentum persistence (are returns accelerating or decelerating?)
        half = total_days // 2
        first_half_return = (float(prices.iloc[-half]) / start_price) - 1.0
        second_half_return = (end_price / float(prices.iloc[-half])) - 1.0

        if momentum_return > 0.20:
            classification = "STRONG_MOMENTUM"
        elif momentum_return > 0.05:
            classification = "MODERATE_MOMENTUM"
        elif momentum_return > -0.05:
            classification = "FLAT"
        elif momentum_return > -0.20:
            classification = "MODERATE_REVERSAL"
        else:
            classification = "STRONG_REVERSAL"

        return {
            "momentum_return": round(momentum_return, 4),
            "recent_return": round(recent_return, 4),
            "classification": classification,
            "persistence": "accelerating" if second_half_return > first_half_return else "decelerating",
            "first_half_return": round(first_half_return, 4),
            "second_half_return": round(second_half_return, 4),
        }

    @staticmethod
    def value_momentum_spread(
        value_score: float,
        momentum_score: float,
    ) -> Dict[str, Any]:
        """
        Analyze the interaction between value and momentum factors.
        Their negative correlation is a key diversification benefit.

        Args:
            value_score: Composite value score (negative = cheap)
            momentum_score: Momentum return

        Returns:
            Combined factor analysis
        """
        # Value: negative score = cheap = attractive
        # Momentum: positive = strong momentum = attractive
        value_signal = -value_score  # Flip so positive = attractive
        momentum_signal = momentum_score

        combined = (value_signal + momentum_signal) / 2

        if value_signal > 0 and momentum_signal > 0:
            regime = "VALUE_MOMENTUM_ALIGNED"
            conviction = "high"
        elif value_signal > 0 and momentum_signal < 0:
            regime = "VALUE_TRAP_RISK"
            conviction = "low"
        elif value_signal < 0 and momentum_signal > 0:
            regime = "EXPENSIVE_WITH_MOMENTUM"
            conviction = "moderate"
        else:
            regime = "AVOID"
            conviction = "high"

        return {
            "combined_signal": round(combined, 3),
            "value_signal": round(value_signal, 3),
            "momentum_signal": round(momentum_signal, 3),
            "regime": regime,
            "conviction": conviction,
            "natural_hedge": "Value and momentum are negatively correlated - "
                            "combining them reduces portfolio volatility.",
        }


# ---------------------------------------------------------------------------
# Strategic Ambiguity Scorer (Cross-Agent)
# ---------------------------------------------------------------------------

class AmbiguityScorer:
    """
    Detects strategic ambiguity in text - when organizations deliberately
    use vague language to obscure information. High scores indicate
    hidden fragility.
    """

    HEDGE_WORDS = [
        "may", "might", "could", "possibly", "potentially", "approximately",
        "generally", "typically", "substantially", "materially", "certain",
        "reasonably", "largely", "somewhat", "partially",
    ]

    HEDGE_PHRASES = [
        "subject to",
    ]

    WEASEL_PHRASES = [
        "going forward", "at this time", "in line with expectations",
        "consistent with", "within the range", "broadly in line",
        "taking into account", "not inconsistent with",
        "in the normal course", "as appropriate",
    ]

    CONFIDENCE_WORDS = [
        "will", "shall", "must", "definitely", "certainly", "precisely",
        "exactly", "specifically", "clearly", "unambiguously",
    ]

    @classmethod
    def score_text(cls, text: str) -> Dict[str, Any]:
        """
        Score text for strategic ambiguity (0 = clear, 100 = highly ambiguous).

        Args:
            text: Text to analyze (e.g., earnings call transcript, strategy doc)

        Returns:
            Ambiguity analysis with score and flagged phrases
        """
        if not text:
            return {"score": 0, "error": "empty text"}

        text_lower = text.lower()
        words = text_lower.split()
        word_count = len(words)

        if word_count < 10:
            return {"score": 0, "warning": "text too short for reliable analysis"}

        # Count hedge words (single words + multi-word phrases)
        hedge_count = sum(1 for w in words if w in cls.HEDGE_WORDS)
        hedge_count += sum(1 for phrase in cls.HEDGE_PHRASES if phrase in text_lower)
        hedge_density = hedge_count / word_count

        # Count weasel phrases
        weasel_count = sum(1 for phrase in cls.WEASEL_PHRASES if phrase in text_lower)

        # Count confidence words (inverse signal)
        confidence_count = sum(1 for w in words if w in cls.CONFIDENCE_WORDS)
        confidence_density = confidence_count / word_count

        # Sentence length variance (longer sentences = more obfuscation potential)
        sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        if len(sentences) > 1:
            sentence_lengths = [len(s.split()) for s in sentences]
            avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths)
        else:
            avg_sentence_length = word_count

        # Composite score
        score = 0.0
        score += min(40, hedge_density * 500)  # Hedge word density
        score += min(25, weasel_count * 5)  # Weasel phrase count
        score -= min(15, confidence_density * 300)  # Confidence discount
        score += min(20, max(0, avg_sentence_length - 15) * 1.5)  # Long sentences
        score = max(0, min(100, score))

        flagged_hedges = [w for w in words if w in cls.HEDGE_WORDS][:10]
        flagged_hedges += [p for p in cls.HEDGE_PHRASES if p in text_lower]
        flagged_weasels = [p for p in cls.WEASEL_PHRASES if p in text_lower]

        if score >= 60:
            risk_level = "HIGH - Likely concealing material information"
        elif score >= 35:
            risk_level = "MODERATE - Some deliberate vagueness detected"
        else:
            risk_level = "LOW - Communication appears direct"

        return {
            "ambiguity_score": round(score, 1),
            "risk_level": risk_level,
            "hedge_density": round(hedge_density, 4),
            "hedge_count": hedge_count,
            "weasel_phrase_count": weasel_count,
            "confidence_word_count": confidence_count,
            "avg_sentence_length": round(avg_sentence_length, 1),
            "word_count": word_count,
            "flagged_hedges": list(set(flagged_hedges)),
            "flagged_weasels": flagged_weasels,
        }
