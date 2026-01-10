"""
Regime Detection: Risk-on / Risk-off overlay using SPY + VIX.

Rules:
  - risk_on: SPY above 200d MA and VIX < 20
  - risk_off: SPY below 200d MA or VIX >= 25
  - transition: everything else
"""
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def compute_regime(spy: pd.DataFrame, vix: pd.DataFrame) -> pd.DataFrame:
    """
    Compute daily regime classification.
    
    Args:
        spy: DataFrame with Date, Close columns
        vix: DataFrame with Date, Close columns
        
    Returns:
        DataFrame with Date, regime, VIX, Close, ma200 columns
    """
    s = spy.copy()
    s["Date"] = pd.to_datetime(s["Date"]).dt.tz_localize(None)
    s = s.sort_values("Date")
    s["ma200"] = s["Close"].rolling(200).mean()

    v = vix.copy()
    v["Date"] = pd.to_datetime(v["Date"]).dt.tz_localize(None)
    v = v.sort_values("Date")[["Date", "Close"]].rename(columns={"Close": "VIX"})

    df = pd.merge_asof(s[["Date", "Close", "ma200"]], v, on="Date", direction="backward")
    df = df.dropna()

    def label(row):
        above = row["Close"] >= row["ma200"]
        vix_val = row["VIX"]
        if above and vix_val < 20:
            return "risk_on"
        if (not above) or vix_val >= 25:
            return "risk_off"
        return "transition"

    df["regime"] = df.apply(label, axis=1)
    return df[["Date", "regime", "VIX", "Close", "ma200"]]


def load_regime_data(start: str = "2007-01-01") -> pd.DataFrame:
    """Load SPY and VIX data and compute regimes."""
    import yfinance as yf
    
    spy_raw = yf.download("SPY", start=start, progress=False)
    vix_raw = yf.download("^VIX", start=start, progress=False)
    
    if spy_raw.empty or vix_raw.empty:
        logger.warning("Could not load SPY or VIX data for regime detection")
        return pd.DataFrame()
    
    spy_raw = spy_raw.reset_index()
    vix_raw = vix_raw.reset_index()
    
    if "Date" in spy_raw.columns:
        spy = pd.DataFrame({
            "Date": spy_raw["Date"],
            "Close": spy_raw["Close"].values.flatten() if hasattr(spy_raw["Close"].values, 'flatten') else spy_raw["Close"]
        })
    else:
        spy = pd.DataFrame({
            "Date": spy_raw.iloc[:, 0],
            "Close": spy_raw.iloc[:, 4].values.flatten() if hasattr(spy_raw.iloc[:, 4].values, 'flatten') else spy_raw.iloc[:, 4]
        })
    
    if "Date" in vix_raw.columns:
        vix = pd.DataFrame({
            "Date": vix_raw["Date"],
            "Close": vix_raw["Close"].values.flatten() if hasattr(vix_raw["Close"].values, 'flatten') else vix_raw["Close"]
        })
    else:
        vix = pd.DataFrame({
            "Date": vix_raw.iloc[:, 0],
            "Close": vix_raw.iloc[:, 4].values.flatten() if hasattr(vix_raw.iloc[:, 4].values, 'flatten') else vix_raw.iloc[:, 4]
        })
    
    return compute_regime(spy, vix)


def get_regime_at_date(regimes: pd.DataFrame, target_date) -> str:
    """Get regime for a specific date (or nearest prior)."""
    if regimes.empty:
        return "unknown"
    
    target = pd.to_datetime(target_date)
    if target.tz is not None:
        target = target.tz_localize(None)
    
    mask = regimes["Date"] <= target
    if mask.any():
        return regimes.loc[mask, "regime"].iloc[-1]
    return "unknown"
