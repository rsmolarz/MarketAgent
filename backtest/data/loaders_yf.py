from __future__ import annotations
from typing import Dict, Optional
import pandas as pd

from .cache import load_cache, save_cache

def load_yf_history(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    Daily OHLCV via yfinance. Cached to parquet.
    """
    key = f"yf_{symbol}_{start}_{end}"
    cached = load_cache(key)
    if cached is not None and len(cached) > 0:
        return cached

    import yfinance as yf

    df = yf.download(symbol, start=start, end=end, auto_adjust=False, progress=False)
    df = df.rename(columns={c: c.lower() for c in df.columns})
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    save_cache(key, df)
    return df


def slice_asof(df: pd.DataFrame, asof_date: pd.Timestamp, lookback_days: int = 252) -> pd.DataFrame:
    """
    Return lookback window ending at asof_date (inclusive).
    """
    df = df.loc[:asof_date].copy()
    if len(df) <= lookback_days:
        return df
    return df.iloc[-lookback_days:]
