"""
Technical Analysis Signal Generation

Produces RSI / MACD / MA / Bollinger / Support-Resistance signals
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Compute MACD line, signal line, and histogram"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(prices: pd.Series, period: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Compute Bollinger Bands (upper, middle, lower)"""
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return upper, middle, lower


def find_support_resistance(prices: pd.Series, lookback: int = 20) -> Tuple[float, float]:
    """Find recent support and resistance levels"""
    recent = prices.tail(lookback)
    support = recent.min()
    resistance = recent.max()
    return support, resistance


def generate_signals(symbol: str, df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generate technical analysis signals from price data
    
    Args:
        symbol: Ticker symbol
        df: DataFrame with OHLCV data (must have 'Close' column)
        
    Returns:
        Tuple of (signals list, ta_snapshot dict)
    """
    signals = []
    
    close = df['Close'] if 'Close' in df.columns else df['close']
    high = df['High'] if 'High' in df.columns else df.get('high', close)
    low = df['Low'] if 'Low' in df.columns else df.get('low', close)
    
    rsi = compute_rsi(close)
    macd_line, signal_line, macd_hist = compute_macd(close)
    bb_upper, bb_middle, bb_lower = compute_bollinger_bands(close)
    support, resistance = find_support_resistance(close)
    
    ma20 = close.rolling(window=20).mean()
    ma50 = close.rolling(window=50).mean()
    
    current_price = float(close.iloc[-1])
    current_rsi = float(rsi.iloc[-1])
    current_macd = float(macd_line.iloc[-1])
    current_signal = float(signal_line.iloc[-1])
    current_hist = float(macd_hist.iloc[-1])
    prev_hist = float(macd_hist.iloc[-2]) if len(macd_hist) > 1 else 0
    current_ma20 = float(ma20.iloc[-1])
    current_ma50 = float(ma50.iloc[-1])
    current_bb_upper = float(bb_upper.iloc[-1])
    current_bb_lower = float(bb_lower.iloc[-1])
    
    ta_snapshot = {
        "rsi": current_rsi,
        "macd": current_macd,
        "macd_signal": current_signal,
        "macd_hist": current_hist,
        "ma20": current_ma20,
        "ma50": current_ma50,
        "bb_upper": current_bb_upper,
        "bb_lower": current_bb_lower,
        "support": float(support),
        "resistance": float(resistance),
        "price": current_price
    }
    
    if current_rsi < 30:
        signals.append({
            "type": "RSI_OVERSOLD",
            "bias": "bullish",
            "confidence": min(0.9, (30 - current_rsi) / 30 + 0.5),
            "value": current_rsi,
            "threshold": 30
        })
    elif current_rsi > 70:
        signals.append({
            "type": "RSI_OVERBOUGHT",
            "bias": "bearish",
            "confidence": min(0.9, (current_rsi - 70) / 30 + 0.5),
            "value": current_rsi,
            "threshold": 70
        })
    
    if current_hist > 0 and prev_hist <= 0:
        signals.append({
            "type": "MACD_BULLISH_CROSS",
            "bias": "bullish",
            "confidence": min(0.8, abs(current_hist) * 10 + 0.5),
            "value": current_hist
        })
    elif current_hist < 0 and prev_hist >= 0:
        signals.append({
            "type": "MACD_BEARISH_CROSS",
            "bias": "bearish",
            "confidence": min(0.8, abs(current_hist) * 10 + 0.5),
            "value": current_hist
        })
    
    if current_ma20 > current_ma50:
        if len(ma20) > 1 and len(ma50) > 1:
            prev_ma20 = float(ma20.iloc[-2])
            prev_ma50 = float(ma50.iloc[-2])
            if prev_ma20 <= prev_ma50:
                signals.append({
                    "type": "GOLDEN_CROSS",
                    "bias": "bullish",
                    "confidence": 0.75,
                    "ma20": current_ma20,
                    "ma50": current_ma50
                })
    elif current_ma20 < current_ma50:
        if len(ma20) > 1 and len(ma50) > 1:
            prev_ma20 = float(ma20.iloc[-2])
            prev_ma50 = float(ma50.iloc[-2])
            if prev_ma20 >= prev_ma50:
                signals.append({
                    "type": "DEATH_CROSS",
                    "bias": "bearish",
                    "confidence": 0.75,
                    "ma20": current_ma20,
                    "ma50": current_ma50
                })
    
    if current_price <= current_bb_lower * 1.01:
        signals.append({
            "type": "BB_LOWER_TOUCH",
            "bias": "bullish",
            "confidence": 0.65,
            "price": current_price,
            "bb_lower": current_bb_lower
        })
    elif current_price >= current_bb_upper * 0.99:
        signals.append({
            "type": "BB_UPPER_TOUCH",
            "bias": "bearish",
            "confidence": 0.65,
            "price": current_price,
            "bb_upper": current_bb_upper
        })
    
    support_distance = (current_price - support) / current_price
    resistance_distance = (resistance - current_price) / current_price
    
    if support_distance < 0.02:
        signals.append({
            "type": "NEAR_SUPPORT",
            "bias": "bullish",
            "confidence": max(0.5, 0.8 - support_distance * 10),
            "price": current_price,
            "support": float(support)
        })
    
    if resistance_distance < 0.02:
        signals.append({
            "type": "NEAR_RESISTANCE",
            "bias": "bearish",
            "confidence": max(0.5, 0.8 - resistance_distance * 10),
            "price": current_price,
            "resistance": float(resistance)
        })
    
    trend_bias = "bullish" if current_price > current_ma50 else "bearish"
    if not signals:
        signals.append({
            "type": "TREND_CONTINUATION",
            "bias": trend_bias,
            "confidence": 0.5,
            "price": current_price,
            "ma50": current_ma50
        })
    
    return signals, ta_snapshot
