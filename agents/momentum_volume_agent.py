"""
Momentum Volume Agent

Detects momentum + volume confirmation signals by analyzing price momentum
across multiple timeframes, volume trends, and momentum-volume divergences.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
import numpy as np


class MomentumVolumeAgent(BaseAgent):

    def __init__(self):
        super().__init__("MomentumVolumeAgent")
        self.yahoo_client = YahooFinanceClient()
        self.instruments = ['SPY', 'QQQ', 'IWM', 'DIA', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD', 'META']
        self.momentum_periods = [5, 10, 20]
        self.strong_momentum_threshold = 0.03
        self.divergence_threshold = 0.02

    def plan(self) -> Dict[str, Any]:
        return {
            "steps": ["fetch_price_data", "calculate_momentum", "check_volume_confirmation", "detect_divergence", "generate_findings"],
            "interval": "30min",
            "symbols": self.instruments,
        }

    def act(self, plan: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return self.analyze()

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        for symbol in self.instruments:
            try:
                data = self.yahoo_client.get_price_data(symbol, period='3mo')
                if data is None or len(data) < 25:
                    continue

                findings.extend(self._check_momentum_confirmation(symbol, data))
                findings.extend(self._check_momentum_volume_divergence(symbol, data))
                findings.extend(self._check_multi_timeframe_alignment(symbol, data))

            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")

        return findings

    def _calculate_returns(self, closes, period: int) -> float:
        if len(closes) <= period:
            return 0.0
        return float((closes.iloc[-1] - closes.iloc[-period]) / closes.iloc[-period])

    def _check_momentum_confirmation(self, symbol: str, data) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)
            volumes = data['Volume'].astype(float)

            ret_5d = self._calculate_returns(closes, 5)
            vol_avg_5d = float(volumes.tail(5).mean())
            vol_avg_20d = float(volumes.tail(20).mean())

            if vol_avg_20d <= 0:
                return findings

            vol_ratio = vol_avg_5d / vol_avg_20d
            price_up = ret_5d > self.strong_momentum_threshold
            volume_up = vol_ratio > 1.2

            if price_up and volume_up:
                findings.append(self.create_finding(
                    title=f"Bullish Momentum + Volume Confirmation: {symbol}",
                    description=(
                        f"{symbol} shows strong upward momentum ({ret_5d*100:+.1f}% over 5 days) "
                        f"confirmed by above-average volume ({vol_ratio:.1f}x 20d avg). "
                        f"Volume-confirmed momentum tends to persist."
                    ),
                    severity='medium',
                    confidence=float(min(0.6 + ret_5d * 3, 0.85)),
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'return_5d': float(ret_5d),
                        'volume_ratio': float(vol_ratio),
                        'signal': 'bullish_confirmation',
                    }
                ))
            elif ret_5d < -self.strong_momentum_threshold and volume_up:
                findings.append(self.create_finding(
                    title=f"Bearish Momentum + Volume Confirmation: {symbol}",
                    description=(
                        f"{symbol} shows strong downward momentum ({ret_5d*100:+.1f}% over 5 days) "
                        f"confirmed by above-average volume ({vol_ratio:.1f}x 20d avg). "
                        f"Volume-confirmed selling pressure may continue."
                    ),
                    severity='high',
                    confidence=float(min(0.6 + abs(ret_5d) * 3, 0.85)),
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'return_5d': float(ret_5d),
                        'volume_ratio': float(vol_ratio),
                        'signal': 'bearish_confirmation',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking momentum confirmation for {symbol}: {e}")
        return findings

    def _check_momentum_volume_divergence(self, symbol: str, data) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)
            volumes = data['Volume'].astype(float)

            ret_10d = self._calculate_returns(closes, 10)
            vol_avg_recent = float(volumes.tail(5).mean())
            vol_avg_prev = float(volumes.iloc[-10:-5].mean())

            if vol_avg_prev <= 0:
                return findings

            vol_change = (vol_avg_recent - vol_avg_prev) / vol_avg_prev

            if ret_10d > self.divergence_threshold and vol_change < -0.15:
                findings.append(self.create_finding(
                    title=f"Bearish Divergence (Price Up, Volume Down): {symbol}",
                    description=(
                        f"{symbol} price up {ret_10d*100:+.1f}% over 10 days but volume declining "
                        f"({vol_change*100:.1f}%). Rally on fading volume suggests weakening conviction "
                        f"and potential for a pullback."
                    ),
                    severity='medium',
                    confidence=0.65,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'return_10d': float(ret_10d),
                        'volume_change': float(vol_change),
                        'signal': 'bearish_divergence',
                    }
                ))
            elif ret_10d < -self.divergence_threshold and vol_change < -0.15:
                findings.append(self.create_finding(
                    title=f"Selling Exhaustion Signal: {symbol}",
                    description=(
                        f"{symbol} price down {ret_10d*100:+.1f}% over 10 days with declining volume "
                        f"({vol_change*100:.1f}%). Declining volume during a selloff may indicate "
                        f"selling pressure is exhausting."
                    ),
                    severity='low',
                    confidence=0.55,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'return_10d': float(ret_10d),
                        'volume_change': float(vol_change),
                        'signal': 'selling_exhaustion',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking momentum-volume divergence for {symbol}: {e}")
        return findings

    def _check_multi_timeframe_alignment(self, symbol: str, data) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)

            returns = {}
            for period in self.momentum_periods:
                returns[period] = self._calculate_returns(closes, period)

            all_positive = all(r > 0.01 for r in returns.values())
            all_negative = all(r < -0.01 for r in returns.values())

            accelerating_up = (returns[5] > returns[10] > returns[20] > 0)
            accelerating_down = (returns[5] < returns[10] < returns[20] < 0)

            if all_positive and accelerating_up:
                findings.append(self.create_finding(
                    title=f"Accelerating Bullish Momentum: {symbol}",
                    description=(
                        f"{symbol} shows aligned bullish momentum across all timeframes with acceleration. "
                        f"5d: {returns[5]*100:+.1f}%, 10d: {returns[10]*100:+.1f}%, 20d: {returns[20]*100:+.1f}%. "
                        f"Momentum is strengthening at shorter timeframes."
                    ),
                    severity='high',
                    confidence=0.75,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'return_5d': float(returns[5]),
                        'return_10d': float(returns[10]),
                        'return_20d': float(returns[20]),
                        'signal': 'accelerating_bullish',
                    }
                ))
            elif all_negative and accelerating_down:
                findings.append(self.create_finding(
                    title=f"Accelerating Bearish Momentum: {symbol}",
                    description=(
                        f"{symbol} shows aligned bearish momentum across all timeframes with acceleration. "
                        f"5d: {returns[5]*100:+.1f}%, 10d: {returns[10]*100:+.1f}%, 20d: {returns[20]*100:+.1f}%. "
                        f"Selling pressure is intensifying."
                    ),
                    severity='high',
                    confidence=0.75,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'return_5d': float(returns[5]),
                        'return_10d': float(returns[10]),
                        'return_20d': float(returns[20]),
                        'signal': 'accelerating_bearish',
                    }
                ))
            elif all_positive:
                findings.append(self.create_finding(
                    title=f"Multi-Timeframe Bullish Alignment: {symbol}",
                    description=(
                        f"{symbol} positive across all momentum timeframes. "
                        f"5d: {returns[5]*100:+.1f}%, 10d: {returns[10]*100:+.1f}%, 20d: {returns[20]*100:+.1f}%."
                    ),
                    severity='medium',
                    confidence=0.65,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'return_5d': float(returns[5]),
                        'return_10d': float(returns[10]),
                        'return_20d': float(returns[20]),
                        'signal': 'bullish_alignment',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking multi-timeframe alignment for {symbol}: {e}")
        return findings
