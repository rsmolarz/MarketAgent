"""
LPPL Bubble Agent

Detects potential market bubbles using Log-Periodic Power Law (LPPL) signatures
by monitoring for super-exponential price growth, price acceleration, and
log-periodic oscillation patterns.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
import numpy as np


class LPPLSBubbleAgent(BaseAgent):

    def __init__(self):
        super().__init__("LPPLSBubbleAgent")
        self.yahoo_client = YahooFinanceClient()
        self.instruments = ['SPY', 'QQQ', 'BTC-USD', 'ETH-USD', 'NVDA', 'TSLA']
        self.acceleration_threshold = 1.5
        self.growth_lookback = 60

    def plan(self) -> Dict[str, Any]:
        return {
            "steps": ["fetch_price_history", "check_super_exponential_growth", "detect_lppl_signatures", "generate_findings"],
            "interval": "60min",
            "symbols": self.instruments,
        }

    def act(self, plan: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return self.analyze()

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        for symbol in self.instruments:
            try:
                data = self.yahoo_client.get_price_data(symbol, period='6mo')
                if data is None or len(data) < self.growth_lookback:
                    continue

                market_type = 'crypto' if symbol.endswith('-USD') else 'equity'

                findings.extend(self._check_super_exponential(symbol, data, market_type))
                findings.extend(self._check_price_acceleration(symbol, data, market_type))
                findings.extend(self._check_log_periodic_oscillation(symbol, data, market_type))

            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")

        return findings

    def _check_super_exponential(self, symbol: str, data, market_type: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float).values
            n = len(closes)
            if n < 60:
                return findings

            log_prices = np.log(closes[-60:])
            t = np.arange(60, dtype=float)

            coeffs = np.polyfit(t, log_prices, 1)
            linear_fit = np.polyval(coeffs, t)
            residuals = log_prices - linear_fit

            recent_residual = float(np.mean(residuals[-10:]))
            early_residual = float(np.mean(residuals[:10]))

            curvature = recent_residual - early_residual

            total_return = float((closes[-1] - closes[-60]) / closes[-60])

            if curvature > 0.05 and total_return > 0.3:
                severity = 'critical' if curvature > 0.15 else 'high'
                findings.append(self.create_finding(
                    title=f"Super-Exponential Growth Detected: {symbol}",
                    description=(
                        f"{symbol} exhibits super-exponential price growth over the past 60 trading days. "
                        f"Total return: {total_return*100:.1f}%, Log-price curvature: {curvature:.3f}. "
                        f"LPPL theory suggests this pattern is unsustainable and may precede a correction."
                    ),
                    severity=severity,
                    confidence=float(min(0.5 + curvature * 2, 0.85)),
                    symbol=symbol,
                    market_type=market_type,
                    metadata={
                        'curvature': float(curvature),
                        'total_return_60d': float(total_return),
                        'signal': 'super_exponential',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking super-exponential for {symbol}: {e}")
        return findings

    def _check_price_acceleration(self, symbol: str, data, market_type: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)

            ret_20d_recent = float((closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20])
            ret_20d_prev = float((closes.iloc[-20] - closes.iloc[-40]) / closes.iloc[-40]) if len(closes) >= 40 else 0

            if ret_20d_prev == 0:
                return findings

            acceleration = ret_20d_recent / ret_20d_prev if ret_20d_prev > 0 else 0

            if acceleration > self.acceleration_threshold and ret_20d_recent > 0.05:
                findings.append(self.create_finding(
                    title=f"Price Acceleration Warning: {symbol}",
                    description=(
                        f"{symbol} price is accelerating: recent 20d return ({ret_20d_recent*100:+.1f}%) is "
                        f"{acceleration:.1f}x the previous 20d return ({ret_20d_prev*100:+.1f}%). "
                        f"Accelerating gains often precede unsustainable bubble-like conditions."
                    ),
                    severity='high',
                    confidence=float(min(0.5 + (acceleration - 1.5) * 0.2, 0.8)),
                    symbol=symbol,
                    market_type=market_type,
                    metadata={
                        'acceleration': float(acceleration),
                        'return_recent_20d': float(ret_20d_recent),
                        'return_prev_20d': float(ret_20d_prev),
                        'signal': 'price_acceleration',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking price acceleration for {symbol}: {e}")
        return findings

    def _check_log_periodic_oscillation(self, symbol: str, data, market_type: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float).values
            if len(closes) < 60:
                return findings

            log_prices = np.log(closes[-60:])
            t = np.arange(60, dtype=float)

            coeffs = np.polyfit(t, log_prices, 2)
            trend = np.polyval(coeffs, t)
            detrended = log_prices - trend

            if len(detrended) < 10:
                return findings

            fft_vals = np.abs(np.fft.rfft(detrended))
            if len(fft_vals) < 3:
                return findings

            fft_vals[0] = 0
            dominant_freq_idx = int(np.argmax(fft_vals[1:])) + 1
            spectral_power = float(fft_vals[dominant_freq_idx])
            total_power = float(np.sum(fft_vals[1:]))

            if total_power <= 0:
                return findings

            concentration = spectral_power / total_power

            if concentration > 0.3:
                findings.append(self.create_finding(
                    title=f"Log-Periodic Oscillation Pattern: {symbol}",
                    description=(
                        f"{symbol} shows log-periodic oscillation signatures in detrended price data. "
                        f"Spectral concentration: {concentration:.1%} at dominant frequency. "
                        f"This pattern is consistent with LPPL bubble dynamics."
                    ),
                    severity='medium',
                    confidence=float(min(0.4 + concentration, 0.75)),
                    symbol=symbol,
                    market_type=market_type,
                    metadata={
                        'spectral_concentration': float(concentration),
                        'dominant_freq_idx': int(dominant_freq_idx),
                        'signal': 'log_periodic',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking log-periodic oscillation for {symbol}: {e}")
        return findings
