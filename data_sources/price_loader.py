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


def _try_schwab_history(symbol: str, start: str = "2007-01-01") -> pd.DataFrame:
    """Attempt to load price history from Schwab API as fallback."""
    try:
        from data_sources.schwab_client import get_schwab_client
        client = get_schwab_client()
        if not client._ensure_token():
            return pd.DataFrame()
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        days_back = max(30, (datetime.now() - start_dt).days)
        data = client.get_daily_history(symbol, days=days_back)
        if not data:
            return pd.DataFrame()
        candles = data.get("candles", [])
        if not candles:
            return pd.DataFrame()
        rows = []
        for c in candles:
            dt = datetime.fromtimestamp(c["datetime"] / 1000) if c.get("datetime") else None
            if dt and c.get("close"):
                rows.append({"Date": dt, "Close": float(c["close"])})
        if rows:
            logger.info(f"Schwab fallback loaded {len(rows)} rows for {symbol}")
            return pd.DataFrame(rows)
    except Exception as e:
        logger.debug(f"Schwab fallback for {symbol}: {e}")
    return pd.DataFrame()


def load_symbol(symbol: str, start: str = "2007-01-01", use_cache: bool = True) -> pd.DataFrame:
    """
    Load any symbol's price data with caching.
    Falls back to Schwab API if Yahoo Finance fails.
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
            raise ValueError(f"Empty yfinance result for {symbol}")
        
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
        logger.warning(f"Yahoo Finance failed for {symbol}: {e}, trying Schwab fallback")
        schwab_df = _try_schwab_history(symbol, start=start)
        if not schwab_df.empty:
            schwab_df.to_parquet(cache_file, index=False)
            return schwab_df
        if cache_file.exists():
            return pd.read_parquet(cache_file)
        return pd.DataFrame(columns=["Date", "Close"])
