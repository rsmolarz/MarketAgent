"""
Sector Rotation Signal Agent

Detects sector rotation signals using relative strength of sector ETFs
against SPY benchmark, monitoring momentum and flow divergence.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
import numpy as np


class SectorRotationSignalAgent(BaseAgent):

    def __init__(self):
        super().__init__("SectorRotationSignalAgent")
        self.yahoo_client = YahooFinanceClient()
        self.sector_etfs = {
            'XLF': 'Financials',
            'XLK': 'Technology',
            'XLE': 'Energy',
            'XLV': 'Health Care',
            'XLI': 'Industrials',
            'XLP': 'Consumer Staples',
            'XLU': 'Utilities',
            'XLB': 'Materials',
            'XLRE': 'Real Estate',
            'XLC': 'Communication Services',
        }
        self.benchmark = 'SPY'
        self.momentum_period = 20
        self.rs_threshold = 0.03

    def plan(self) -> Dict[str, Any]:
        return {
            "steps": ["fetch_sector_data", "calculate_relative_strength", "detect_rotation", "generate_findings"],
            "interval": "60min",
            "symbols": list(self.sector_etfs.keys()),
        }

    def act(self, plan: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return self.analyze()

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        try:
            spy_data = self.yahoo_client.get_price_data(self.benchmark, period='3mo')
            if spy_data is None or len(spy_data) < self.momentum_period:
                self.logger.warning("Insufficient SPY data for sector rotation analysis")
                return findings
        except Exception as e:
            self.logger.error(f"Error fetching SPY data: {e}")
            return findings

        spy_closes = spy_data['Close'].astype(float)
        spy_return_20d = float((spy_closes.iloc[-1] - spy_closes.iloc[-self.momentum_period]) / spy_closes.iloc[-self.momentum_period])

        sector_rs = {}

        for symbol, sector_name in self.sector_etfs.items():
            try:
                data = self.yahoo_client.get_price_data(symbol, period='3mo')
                if data is None or len(data) < self.momentum_period:
                    continue

                closes = data['Close'].astype(float)
                sector_return_20d = float((closes.iloc[-1] - closes.iloc[-self.momentum_period]) / closes.iloc[-self.momentum_period])
                relative_strength = sector_return_20d - spy_return_20d

                sector_rs[symbol] = {
                    'name': sector_name,
                    'return_20d': sector_return_20d,
                    'relative_strength': relative_strength,
                }

                findings.extend(self._check_relative_strength(symbol, sector_name, relative_strength, sector_return_20d, spy_return_20d))
                findings.extend(self._check_momentum_shift(symbol, sector_name, closes, spy_closes))

            except Exception as e:
                self.logger.error(f"Error analyzing sector {symbol}: {e}")

        findings.extend(self._check_rotation_pattern(sector_rs))

        return findings

    def _check_relative_strength(self, symbol: str, sector_name: str, rs: float,
                                  sector_ret: float, spy_ret: float) -> List[Dict[str, Any]]:
        findings = []
        try:
            if abs(rs) > self.rs_threshold:
                if rs > 0:
                    findings.append(self.create_finding(
                        title=f"Sector Outperformance: {sector_name} ({symbol})",
                        description=(
                            f"{sector_name} sector is outperforming SPY by {rs*100:.1f}% over 20 days. "
                            f"Sector return: {sector_ret*100:+.1f}%, SPY: {spy_ret*100:+.1f}%. "
                            f"Capital may be rotating into this sector."
                        ),
                        severity='medium',
                        confidence=float(min(0.5 + abs(rs) * 3, 0.85)),
                        symbol=symbol,
                        market_type='equity',
                        metadata={
                            'relative_strength': float(rs),
                            'sector_return': float(sector_ret),
                            'spy_return': float(spy_ret),
                            'sector_name': sector_name,
                            'signal': 'outperformance',
                        }
                    ))
                else:
                    findings.append(self.create_finding(
                        title=f"Sector Underperformance: {sector_name} ({symbol})",
                        description=(
                            f"{sector_name} sector is underperforming SPY by {abs(rs)*100:.1f}% over 20 days. "
                            f"Sector return: {sector_ret*100:+.1f}%, SPY: {spy_ret*100:+.1f}%. "
                            f"Capital may be rotating out of this sector."
                        ),
                        severity='medium',
                        confidence=float(min(0.5 + abs(rs) * 3, 0.85)),
                        symbol=symbol,
                        market_type='equity',
                        metadata={
                            'relative_strength': float(rs),
                            'sector_return': float(sector_ret),
                            'spy_return': float(spy_ret),
                            'sector_name': sector_name,
                            'signal': 'underperformance',
                        }
                    ))
        except Exception as e:
            self.logger.error(f"Error checking relative strength for {symbol}: {e}")
        return findings

    def _check_momentum_shift(self, symbol: str, sector_name: str,
                               sector_closes, spy_closes) -> List[Dict[str, Any]]:
        findings = []
        try:
            if len(sector_closes) < 20 or len(spy_closes) < 20:
                return findings

            sector_ret_10d = float((sector_closes.iloc[-1] - sector_closes.iloc[-10]) / sector_closes.iloc[-10])
            sector_ret_prev_10d = float((sector_closes.iloc[-10] - sector_closes.iloc[-20]) / sector_closes.iloc[-20])

            spy_ret_10d = float((spy_closes.iloc[-1] - spy_closes.iloc[-10]) / spy_closes.iloc[-10])
            spy_ret_prev_10d = float((spy_closes.iloc[-10] - spy_closes.iloc[-20]) / spy_closes.iloc[-20])

            rs_recent = sector_ret_10d - spy_ret_10d
            rs_prev = sector_ret_prev_10d - spy_ret_prev_10d

            if rs_prev < -0.02 and rs_recent > 0.02:
                findings.append(self.create_finding(
                    title=f"Momentum Shift Into {sector_name} ({symbol})",
                    description=(
                        f"{sector_name} has shifted from underperforming to outperforming SPY. "
                        f"Previous 10d RS: {rs_prev*100:+.1f}%, Recent 10d RS: {rs_recent*100:+.1f}%. "
                        f"This may signal the beginning of a sector rotation."
                    ),
                    severity='high',
                    confidence=0.7,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'rs_recent': float(rs_recent),
                        'rs_previous': float(rs_prev),
                        'sector_name': sector_name,
                        'signal': 'momentum_shift_in',
                    }
                ))
            elif rs_prev > 0.02 and rs_recent < -0.02:
                findings.append(self.create_finding(
                    title=f"Momentum Shift Away From {sector_name} ({symbol})",
                    description=(
                        f"{sector_name} has shifted from outperforming to underperforming SPY. "
                        f"Previous 10d RS: {rs_prev*100:+.1f}%, Recent 10d RS: {rs_recent*100:+.1f}%. "
                        f"Capital may be rotating out of this sector."
                    ),
                    severity='high',
                    confidence=0.7,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'rs_recent': float(rs_recent),
                        'rs_previous': float(rs_prev),
                        'sector_name': sector_name,
                        'signal': 'momentum_shift_out',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking momentum shift for {symbol}: {e}")
        return findings

    def _check_rotation_pattern(self, sector_rs: Dict) -> List[Dict[str, Any]]:
        findings = []
        try:
            if len(sector_rs) < 5:
                return findings

            sorted_sectors = sorted(sector_rs.items(), key=lambda x: x[1]['relative_strength'], reverse=True)
            top_sectors = sorted_sectors[:3]
            bottom_sectors = sorted_sectors[-3:]

            top_names = [f"{s[1]['name']} ({s[1]['relative_strength']*100:+.1f}%)" for s in top_sectors]
            bottom_names = [f"{s[1]['name']} ({s[1]['relative_strength']*100:+.1f}%)" for s in bottom_sectors]

            spread = float(top_sectors[0][1]['relative_strength'] - bottom_sectors[-1]['relative_strength'])

            if spread > 0.06:
                findings.append(self.create_finding(
                    title="Significant Sector Rotation Detected",
                    description=(
                        f"Wide dispersion in sector performance detected ({spread*100:.1f}% spread). "
                        f"Leaders: {', '.join(top_names)}. "
                        f"Laggards: {', '.join(bottom_names)}. "
                        f"This suggests active sector rotation is underway."
                    ),
                    severity='high',
                    confidence=0.75,
                    symbol='SPY',
                    market_type='equity',
                    metadata={
                        'spread': float(spread),
                        'top_sectors': [s[0] for s in top_sectors],
                        'bottom_sectors': [s[0] for s in bottom_sectors],
                        'signal': 'rotation_pattern',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking rotation pattern: {e}")
        return findings
