"""
Bank Earnings Agent

Analyzes bank sector earnings and credit metrics including NIM proxies
(yield curve slope), credit stress indicators, and bank vs market momentum.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
import numpy as np


class BankEarningsAgent(BaseAgent):

    def __init__(self):
        super().__init__("BankEarningsAgent")
        self.yahoo_client = YahooFinanceClient()
        self.bank_stocks = ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'USB', 'PNC', 'TFC', 'SCHW']
        self.yield_curve_long = '^TNX'
        self.yield_curve_short = '^IRX'
        self.credit_hy = 'HYG'
        self.credit_ig = 'LQD'
        self.benchmark = 'SPY'

    def plan(self) -> Dict[str, Any]:
        return {
            "steps": ["fetch_bank_data", "analyze_yield_curve", "check_credit_stress", "compare_momentum", "generate_findings"],
            "interval": "120min",
            "symbols": self.bank_stocks,
        }

    def act(self, plan: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return self.analyze()

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        yield_curve_data = self._get_yield_curve_data()
        credit_stress_data = self._get_credit_stress_data()
        spy_data = self._get_benchmark_data()

        for symbol in self.bank_stocks:
            try:
                data = self.yahoo_client.get_price_data(symbol, period='3mo')
                if data is None or len(data) < 20:
                    continue

                findings.extend(self._check_bank_momentum(symbol, data, spy_data))
                findings.extend(self._check_nim_sensitivity(symbol, data, yield_curve_data))

            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")

        findings.extend(self._check_yield_curve_signal(yield_curve_data))
        findings.extend(self._check_credit_stress_signal(credit_stress_data))

        return findings

    def _get_yield_curve_data(self) -> Dict[str, Any]:
        result = {}
        try:
            tnx_data = self.yahoo_client.get_price_data(self.yield_curve_long, period='3mo')
            irx_data = self.yahoo_client.get_price_data(self.yield_curve_short, period='3mo')

            if tnx_data is not None and len(tnx_data) > 0:
                result['tnx_current'] = float(tnx_data['Close'].iloc[-1])
                if len(tnx_data) >= 20:
                    result['tnx_20d_ago'] = float(tnx_data['Close'].iloc[-20])

            if irx_data is not None and len(irx_data) > 0:
                result['irx_current'] = float(irx_data['Close'].iloc[-1])
                if len(irx_data) >= 20:
                    result['irx_20d_ago'] = float(irx_data['Close'].iloc[-20])

            if 'tnx_current' in result and 'irx_current' in result:
                result['spread_current'] = result['tnx_current'] - result['irx_current']
                if 'tnx_20d_ago' in result and 'irx_20d_ago' in result:
                    result['spread_20d_ago'] = result['tnx_20d_ago'] - result['irx_20d_ago']
                    result['spread_change'] = result['spread_current'] - result['spread_20d_ago']

        except Exception as e:
            self.logger.error(f"Error fetching yield curve data: {e}")
        return result

    def _get_credit_stress_data(self) -> Dict[str, Any]:
        result = {}
        try:
            hyg_data = self.yahoo_client.get_price_data(self.credit_hy, period='3mo')
            lqd_data = self.yahoo_client.get_price_data(self.credit_ig, period='3mo')

            if hyg_data is not None and lqd_data is not None and len(hyg_data) >= 20 and len(lqd_data) >= 20:
                hyg_close = hyg_data['Close'].astype(float)
                lqd_close = lqd_data['Close'].astype(float)

                min_len = min(len(hyg_close), len(lqd_close))
                hyg_close = hyg_close.iloc[-min_len:]
                lqd_close = lqd_close.iloc[-min_len:]

                ratio = hyg_close / lqd_close
                result['ratio_current'] = float(ratio.iloc[-1])
                result['ratio_20d_ago'] = float(ratio.iloc[-20]) if len(ratio) >= 20 else float(ratio.iloc[0])
                result['ratio_change'] = result['ratio_current'] - result['ratio_20d_ago']
                result['hyg_return_20d'] = float((hyg_close.iloc[-1] - hyg_close.iloc[-20]) / hyg_close.iloc[-20])
                result['lqd_return_20d'] = float((lqd_close.iloc[-1] - lqd_close.iloc[-20]) / lqd_close.iloc[-20])

        except Exception as e:
            self.logger.error(f"Error fetching credit stress data: {e}")
        return result

    def _get_benchmark_data(self):
        try:
            return self.yahoo_client.get_price_data(self.benchmark, period='3mo')
        except Exception as e:
            self.logger.error(f"Error fetching benchmark data: {e}")
            return None

    def _check_bank_momentum(self, symbol: str, data, spy_data) -> List[Dict[str, Any]]:
        findings = []
        try:
            closes = data['Close'].astype(float)
            bank_ret_20d = float((closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20])

            spy_ret_20d = 0.0
            if spy_data is not None and len(spy_data) >= 20:
                spy_closes = spy_data['Close'].astype(float)
                spy_ret_20d = float((spy_closes.iloc[-1] - spy_closes.iloc[-20]) / spy_closes.iloc[-20])

            relative_perf = bank_ret_20d - spy_ret_20d

            if abs(relative_perf) > 0.03:
                direction = 'outperforming' if relative_perf > 0 else 'underperforming'
                findings.append(self.create_finding(
                    title=f"Bank Stock {direction.title()}: {symbol}",
                    description=(
                        f"{symbol} is {direction} SPY by {abs(relative_perf)*100:.1f}% over 20 days. "
                        f"Bank return: {bank_ret_20d*100:+.1f}%, SPY: {spy_ret_20d*100:+.1f}%. "
                        f"This divergence may reflect changing expectations for bank earnings."
                    ),
                    severity='medium',
                    confidence=float(min(0.5 + abs(relative_perf) * 3, 0.8)),
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'bank_return_20d': float(bank_ret_20d),
                        'spy_return_20d': float(spy_ret_20d),
                        'relative_performance': float(relative_perf),
                        'signal': f'bank_{direction}',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking bank momentum for {symbol}: {e}")
        return findings

    def _check_nim_sensitivity(self, symbol: str, data, yc_data: Dict) -> List[Dict[str, Any]]:
        findings = []
        try:
            if 'spread_change' not in yc_data:
                return findings

            spread_change = yc_data['spread_change']
            closes = data['Close'].astype(float)
            bank_ret = float((closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20])

            if spread_change > 0.2 and bank_ret < 0:
                findings.append(self.create_finding(
                    title=f"NIM Divergence: {symbol}",
                    description=(
                        f"Yield curve steepening (+{spread_change:.2f}%) should benefit {symbol}'s NIM, "
                        f"but the stock is down {bank_ret*100:.1f}% over 20 days. "
                        f"This divergence may present a buying opportunity if earnings confirm NIM expansion."
                    ),
                    severity='medium',
                    confidence=0.6,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'spread_change': float(spread_change),
                        'bank_return': float(bank_ret),
                        'signal': 'nim_divergence',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking NIM sensitivity for {symbol}: {e}")
        return findings

    def _check_yield_curve_signal(self, yc_data: Dict) -> List[Dict[str, Any]]:
        findings = []
        try:
            if 'spread_current' not in yc_data:
                return findings

            spread = yc_data['spread_current']
            spread_change = yc_data.get('spread_change', 0)

            if abs(spread_change) > 0.3:
                direction = 'steepening' if spread_change > 0 else 'flattening'
                impact = 'positive' if spread_change > 0 else 'negative'
                findings.append(self.create_finding(
                    title=f"Yield Curve {direction.title()} - {impact.title()} for Banks",
                    description=(
                        f"Yield curve has {'steepened' if spread_change > 0 else 'flattened'} by "
                        f"{abs(spread_change):.2f}% over 20 days. Current 10Y-3M spread: {spread:.2f}%. "
                        f"This is generally {impact} for bank net interest margins."
                    ),
                    severity='high' if abs(spread_change) > 0.5 else 'medium',
                    confidence=0.7,
                    symbol='^TNX',
                    market_type='equity',
                    metadata={
                        'spread_current': float(spread),
                        'spread_change': float(spread_change),
                        'signal': f'yield_curve_{direction}',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking yield curve signal: {e}")
        return findings

    def _check_credit_stress_signal(self, credit_data: Dict) -> List[Dict[str, Any]]:
        findings = []
        try:
            if 'ratio_change' not in credit_data:
                return findings

            ratio_change = credit_data['ratio_change']
            ratio_current = credit_data['ratio_current']

            if ratio_change < -0.01:
                findings.append(self.create_finding(
                    title="Credit Stress Rising - Risk for Bank Earnings",
                    description=(
                        f"HYG/LQD ratio has declined by {abs(ratio_change):.3f} over 20 days "
                        f"(current: {ratio_current:.3f}). High yield underperforming investment grade "
                        f"suggests rising credit stress, which could impact bank loan portfolios."
                    ),
                    severity='high',
                    confidence=0.7,
                    symbol='HYG',
                    market_type='equity',
                    metadata={
                        'hyg_lqd_ratio': float(ratio_current),
                        'ratio_change': float(ratio_change),
                        'signal': 'credit_stress',
                    }
                ))
        except Exception as e:
            self.logger.error(f"Error checking credit stress: {e}")
        return findings
