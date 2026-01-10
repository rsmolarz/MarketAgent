"""
Technical Analysis Indicator Utilities
Shared by overlay service, signals, and regime detection
"""
import pandas as pd
import numpy as np


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average"""
    return series.ewm(span=span, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD line, signal line, and histogram"""
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(close: pd.Series, window: int = 20, n_std: float = 2.0):
    """Bollinger Bands (middle, upper, lower)"""
    middle = close.rolling(window).mean()
    sd = close.rolling(window).std()
    upper = middle + n_std * sd
    lower = middle - n_std * sd
    return middle, upper, lower


def ma(close: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average"""
    return close.rolling(window).mean()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range"""
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average Directional Index (trend strength)"""
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    
    atr_val = atr(high, low, close, period)
    
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr_val.replace(0, 1e-9))
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr_val.replace(0, 1e-9))
    
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-9))
    adx_val = dx.rolling(period).mean()
    
    return adx_val


def ma_slope(series: pd.Series, lookback: int = 5) -> float:
    """Calculate slope of last N values using linear regression"""
    if len(series) < lookback:
        return 0.0
    
    recent = series.dropna().tail(lookback).values
    if len(recent) < 2:
        return 0.0
    
    x = np.arange(len(recent))
    try:
        slope = np.polyfit(x, recent, 1)[0]
        return float(slope)
    except Exception:
        return 0.0
