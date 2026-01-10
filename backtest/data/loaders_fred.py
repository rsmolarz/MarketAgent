from __future__ import annotations
from typing import Optional
import pandas as pd

from .cache import load_cache, save_cache


def load_fred_series(series_id: str, start: str, end: str) -> pd.DataFrame:
    """
    Load FRED economic data series. Cached to parquet.
    Requires pandas-datareader or fredapi for live data.
    """
    key = f"fred_{series_id}_{start}_{end}"
    cached = load_cache(key)
    if cached is not None and len(cached) > 0:
        return cached

    try:
        import pandas_datareader.data as web
        df = web.DataReader(series_id, 'fred', start, end)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        save_cache(key, df)
        return df
    except ImportError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()
