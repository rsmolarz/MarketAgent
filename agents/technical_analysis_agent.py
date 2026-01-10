from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
from ta.signals import generate_signals


class TechnicalAnalysisAgent(BaseAgent):
    """
    Core Technical Analysis Agent
    Produces RSI / MACD / MA / Bollinger / Support-Resistance signals
    """

    def __init__(self):
        super().__init__()
        self.yahoo = YahooFinanceClient()
        self.symbols = self.config.get(
            "symbols",
            ["SPY", "QQQ", "IWM", "DIA", "TLT", "GLD", "BTC-USD"]
        )
        self.period = self.config.get("period", "6mo")

    def analyze(self) -> List[Dict[str, Any]]:
        findings = []

        for symbol in self.symbols:
            df = self.yahoo.get_price_data(symbol, period=self.period)
            if df is None or df.empty or len(df) < 60:
                continue

            signals, ta = generate_signals(symbol, df)

            for s in signals:
                severity = "medium" if s["confidence"] >= 0.6 else "low"

                findings.append(self.create_finding(
                    title=f"TA Signal: {s['type']} on {symbol}",
                    description=f"{symbol} technical signal detected ({s['bias']}). "
                                f"RSI={ta['rsi']:.1f}, MA20={ta['ma20']:.2f}, MA50={ta['ma50']:.2f}",
                    severity=severity,
                    confidence=float(s.get("confidence", 0.5)),
                    symbol=symbol,
                    market_type="technical",
                    metadata={
                        "signal": s,
                        "ta_snapshot": ta
                    }
                ))

        return findings

    def analyze_ctx(self, ctx) -> List[Dict[str, Any]]:
        """Backtest-compatible analysis using context frame"""
        findings = []

        for symbol in self.symbols:
            df = ctx.frame(symbol)
            if df is None or df.empty or len(df) < 60:
                continue

            signals, ta = generate_signals(symbol, df)

            for s in signals:
                findings.append(self.create_finding(
                    title=f"TA Signal: {s['type']} on {symbol}",
                    description=f"{symbol} TA signal ({s['bias']})",
                    severity="medium",
                    confidence=float(s.get("confidence", 0.5)),
                    symbol=symbol,
                    market_type="technical",
                    metadata={
                        "signal": s,
                        "ta_snapshot": ta,
                        "asof": ctx.asof.isoformat()
                    }
                ))

        return findings
