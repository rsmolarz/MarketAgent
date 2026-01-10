"""
TA Regime Attribution
Determines if market is in trend or mean-reversion mode
"""
import logging
from typing import Dict, Any
import pandas as pd

from ta.indicators import rsi, ma, adx, ma_slope

logger = logging.getLogger(__name__)


def classify_ta_regime(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Classify market regime based on TA indicators
    
    Returns:
        {
            "ta_regime": "trend" | "mean_reversion" | "mixed",
            "confidence": 0.0-1.0,
            "trend_direction": "up" | "down" | "neutral",
            "indicators": {...}
        }
    """
    if df is None or df.empty or len(df) < 60:
        return {
            "ta_regime": "mixed",
            "confidence": 0.0,
            "trend_direction": "neutral",
            "indicators": {}
        }
    
    try:
        close = df["Close"].astype(float)
        high = df["High"].astype(float) if "High" in df.columns else close
        low = df["Low"].astype(float) if "Low" in df.columns else close
        
        current_price = float(close.iloc[-1])
        
        ma20 = ma(close, 20)
        ma50 = ma(close, 50)
        ma200 = ma(close, 200)
        
        current_ma20 = float(ma20.iloc[-1]) if not pd.isna(ma20.iloc[-1]) else current_price
        current_ma50 = float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else current_price
        current_ma200 = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else current_price
        
        rsi_val = rsi(close, 14)
        current_rsi = float(rsi_val.iloc[-1]) if not pd.isna(rsi_val.iloc[-1]) else 50.0
        
        adx_val = adx(high, low, close, 14)
        current_adx = float(adx_val.iloc[-1]) if not pd.isna(adx_val.iloc[-1]) else 20.0
        
        ma200_slope = ma_slope(ma200, 10)
        ma50_slope = ma_slope(ma50, 10)
        
        trend_score = 0.0
        mean_rev_score = 0.0
        
        if current_adx > 25:
            trend_score += 0.3
        elif current_adx < 20:
            mean_rev_score += 0.3
        
        if current_price > current_ma200 and ma200_slope > 0:
            trend_score += 0.2
        elif current_price < current_ma200 and ma200_slope < 0:
            trend_score += 0.2
        else:
            mean_rev_score += 0.2
        
        if current_ma20 > current_ma50 > current_ma200:
            trend_score += 0.2
        elif current_ma20 < current_ma50 < current_ma200:
            trend_score += 0.2
        else:
            mean_rev_score += 0.15
        
        if 40 <= current_rsi <= 60:
            mean_rev_score += 0.15
        elif current_rsi > 70 or current_rsi < 30:
            mean_rev_score += 0.1
        else:
            trend_score += 0.1
        
        if abs(ma50_slope) > abs(ma200_slope) * 1.5:
            trend_score += 0.1
        else:
            mean_rev_score += 0.1
        
        if trend_score > mean_rev_score + 0.15:
            regime = "trend"
            confidence = min(trend_score, 1.0)
        elif mean_rev_score > trend_score + 0.15:
            regime = "mean_reversion"
            confidence = min(mean_rev_score, 1.0)
        else:
            regime = "mixed"
            confidence = 0.5
        
        if current_price > current_ma200 and ma200_slope > 0:
            trend_direction = "up"
        elif current_price < current_ma200 and ma200_slope < 0:
            trend_direction = "down"
        else:
            trend_direction = "neutral"
        
        return {
            "ta_regime": regime,
            "confidence": round(confidence, 3),
            "trend_direction": trend_direction,
            "indicators": {
                "adx": round(current_adx, 2),
                "rsi": round(current_rsi, 2),
                "ma200_slope": round(ma200_slope, 4),
                "ma50_slope": round(ma50_slope, 4),
                "price_vs_ma200": round((current_price / current_ma200 - 1) * 100, 2),
                "ma_alignment": "bullish" if current_ma20 > current_ma50 > current_ma200 else (
                    "bearish" if current_ma20 < current_ma50 < current_ma200 else "mixed"
                )
            }
        }
        
    except Exception as e:
        logger.error(f"TA regime classification error: {e}")
        return {
            "ta_regime": "mixed",
            "confidence": 0.0,
            "trend_direction": "neutral",
            "indicators": {}
        }


def get_regime_agent_weights(ta_regime: str) -> Dict[str, float]:
    """
    Return agent weight adjustments based on TA regime
    
    Trend regime: boost momentum/trend-following agents
    Mean-reversion regime: boost mean-reversion/contrarian agents
    """
    if ta_regime == "trend":
        return {
            "TechnicalAnalysisAgent": 1.2,
            "EquityMomentumAgent": 1.3,
            "MacroWatcherAgent": 1.1,
            "SentimentDivergenceAgent": 0.8,
            "ArbitrageFinderAgent": 0.9,
        }
    elif ta_regime == "mean_reversion":
        return {
            "TechnicalAnalysisAgent": 1.0,
            "EquityMomentumAgent": 0.7,
            "MacroWatcherAgent": 0.9,
            "SentimentDivergenceAgent": 1.2,
            "ArbitrageFinderAgent": 1.3,
        }
    else:
        return {}
