from __future__ import annotations
import numpy as np
import pandas as pd
from portfolio.governor import PortfolioDrawdownGovernor, findings_to_risk_signal, allocate_exposure
from analytics.regime import classify_regime

def spy_drawdown(spy_df: pd.DataFrame, lookback_high: int = 252) -> float:
    c = spy_df["Close"].astype(float)
    hi = c.tail(lookback_high).max()
    if hi <= 0:
        return 0.0
    return float(c.iloc[-1] / hi - 1.0)

def compute_targets(spy_df: pd.DataFrame, vix_df: pd.DataFrame, findings: list[dict]):
    rr = classify_regime(spy_df.tail(252), vix_df.tail(252))
    dd = spy_drawdown(spy_df.tail(252), 252)

    gov = PortfolioDrawdownGovernor().compute(dd)
    risk = findings_to_risk_signal(findings)

    return allocate_exposure(
        base_target=1.0,
        risk_signal=risk,
        regime=rr.regime,
        vol_label=rr.vol_label,
        governor=gov,
    )
