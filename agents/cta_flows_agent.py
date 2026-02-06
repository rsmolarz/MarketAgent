"""
CTAFlowsAgent - CTA/Trend-Follower Positioning Analysis

Monitors Commodity Trading Advisors (CTAs) and systematic trend-following
strategies to identify positioning extremes and potential flow impacts
on major asset classes (equities, bonds, commodities).

Uses moving average crossover signals, momentum scoring, and volume
analysis to estimate CTA positioning and detect regime shifts.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

TRACKED_INSTRUMENTS = {
    'SPY': {'asset_class': 'equity', 'name': 'S&P 500 ETF'},
    'QQQ': {'asset_class': 'equity', 'name': 'Nasdaq 100 ETF'},
    'IWM': {'asset_class': 'equity', 'name': 'Russell 2000 ETF'},
    'EEM': {'asset_class': 'equity', 'name': 'Emerging Markets ETF'},
    'TLT': {'asset_class': 'bond', 'name': '20+ Year Treasury ETF'},
    'IEF': {'asset_class': 'bond', 'name': '7-10 Year Treasury ETF'},
    'GLD': {'asset_class': 'commodity', 'name': 'Gold ETF'},
    'USO': {'asset_class': 'commodity', 'name': 'Oil ETF'},
    'DBA': {'asset_class': 'commodity', 'name': 'Agriculture ETF'},
}

MA_WINDOWS = [20, 50, 100, 200]
EXTREME_THRESHOLD = 0.85
FLIP_THRESHOLD = 0.02


class CTAFlowsAgent(BaseAgent):
    """
    Analyzes CTA/trend-follower positioning by computing momentum
    signals across multiple timeframes and detecting:
    - Extreme long/short positioning
    - Trend flip imminent signals
    - Key breakout/breakdown levels
    """

    def __init__(self, name: Optional[str] = None):
        super().__init__(name if name else self.__class__.__name__)

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        try:
            import yfinance as yf
            import numpy as np

            for symbol, info in TRACKED_INSTRUMENTS.items():
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1y')

                    if hist.empty or len(hist) < 200:
                        continue

                    close = hist['Close']

                    ma_signals = {}
                    for w in MA_WINDOWS:
                        ma = close.rolling(window=w).mean()
                        if len(ma.dropna()) > 0:
                            ma_signals[w] = float(close.iloc[-1]) > float(ma.iloc[-1])

                    if not ma_signals:
                        continue

                    long_count = sum(1 for v in ma_signals.values() if v)
                    total = len(ma_signals)
                    positioning_score = long_count / total if total > 0 else 0.5

                    if positioning_score >= EXTREME_THRESHOLD:
                        findings.append(self.create_finding(
                            title=f"CTA_EXTREME_LONG: {symbol}",
                            description=(
                                f"CTA_EXTREME_LONG - {info['name']} showing extreme long "
                                f"positioning ({positioning_score:.0%} of MA signals bullish). "
                                f"Potential for crowded trade reversal."
                            ),
                            severity='high',
                            confidence=float(round(0.6 + positioning_score * 0.2, 4)),
                            symbol=symbol,
                            market_type=info['asset_class'],
                        ))

                    elif positioning_score <= (1 - EXTREME_THRESHOLD):
                        findings.append(self.create_finding(
                            title=f"CTA_EXTREME_SHORT: {symbol}",
                            description=(
                                f"CTA_EXTREME_SHORT - {info['name']} showing extreme short "
                                f"positioning ({1 - positioning_score:.0%} of MA signals bearish). "
                                f"Potential for short squeeze."
                            ),
                            severity='high',
                            confidence=float(round(0.6 + (1 - positioning_score) * 0.2, 4)),
                            symbol=symbol,
                            market_type=info['asset_class'],
                        ))

                    ma50 = close.rolling(window=50).mean()
                    if len(ma50.dropna()) >= 5:
                        recent_dist = [
                            float(close.iloc[-i]) - float(ma50.iloc[-i])
                            for i in range(1, 6)
                        ]
                        if len(recent_dist) >= 2:
                            cross_near = abs(recent_dist[0]) / (float(close.iloc[-1]) + 1e-9)
                            if cross_near < FLIP_THRESHOLD:
                                direction = 'bullish' if recent_dist[0] > 0 and recent_dist[-1] < 0 else 'bearish'
                                findings.append(self.create_finding(
                                    title=f"CTA_TREND_FLIP_IMMINENT: {symbol}",
                                    description=(
                                        f"CTA_TREND_FLIP_IMMINENT - {info['name']} price within "
                                        f"{cross_near:.1%} of 50-day MA. Potential {direction} "
                                        f"trend flip may trigger CTA flow reversal."
                                    ),
                                    severity='high',
                                    confidence=float(round(min(0.9, 0.7 + (FLIP_THRESHOLD - cross_near) * 10), 4)),
                                    symbol=symbol,
                                    market_type=info['asset_class'],
                                ))

                    ma200 = close.rolling(window=200).mean()
                    if len(ma200.dropna()) > 0:
                        level_200 = float(ma200.iloc[-1])
                        current = float(close.iloc[-1])
                        distance_pct = (current - level_200) / level_200

                        if abs(distance_pct) < 0.03:
                            findings.append(self.create_finding(
                                title=f"CTA_BREAKOUT_LEVELS: {symbol}",
                                description=(
                                    f"CTA_BREAKOUT_LEVELS - {info['name']} within "
                                    f"{abs(distance_pct):.1%} of 200-day MA (${level_200:.2f}). "
                                    f"Break {'above' if distance_pct < 0 else 'below'} may "
                                    f"trigger significant CTA flow activity."
                                ),
                                severity='medium',
                                confidence=float(round(0.65, 4)),
                                symbol=symbol,
                                market_type=info['asset_class'],
                            ))

                except Exception as e:
                    logger.warning(f"CTAFlowsAgent: Error analyzing {symbol}: {e}")
                    continue

            logger.info(f"CTA FLOWS AGENT: {len(findings)} signals detected")
            return findings

        except ImportError as e:
            logger.error(f"CTAFlowsAgent missing dependency: {e}")
            return [{
                "title": "CTA_FLOWS_DEPENDENCY_ERROR",
                "description": f"Missing required library: {e}",
                "severity": "medium",
                "confidence": 1.0,
                "market_type": "system",
            }]
        except Exception as e:
            logger.error(f"CTAFlowsAgent error: {e}")
            return [{
                "title": "CTA_FLOWS_ERROR",
                "description": f"CTA flows analysis failed: {e}",
                "severity": "medium",
                "confidence": 1.0,
                "market_type": "system",
            }]
