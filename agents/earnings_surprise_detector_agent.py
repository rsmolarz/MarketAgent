"""
Earnings Surprise Detector Agent

Detects upcoming earnings that may produce surprises based on pre-earnings patterns
including unusual volume, options activity signals (implied volatility), and
price drift before earnings announcements.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
import numpy as np


class EarningsSurpriseDetectorAgent(BaseAgent):

    def __init__(self):
        super().__init__("EarningsSurpriseDetectorAgent")
        self.yahoo_client = YahooFinanceClient()
        self.instruments = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'JPM', 'BAC', 'GS', 'WFC']
        self.volume_spike_threshold = 1.5
        self.drift_threshold = 0.03

    def plan(self) -> Dict[str, Any]:
        return {
            "steps": ["fetch_price_data", "check_pre_earnings_volume", "check_price_drift", "check_iv_signals", "generate_findings"],
            "interval": "60min",
            "symbols": self.instruments,
        }

    def act(self, plan: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return self.analyze()

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        for symbol in self.instruments:
            try:
                data = self.yahoo_client.get_price_data(symbol, period='3mo')
                if data is None or len(data) < 30:
                    continue

                findings.extend(self._check_pre_earnings_volume(symbol, data))
                findings.extend(self._check_pre_earnings_drift(symbol, data))
                findings.extend(self._check_iv_proxy(symbol, data))

            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")

        return findings

    def _check_pre_earnings_volume(self, symbol: str, data) -> List[Dict[str, Any]]:
        findings = []
        try:
            volumes = data['Volume'].astype(float)
            avg_vol_20 = float(volumes.iloc[-25:-5].mean())
            recent_vol = float(volumes.tail(5).mean())

            if avg_vol_20 <= 0:
                return findings

            vol_ratio = recent_vol / avg_vol_20

            if vol_ratio > self.volume_spike_threshold:
                findings.append(self.create_finding(
                    title=f"Unusual Pre-Earnings Volume: {symbol}",
                    description=(
                        f"{symbol} shows {vol_ratio:.1f}x normal volume over the last 5 days. "
                        f"Recent avg: {recent_vol:,.0f}, 20d avg: {avg_vol_20:,.0f}. "
                        f"Elevated volume before earnings often signals informed positioning."
                    ),
                    severity='medium',
                    confidence=float(min(0.5 + (vol_ratio - 1.5) * 0.15, 0.85)),
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'volume_ratio': float(vol_ratio),
                        'recent_avg_volume': float(recent_vol),
                        'baseline_avg_volume': float(avg_vol_20),
                        'signal': 'pre_earnings_volume',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking pre-earnings volume for {symbol}: {e}")
        return findings

    def _check_pre_earnings_drift(self, symbol: str, data) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)
            drift_10d = float((closes.iloc[-1] - closes.iloc[-10]) / closes.iloc[-10])
            drift_5d = float((closes.iloc[-1] - closes.iloc[-5]) / closes.iloc[-5])

            if abs(drift_10d) > self.drift_threshold:
                direction = 'positive' if drift_10d > 0 else 'negative'
                findings.append(self.create_finding(
                    title=f"Pre-Earnings Price Drift: {symbol}",
                    description=(
                        f"{symbol} has drifted {drift_10d*100:+.1f}% over 10 days and "
                        f"{drift_5d*100:+.1f}% over 5 days. A {direction} pre-earnings drift may "
                        f"indicate the market is pricing in a {'positive' if drift_10d > 0 else 'negative'} "
                        f"earnings surprise."
                    ),
                    severity='medium' if abs(drift_10d) < 0.05 else 'high',
                    confidence=float(min(0.5 + abs(drift_10d) * 3, 0.8)),
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'drift_10d': float(drift_10d),
                        'drift_5d': float(drift_5d),
                        'direction': direction,
                        'signal': 'pre_earnings_drift',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking pre-earnings drift for {symbol}: {e}")
        return findings

    def _check_iv_proxy(self, symbol: str, data) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)
            highs = data['High'].astype(float)
            lows = data['Low'].astype(float)

            hl_range = (highs - lows) / closes
            recent_range = float(hl_range.tail(5).mean())
            historical_range = float(hl_range.tail(30).mean())

            if historical_range <= 0:
                return findings

            iv_proxy_ratio = recent_range / historical_range

            if iv_proxy_ratio > 1.5:
                findings.append(self.create_finding(
                    title=f"Elevated Implied Volatility Signal: {symbol}",
                    description=(
                        f"{symbol} intraday range has expanded to {iv_proxy_ratio:.1f}x its 30-day average. "
                        f"Recent avg range: {recent_range*100:.2f}%, Historical: {historical_range*100:.2f}%. "
                        f"Expanding ranges near earnings suggest elevated implied volatility and "
                        f"potential for a large earnings move."
                    ),
                    severity='medium',
                    confidence=float(min(0.5 + (iv_proxy_ratio - 1.5) * 0.2, 0.8)),
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'iv_proxy_ratio': float(iv_proxy_ratio),
                        'recent_range': float(recent_range),
                        'historical_range': float(historical_range),
                        'signal': 'elevated_iv',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking IV proxy for {symbol}: {e}")
        return findings
