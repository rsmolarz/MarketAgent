from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class RegimeResult:
    regime: str                 # "trend" | "mean_reversion" | "volatility" | "transition" | "unknown"
    risk: str                   # "risk_on" | "risk_off" | "mixed"
    vol_label: str              # "calm" | "elevated" | "high"
    score: float                # 0..1 confidence-ish
    details: Dict[str, float]

def _rolling_vol(close: pd.Series, window: int = 20) -> float:
    r = close.pct_change().dropna()
    if len(r) < window + 5:
        return float("nan")
    return float(r.tail(window).std() * np.sqrt(252))

def _slope(close: pd.Series, window: int = 63) -> float:
    if len(close) < window:
        return float("nan")
    y = close.tail(window).values.astype(float)
    x = np.arange(len(y), dtype=float)
    beta = np.polyfit(x, y, 1)[0]
    return float(beta / (np.mean(y) + 1e-12))

def classify_regime(spy_df: pd.DataFrame, vix_df: Optional[pd.DataFrame] = None) -> RegimeResult:
    if spy_df is None or spy_df.empty or "Close" not in spy_df.columns:
        return RegimeResult("unknown", "mixed", "elevated", 0.0, {})

    close = spy_df["Close"].astype(float)
    vol20 = _rolling_vol(close, 20)
    sl63 = _slope(close, 63)
    sl252 = _slope(close, 252)

    vix = None
    if vix_df is not None and not vix_df.empty and "Close" in vix_df.columns:
        vix = float(vix_df["Close"].astype(float).iloc[-1])

    vol_label = "elevated"
    if np.isfinite(vol20):
        if vol20 < 0.16: vol_label = "calm"
        elif vol20 < 0.25: vol_label = "elevated"
        else: vol_label = "high"
    if vix is not None:
        if vix < 18: vol_label = "calm"
        elif vix < 28: vol_label = "elevated"
        else: vol_label = "high"

    transition = False
    if np.isfinite(sl63) and np.isfinite(sl252):
        transition = (sl63 > 0 and sl252 < 0) or (sl63 < 0 and sl252 > 0)

    if vol_label == "high":
        regime = "volatility"
        risk = "risk_off"
        score = 0.8
    elif transition:
        regime = "transition"
        risk = "mixed"
        score = 0.65
    else:
        if np.isfinite(sl252) and abs(sl252) > 0.00035:
            regime = "trend"
            risk = "risk_on" if sl252 > 0 else "risk_off"
            score = 0.7
        else:
            regime = "mean_reversion"
            risk = "mixed"
            score = 0.6

    return RegimeResult(
        regime=regime,
        risk=risk,
        vol_label=vol_label,
        score=float(score),
        details={
            "vol20_ann": float(vol20) if np.isfinite(vol20) else -1.0,
            "slope63_norm": float(sl63) if np.isfinite(sl63) else 0.0,
            "slope252_norm": float(sl252) if np.isfinite(sl252) else 0.0,
            "vix": float(vix) if vix is not None else -1.0,
        },
    )
