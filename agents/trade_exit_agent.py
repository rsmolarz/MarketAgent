"""
Trade Exit Agent

Monitors positions for exit signals including trailing stops, target reached,
RSI overbought/oversold, Bollinger Band breach, mean reversion, and volume exhaustion.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
import numpy as np


class TradeExitAgent(BaseAgent):

    def __init__(self):
        super().__init__("TradeExitAgent")
        self.yahoo_client = YahooFinanceClient()
        self.instruments = ['SPY', 'QQQ', 'IWM', 'GLD', 'TLT', 'BTC-USD', 'ETH-USD']
        self.rsi_overbought = 75
        self.rsi_oversold = 25
        self.bb_period = 20
        self.bb_std = 2.0

    def plan(self) -> Dict[str, Any]:
        return {
            "steps": ["fetch_price_data", "check_rsi", "check_bollinger", "check_volume_exhaustion", "generate_findings"],
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
                if data is None or len(data) < 30:
                    continue

                market_type = 'crypto' if symbol.endswith('-USD') else 'equity'

                findings.extend(self._check_rsi_exit(symbol, data, market_type))
                findings.extend(self._check_bollinger_breach(symbol, data, market_type))
                findings.extend(self._check_mean_reversion(symbol, data, market_type))
                findings.extend(self._check_volume_exhaustion(symbol, data, market_type))

            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")

        return findings

    def _calculate_rsi(self, prices, period=14):
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except Exception:
            return prices * 0 + 50

    def _check_rsi_exit(self, symbol: str, data, market_type: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)
            rsi = self._calculate_rsi(closes)
            current_rsi = float(rsi.iloc[-1])

            if current_rsi > self.rsi_overbought:
                findings.append(self.create_finding(
                    title=f"RSI Overbought Exit Signal: {symbol}",
                    description=(
                        f"{symbol} RSI at {current_rsi:.1f} (threshold: {self.rsi_overbought}). "
                        f"Momentum exhaustion detected - consider taking profits or tightening stops."
                    ),
                    severity='high' if current_rsi > 80 else 'medium',
                    confidence=float(min(0.6 + (current_rsi - self.rsi_overbought) * 0.01, 0.9)),
                    symbol=symbol,
                    market_type=market_type,
                    metadata={'rsi': float(current_rsi), 'signal': 'overbought_exit'}
                ))
            elif current_rsi < self.rsi_oversold:
                findings.append(self.create_finding(
                    title=f"RSI Oversold Exit Signal: {symbol}",
                    description=(
                        f"{symbol} RSI at {current_rsi:.1f} (threshold: {self.rsi_oversold}). "
                        f"Oversold conditions detected - consider exiting short positions."
                    ),
                    severity='high' if current_rsi < 20 else 'medium',
                    confidence=float(min(0.6 + (self.rsi_oversold - current_rsi) * 0.01, 0.9)),
                    symbol=symbol,
                    market_type=market_type,
                    metadata={'rsi': float(current_rsi), 'signal': 'oversold_exit'}
                ))
        except Exception as e:
            self.logger.error(f"Error checking RSI for {symbol}: {e}")
        return findings

    def _check_bollinger_breach(self, symbol: str, data, market_type: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)
            sma = closes.rolling(window=self.bb_period).mean()
            std = closes.rolling(window=self.bb_period).std()

            upper_band = sma + self.bb_std * std
            lower_band = sma - self.bb_std * std

            current_price = float(closes.iloc[-1])
            upper = float(upper_band.iloc[-1])
            lower = float(lower_band.iloc[-1])
            middle = float(sma.iloc[-1])

            if current_price > upper:
                pct_above = (current_price - upper) / upper * 100
                findings.append(self.create_finding(
                    title=f"Bollinger Upper Band Breach: {symbol}",
                    description=(
                        f"{symbol} at ${current_price:.2f} is {pct_above:.1f}% above upper Bollinger Band "
                        f"(${upper:.2f}). Price is extended and may revert to the mean (${middle:.2f})."
                    ),
                    severity='medium',
                    confidence=0.65,
                    symbol=symbol,
                    market_type=market_type,
                    metadata={
                        'current_price': float(current_price),
                        'upper_band': float(upper),
                        'lower_band': float(lower),
                        'middle_band': float(middle),
                        'signal': 'upper_breach',
                    }
                ))
            elif current_price < lower:
                pct_below = (lower - current_price) / lower * 100
                findings.append(self.create_finding(
                    title=f"Bollinger Lower Band Breach: {symbol}",
                    description=(
                        f"{symbol} at ${current_price:.2f} is {pct_below:.1f}% below lower Bollinger Band "
                        f"(${lower:.2f}). Price is extended to the downside."
                    ),
                    severity='medium',
                    confidence=0.65,
                    symbol=symbol,
                    market_type=market_type,
                    metadata={
                        'current_price': float(current_price),
                        'upper_band': float(upper),
                        'lower_band': float(lower),
                        'middle_band': float(middle),
                        'signal': 'lower_breach',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking Bollinger Bands for {symbol}: {e}")
        return findings

    def _check_mean_reversion(self, symbol: str, data, market_type: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)
            sma_20 = float(closes.rolling(window=20).mean().iloc[-1])
            current_price = float(closes.iloc[-1])

            if sma_20 <= 0:
                return findings

            deviation = (current_price - sma_20) / sma_20

            if abs(deviation) > 0.05:
                direction = 'above' if deviation > 0 else 'below'
                findings.append(self.create_finding(
                    title=f"Mean Reversion Signal: {symbol}",
                    description=(
                        f"{symbol} is {abs(deviation)*100:.1f}% {direction} its 20-day SMA "
                        f"(${sma_20:.2f}). Extended moves tend to revert toward the mean."
                    ),
                    severity='medium',
                    confidence=float(min(0.5 + abs(deviation) * 2, 0.85)),
                    symbol=symbol,
                    market_type=market_type,
                    metadata={
                        'deviation_pct': float(deviation),
                        'sma_20': float(sma_20),
                        'current_price': float(current_price),
                        'signal': 'mean_reversion',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking mean reversion for {symbol}: {e}")
        return findings

    def _check_volume_exhaustion(self, symbol: str, data, market_type: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)
            volumes = data['Volume'].astype(float)

            price_change_5d = float((closes.iloc[-1] - closes.iloc[-5]) / closes.iloc[-5])
            avg_vol_20 = float(volumes.tail(20).mean())
            avg_vol_5 = float(volumes.tail(5).mean())

            if avg_vol_20 <= 0:
                return findings

            vol_trend = (avg_vol_5 - avg_vol_20) / avg_vol_20

            if abs(price_change_5d) > 0.03 and vol_trend < -0.2:
                direction = 'rally' if price_change_5d > 0 else 'selloff'
                findings.append(self.create_finding(
                    title=f"Volume Exhaustion in {symbol} {direction.title()}",
                    description=(
                        f"{symbol} has moved {price_change_5d*100:+.1f}% over 5 days but volume is "
                        f"declining ({vol_trend*100:.1f}% vs 20d avg). Fading volume during a "
                        f"{direction} suggests the move may be losing steam."
                    ),
                    severity='medium',
                    confidence=0.6,
                    symbol=symbol,
                    market_type=market_type,
                    metadata={
                        'price_change_5d': float(price_change_5d),
                        'volume_trend': float(vol_trend),
                        'signal': 'volume_exhaustion',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking volume exhaustion for {symbol}: {e}")
        return findings
