"""
High Frequency Flow Analysis Agent

Analyzes high-frequency order flow for institutional activity signals
including volume spikes, bid-ask spread compression, and unusual block trades.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
import numpy as np


class HighFrequencyFlowAnalysisAgent(BaseAgent):

    def __init__(self):
        super().__init__("HighFrequencyFlowAnalysisAgent")
        self.yahoo_client = YahooFinanceClient()
        self.instruments = ['SPY', 'QQQ', 'IWM', 'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN']
        self.volume_spike_threshold = 2.0
        self.block_trade_threshold = 1.5

    def plan(self) -> Dict[str, Any]:
        return {
            "steps": ["fetch_intraday_data", "detect_volume_spikes", "analyze_block_trades", "generate_findings"],
            "interval": "15min",
            "symbols": self.instruments,
        }

    def act(self, plan: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return self.analyze()

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        for symbol in self.instruments:
            try:
                data = self.yahoo_client.get_price_data(symbol, period='1mo')
                if data is None or len(data) < 20:
                    continue

                findings.extend(self._check_volume_spike(symbol, data))
                findings.extend(self._check_spread_compression(symbol, data))
                findings.extend(self._check_block_trade_signals(symbol, data))

            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")

        return findings

    def _check_volume_spike(self, symbol: str, data) -> List[Dict[str, Any]]:
        findings = []
        try:
            volumes = data['Volume'].astype(float)
            avg_20 = float(volumes.tail(20).mean())
            current_vol = float(volumes.iloc[-1])

            if avg_20 <= 0:
                return findings

            vol_ratio = current_vol / avg_20

            if vol_ratio >= self.volume_spike_threshold:
                severity = 'high' if vol_ratio >= 3.0 else 'medium'
                findings.append(self.create_finding(
                    title=f"Volume Spike Detected in {symbol}",
                    description=(
                        f"{symbol} current volume is {vol_ratio:.1f}x the 20-day average. "
                        f"Current: {current_vol:,.0f}, Avg: {avg_20:,.0f}. "
                        f"This may indicate institutional activity or information-driven trading."
                    ),
                    severity=severity,
                    confidence=float(min(0.5 + (vol_ratio - 2.0) * 0.1, 0.9)),
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'volume_ratio': float(vol_ratio),
                        'current_volume': float(current_vol),
                        'avg_20d_volume': float(avg_20),
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking volume spike for {symbol}: {e}")
        return findings

    def _check_spread_compression(self, symbol: str, data) -> List[Dict[str, Any]]:
        findings = []
        try:
            highs = data['High'].astype(float)
            lows = data['Low'].astype(float)
            closes = data['Close'].astype(float)

            spreads = (highs - lows) / closes
            avg_spread = float(spreads.tail(20).mean())
            recent_spread = float(spreads.tail(3).mean())

            if avg_spread <= 0:
                return findings

            compression_ratio = recent_spread / avg_spread

            if compression_ratio < 0.5:
                findings.append(self.create_finding(
                    title=f"Spread Compression in {symbol}",
                    description=(
                        f"{symbol} intraday range has compressed to {compression_ratio:.1%} of its "
                        f"20-day average. This often precedes a significant directional move."
                    ),
                    severity='medium',
                    confidence=float(min(0.6 + (1 - compression_ratio) * 0.3, 0.85)),
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'compression_ratio': float(compression_ratio),
                        'avg_spread': float(avg_spread),
                        'recent_spread': float(recent_spread),
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking spread compression for {symbol}: {e}")
        return findings

    def _check_block_trade_signals(self, symbol: str, data) -> List[Dict[str, Any]]:
        findings = []
        try:
            volumes = data['Volume'].astype(float)
            closes = data['Close'].astype(float)

            dollar_volume = volumes * closes
            avg_dollar_vol = float(dollar_volume.tail(20).mean())
            recent_dollar_vol = float(dollar_volume.iloc[-1])

            if avg_dollar_vol <= 0:
                return findings

            dv_ratio = recent_dollar_vol / avg_dollar_vol

            price_change = float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2]) if len(closes) >= 2 else 0
            abs_price_change = abs(price_change)

            if dv_ratio > self.block_trade_threshold and abs_price_change < 0.005:
                findings.append(self.create_finding(
                    title=f"Unusual Block Trade Activity in {symbol}",
                    description=(
                        f"{symbol} shows {dv_ratio:.1f}x normal dollar volume with minimal price impact "
                        f"({price_change*100:+.2f}%). This pattern suggests large institutional block trades "
                        f"being executed with minimal market impact."
                    ),
                    severity='high',
                    confidence=0.7,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'dollar_volume_ratio': float(dv_ratio),
                        'price_change': float(price_change),
                        'recent_dollar_volume': float(recent_dollar_vol),
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking block trades for {symbol}: {e}")
        return findings
