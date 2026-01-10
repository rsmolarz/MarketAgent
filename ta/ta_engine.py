"""
Technical Analysis Engine

Provides TA confirmation for findings:
- RSI momentum
- MA trend confirmation
- Combined vote (ACT/WATCH/IGNORE)
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def ta_vote(df) -> dict:
    """
    Returns a TA decision: ACT/WATCH/IGNORE + rationale.
    
    ACT = strong confirmation (trend + momentum)
    WATCH = partial confirmation
    IGNORE = conflicts / neutral
    """
    if df is None or len(df) < 60 or "Close" not in df.columns:
        return {"vote": "WATCH", "score": 0.5, "reason": "insufficient price history"}

    try:
        close = df["Close"].astype(float)
        r = float(rsi(close, 14).iloc[-1])
        
        if np.isnan(r):
            r = 50.0

        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])
        px = float(close.iloc[-1])

        trend_up = (px > ma20) and (ma20 > ma50)
        trend_down = (px < ma20) and (ma20 < ma50)

        if trend_up and r >= 55:
            return {"vote": "ACT", "score": 0.85, "reason": f"trend_up + RSI {r:.1f}"}
        if trend_down and r <= 45:
            return {"vote": "ACT", "score": 0.85, "reason": f"trend_down + RSI {r:.1f}"}
        if trend_up or trend_down:
            return {"vote": "WATCH", "score": 0.60, "reason": f"trend present, RSI {r:.1f} mixed"}
        
        return {"vote": "IGNORE", "score": 0.25, "reason": f"no trend confirmation, RSI {r:.1f}"}
    
    except Exception as e:
        logger.warning(f"TA vote error: {e}")
        return {"vote": "WATCH", "score": 0.5, "reason": f"error: {str(e)}"}


def get_ta_signals(df, symbol: str = None) -> dict:
    """
    Get comprehensive TA signals for a price dataframe.
    
    Returns dict with indicators and overall vote.
    """
    if df is None or len(df) < 60 or "Close" not in df.columns:
        return {
            "symbol": symbol,
            "vote": "WATCH",
            "indicators": {},
            "reason": "insufficient data"
        }
    
    try:
        close = df["Close"].astype(float)
        
        rsi_val = float(rsi(close, 14).iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
        px = float(close.iloc[-1])
        
        vote_result = ta_vote(df)
        
        return {
            "symbol": symbol,
            "vote": vote_result["vote"],
            "score": vote_result["score"],
            "reason": vote_result["reason"],
            "indicators": {
                "price": px,
                "rsi_14": rsi_val if not np.isnan(rsi_val) else None,
                "ma_20": ma20 if not np.isnan(ma20) else None,
                "ma_50": ma50 if not np.isnan(ma50) else None,
                "ma_200": ma200 if ma200 and not np.isnan(ma200) else None,
                "above_ma20": px > ma20,
                "above_ma50": px > ma50,
                "ma20_above_ma50": ma20 > ma50,
            }
        }
    
    except Exception as e:
        logger.warning(f"TA signals error: {e}")
        return {
            "symbol": symbol,
            "vote": "WATCH",
            "indicators": {},
            "reason": f"error: {str(e)}"
        }
