"""
Backtest Service

Agent vs SPY backtesting by regime for performance attribution.
"""
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


def load_spy() -> Optional[pd.DataFrame]:
    """Load SPY price data."""
    from data_sources.price_loader import load_symbol_frame
    return load_symbol_frame("SPY")


def load_symbol(symbol: str) -> Optional[pd.DataFrame]:
    """Load symbol price data."""
    from data_sources.price_loader import load_symbol_frame
    return load_symbol_frame(symbol)


def backtest_agent_vs_spy(
    agent_name: str,
    symbol: str,
    regime_series: Optional[pd.Series] = None
) -> List[Dict[str, Any]]:
    """
    Backtest an agent's symbol against SPY by regime.
    
    Args:
        agent_name: Name of the agent
        symbol: Symbol to backtest
        regime_series: Optional regime labels aligned to dates
        
    Returns:
        List of regime performance dicts:
        [
            {
                "regime": str,
                "agent_return": float,
                "spy_return": float,
                "alpha": float,
                "count": int
            }
        ]
    """
    prices = load_symbol(symbol)
    spy = load_spy()
    
    if prices is None or spy is None:
        logger.warning(f"Could not load data for {symbol} or SPY")
        return []
    
    if len(prices) < 20 or len(spy) < 20:
        logger.warning(f"Insufficient data for backtest")
        return []
    
    try:
        prices = prices.reset_index()
        spy = spy.reset_index()
        
        if "Date" not in prices.columns:
            prices["Date"] = prices.index
        if "Date" not in spy.columns:
            spy["Date"] = spy.index
        
        merged = prices.merge(spy[["Date", "Close"]], on="Date", suffixes=("", "_spy"))
        
        if len(merged) < 20:
            logger.warning(f"Insufficient merged data for backtest")
            return []
        
        merged["ret"] = merged["Close"].pct_change()
        merged["spy_ret"] = merged["Close_spy"].pct_change()
        
        if regime_series is not None and len(regime_series) == len(merged):
            merged["regime"] = regime_series.values
        else:
            merged["regime"] = classify_regimes(merged)
        
        results = []
        for regime, grp in merged.groupby("regime"):
            if len(grp) < 5:
                continue
                
            agent_ret = grp["ret"].mean()
            spy_ret = grp["spy_ret"].mean()
            
            results.append({
                "agent": agent_name,
                "symbol": symbol,
                "regime": str(regime),
                "agent_return": float(agent_ret) if pd.notna(agent_ret) else 0.0,
                "spy_return": float(spy_ret) if pd.notna(spy_ret) else 0.0,
                "alpha": float(agent_ret - spy_ret) if pd.notna(agent_ret) and pd.notna(spy_ret) else 0.0,
                "count": len(grp)
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Backtest error for {agent_name}/{symbol}: {e}")
        return []


def classify_regimes(df: pd.DataFrame) -> pd.Series:
    """
    Classify market regimes based on volatility and trend.
    
    Returns:
        Series with regime labels: "risk_on", "risk_off", "volatile", "calm"
    """
    if "Close" not in df.columns:
        return pd.Series(["unknown"] * len(df), index=df.index)
    
    try:
        close = df["Close"].astype(float)
        
        ret = close.pct_change()
        vol = ret.rolling(20).std()
        ma50 = close.rolling(50).mean()
        
        regimes = []
        for i in range(len(df)):
            if i < 50:
                regimes.append("unknown")
                continue
            
            current_vol = vol.iloc[i] if pd.notna(vol.iloc[i]) else 0.02
            current_price = close.iloc[i]
            current_ma = ma50.iloc[i] if pd.notna(ma50.iloc[i]) else current_price
            
            high_vol = current_vol > 0.02
            uptrend = current_price > current_ma
            
            if uptrend and not high_vol:
                regimes.append("risk_on")
            elif uptrend and high_vol:
                regimes.append("volatile")
            elif not uptrend and high_vol:
                regimes.append("risk_off")
            else:
                regimes.append("calm")
        
        return pd.Series(regimes, index=df.index)
        
    except Exception as e:
        logger.warning(f"Regime classification error: {e}")
        return pd.Series(["unknown"] * len(df), index=df.index)


def get_agent_performance_by_regime(agent_name: str) -> List[Dict[str, Any]]:
    """
    Get agent's historical performance grouped by regime.
    
    Aggregates findings and returns by regime.
    """
    from models import Finding, AgentCouncilStat
    from sqlalchemy import func
    
    try:
        stats = AgentCouncilStat.query.filter_by(agent_name=agent_name).all()
        
        results = []
        for stat in stats:
            total = stat.votes_act + stat.votes_watch + stat.votes_ignore
            if total == 0:
                continue
                
            results.append({
                "agent": agent_name,
                "regime": stat.regime,
                "act_rate": stat.votes_act / total,
                "watch_rate": stat.votes_watch / total,
                "ignore_rate": stat.votes_ignore / total,
                "total_votes": total,
                "alpha_estimate": (stat.votes_act - stat.votes_ignore) / total * 0.01
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Agent performance lookup error: {e}")
        return []
