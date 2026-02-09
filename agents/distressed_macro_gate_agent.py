from typing import List, Dict, Any
from .base_agent import BaseAgent


class DistressedMacroGateAgent(BaseAgent):
    """
    Macro risk overlay for distressed real-estate deployment.
    Gates underwriting velocity, margin-of-safety, and capital release.
    
    This is a deployment gate that controls when distressed deals are allowed to advance.
    It converts macro regime + drawdown into real-estate underwriting friction.
    
    Emits system-level findings consumed by:
    - IC memo
    - Deal room
    - Capital allocator
    - Kill rules
    """
    
    name = "DistressedMacroGateAgent"
    description = "Macro risk gate for distressed real-estate deployment"

    def analyze_ctx(self, ctx) -> List[Dict[str, Any]]:
        findings = []

        regime = ctx.meta.get("regime", "unknown")
        vol = ctx.meta.get("vol_label", "elevated")
        drawdown = float(ctx.meta.get("portfolio_drawdown", 0.0))

        gate = "GREEN"
        severity = "low"
        mos_multiplier = 1.0
        max_capital_pct = 1.0
        notes = []

        if regime in ("volatility", "transition"):
            gate = "YELLOW"
            severity = "medium"
            mos_multiplier = 1.15
            max_capital_pct = 0.6
            notes.append("Macro regime unstable - slower underwriting, higher MOS")

        if drawdown <= -0.10:
            gate = "RED"
            severity = "high"
            mos_multiplier = 1.30
            max_capital_pct = 0.3
            notes.append("Portfolio drawdown >=10% - capital preservation mode")

        if drawdown <= -0.20:
            gate = "RED"
            severity = "critical"
            mos_multiplier = 1.50
            max_capital_pct = 0.15
            notes.append("Severe drawdown >=20% - deploy only exceptional distress")

        findings.append(self.create_finding(
            title=f"Distressed Deal Macro Gate: {gate}",
            description=" | ".join(notes) if notes else "Macro conditions supportive of deployment.",
            severity=severity,
            confidence=0.85,
            market_type="real_estate",
            metadata={
                "gate": gate,
                "regime": regime,
                "volatility": vol,
                "portfolio_drawdown": drawdown,
                "mos_multiplier": mos_multiplier,
                "max_capital_pct": max_capital_pct,
            }
        ))

        return findings

    def analyze(self) -> List[Dict[str, Any]]:
        """
        Live analysis mode - fetches current regime and drawdown from system state.
        """
        from services.api_toggle import api_guard
        if not api_guard("yahoo_finance", "distressed macro gate market data"):
            return []

        from analytics.regime import classify_regime
        from portfolio.governor import PortfolioDrawdownGovernor
        import yfinance as yf
        import pandas as pd
        
        try:
            spy = yf.download("SPY", period="1y", interval="1d", progress=False)
            vix = yf.download("^VIX", period="1y", interval="1d", progress=False)
            
            if spy.empty:
                return []
            
            spy.index = pd.to_datetime(spy.index).tz_localize(None)
            if not vix.empty:
                vix.index = pd.to_datetime(vix.index).tz_localize(None)
            
            regime_result = classify_regime(spy.tail(252), vix.tail(252) if not vix.empty else None)
            
            close = spy["Close"].astype(float)
            hi = close.tail(252).max()
            drawdown = float(close.iloc[-1] / hi - 1.0) if hi > 0 else 0.0
            
            class MockCtx:
                def __init__(self, meta):
                    self.meta = meta
            
            ctx = MockCtx({
                "regime": regime_result.regime,
                "vol_label": regime_result.vol_label,
                "portfolio_drawdown": drawdown,
            })
            
            return self.analyze_ctx(ctx)
            
        except Exception as e:
            return [self.create_finding(
                title="DistressedMacroGateAgent Error",
                description=str(e),
                severity="medium",
                confidence=0.5,
                market_type="system",
                metadata={"error": repr(e)}
            )]
