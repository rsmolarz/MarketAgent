"""
TA Confirmation Service

Provides technical analysis confirmation scoring for findings.
Used in combined TA + LLM decision scoring.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def get_ta_state(symbol: str) -> Dict[str, Any]:
    """
    Get current TA state for a symbol.
    
    Returns:
        {
            "regime": "trend" | "mean_reversion" | "mixed",
            "direction": "up" | "down" | "neutral",
            "rsi": float,
            "trend_strength": float
        }
    """
    from data_sources.price_loader import load_symbol_frame
    from ta.regime import classify_ta_regime
    from ta.ta_engine import rsi
    
    if not symbol:
        return None
    
    try:
        df = load_symbol_frame(symbol)
        if df is None or len(df) < 60:
            return None
        
        ta = classify_ta_regime(df)
        
        close = df["Close"].astype(float)
        rsi_val = float(rsi(close, 14).iloc[-1])
        
        return {
            "regime": ta["ta_regime"],
            "direction": ta["trend_direction"],
            "rsi": rsi_val,
            "trend_strength": ta.get("confidence", 0.5)
        }
        
    except Exception as e:
        logger.warning(f"get_ta_state error for {symbol}: {e}")
        return None


def ta_confirmation_score(symbol: str) -> float:
    """
    Get TA confirmation score for a symbol.
    
    Returns:
        float: 0.0 - 1.0 confidence score
        
    Decision logic:
        - Trend with direction: 0.85
        - Mean reversion: 0.65
        - Mixed/unknown: 0.4
    """
    ta = get_ta_state(symbol)
    
    if not ta:
        return 0.5
    
    if ta["regime"] == "trend" and ta["direction"] in ("up", "down"):
        return 0.85
    
    if ta["regime"] == "mean_reversion":
        return 0.65
    
    return 0.4


def combined_confidence(llm_confidence: float, symbol: str) -> float:
    """
    Calculate combined TA + LLM confidence.
    
    Formula: 0.65 * llm + 0.35 * ta (institutional weighting)
    """
    ta_score = ta_confirmation_score(symbol)
    return round(0.65 * llm_confidence + 0.35 * ta_score, 4)


def should_act(finding, council_result: dict) -> bool:
    """
    Determine if a finding should trigger action.
    
    Requires:
        - Critical severity
        - LLM council consensus = ACT
        - TA confirmation score >= 0.7
    """
    severity = getattr(finding, "severity", "") or ""
    if severity.lower() != "critical":
        return False
    
    if council_result.get("consensus") != "ACT":
        return False
    
    ta_score = ta_confirmation_score(getattr(finding, "symbol", None))
    if ta_score < 0.7:
        return False
    
    return True
