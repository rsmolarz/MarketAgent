from __future__ import annotations
from pathlib import Path
import pandas as pd

CACHE_DIR = Path("data_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def cache_path(key: str) -> Path:
    safe = key.replace("/", "_").replace(":", "_")
    return CACHE_DIR / f"{safe}.parquet"

def load_cache(key: str):
    p = cache_path(key)
    if p.exists():
        return pd.read_parquet(p)
    return None

def save_cache(key: str, df):
    p = cache_path(key)
    df.to_parquet(p, index=True)
