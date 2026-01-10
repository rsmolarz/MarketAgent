from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

try:
    import yfinance as yf
except Exception as e:
    raise RuntimeError("yfinance is required. Add it to pyproject.toml deps.") from e

CACHE_DIR = Path("data_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(symbol: str, start: str, end: str) -> Path:
    safe_sym = symbol.replace("^", "_").replace("/", "_")
    return CACHE_DIR / f"yf_{safe_sym}_{start}_{end}.parquet"


def fetch_daily(symbols: List[str], start: str, end: str, use_cache: bool = True) -> Dict[str, pd.DataFrame]:
    """
    Fetch daily OHLCV for symbols from Yahoo. Returns dict[symbol -> df].
    Index is timezone-naive pandas DatetimeIndex.
    Caches to parquet for efficiency.
    """
    out: Dict[str, pd.DataFrame] = {}

    for sym in symbols:
        cache_file = _cache_path(sym, start, end)
        
        if use_cache and cache_file.exists():
            df = pd.read_parquet(cache_file)
            out[sym] = df
            continue

        df = yf.download(sym, start=start, end=end, interval="1d", auto_adjust=False, progress=False)
        if df is None or df.empty:
            out[sym] = pd.DataFrame()
            continue
        df = df.copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        
        if use_cache:
            df.to_parquet(cache_file)
        
        out[sym] = df

    return out


def slice_asof(df: pd.DataFrame, asof: datetime) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    return df.loc[df.index <= pd.to_datetime(asof)]
