"""
Cached price data loader for dashboard and backtesting.
"""
import yfinance as yf
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data/prices")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_spy(start: str = "2007-01-01", use_cache: bool = True) -> pd.DataFrame:
    """
    Load SPY price data with caching.
    
    Args:
        start: Start date string (YYYY-MM-DD)
        use_cache: Whether to use cached data if available
    
    Returns:
        DataFrame with Date and Close columns
    """
    cache_file = CACHE_DIR / "spy_daily.parquet"
    
    if use_cache and cache_file.exists():
        cached = pd.read_parquet(cache_file)
        cached["Date"] = pd.to_datetime(cached["Date"])
        
        cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if cache_age < timedelta(hours=12):
            return cached
    
    try:
        df = yf.download("SPY", start=start, progress=False)
        if df.empty:
            logger.warning("Empty SPY data from yfinance")
            if cache_file.exists():
                return pd.read_parquet(cache_file)
            return pd.DataFrame(columns=["Date", "Close"])
        
        df = df.reset_index()
        
        if "Date" in df.columns:
            date_col = df["Date"]
        elif ("Date", "") in df.columns:
            date_col = df[("Date", "")]
        else:
            date_col = df.iloc[:, 0]
        
        if "Close" in df.columns:
            close_col = df["Close"]
        elif ("Close", "SPY") in df.columns:
            close_col = df[("Close", "SPY")]
        else:
            for col in df.columns:
                if "close" in str(col).lower():
                    close_col = df[col]
                    break
            else:
                close_col = df.iloc[:, 4]
        
        result = pd.DataFrame({
            "Date": pd.to_datetime(date_col),
            "Close": close_col.values.flatten() if hasattr(close_col.values, 'flatten') else close_col.values
        })
        
        result.to_parquet(cache_file, index=False)
        logger.info(f"Cached SPY data: {len(result)} rows")
        
        return result
        
    except Exception as e:
        logger.error(f"Error loading SPY: {e}")
        if cache_file.exists():
            return pd.read_parquet(cache_file)
        return pd.DataFrame(columns=["Date", "Close"])


def load_symbol_frame(
    symbol: str,
    start: str = "2007-01-01",
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Standardized OHLC frame loader for TA + agents + dashboard.
    Returns DataFrame indexed by Date with Close column.
    """
    if not symbol:
        return pd.DataFrame()

    df = load_symbol(symbol, start=start, use_cache=use_cache)

    if df.empty:
        return df

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")
    df = df.set_index("Date")

    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["Close"])

    return df


def load_symbol(symbol: str, start: str = "2007-01-01", use_cache: bool = True) -> pd.DataFrame:
    """
    Load any symbol's price data with caching.
    """
    cache_file = CACHE_DIR / f"{symbol.replace('^', '_').lower()}_daily.parquet"
    
    if use_cache and cache_file.exists():
        cached = pd.read_parquet(cache_file)
        cached["Date"] = pd.to_datetime(cached["Date"])
        
        cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if cache_age < timedelta(hours=12):
            return cached
    
    try:
        df = yf.download(symbol, start=start, progress=False)
        if df.empty:
            if cache_file.exists():
                return pd.read_parquet(cache_file)
            return pd.DataFrame(columns=["Date", "Close"])
        
        df = df.reset_index()
        
        date_col = df.iloc[:, 0]
        close_col = df["Close"] if "Close" in df.columns else df.iloc[:, 4]
        
        result = pd.DataFrame({
            "Date": pd.to_datetime(date_col),
            "Close": close_col.values.flatten() if hasattr(close_col.values, 'flatten') else close_col.values
        })
        
        result.to_parquet(cache_file, index=False)
        return result
        
    except Exception as e:
        logger.error(f"Error loading {symbol}: {e}")
        if cache_file.exists():
            return pd.read_parquet(cache_file)
        return pd.DataFrame(columns=["Date", "Close"])
