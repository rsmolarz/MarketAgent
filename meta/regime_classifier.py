"""
Regime Detection Overlay

Classifies macro market regimes using observable indicators.
Works with signal clustering + allocator.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RegimeClassifier:
    def __init__(
        self,
        vix_high: float = 25,
        vix_low: float = 18,
        rate_move_threshold: float = 0.5
    ):
        self.vix_high = vix_high
        self.vix_low = vix_low
        self.rate_move_threshold = rate_move_threshold

    def classify(
        self,
        spy_df: pd.DataFrame,
        vix_df: pd.DataFrame,
        tnx_df: Optional[pd.DataFrame] = None
    ) -> Dict[pd.Timestamp, str]:
        """
        Returns regime label for each date.
        
        Regimes:
        - risk_on: SPY up, VIX low
        - risk_off: SPY down, VIX high
        - vol_spike: VIX high (regardless of SPY)
        - rates_rising: 10Y yield up fast
        - rates_falling: 10Y yield down fast
        - neutral: none of the above
        """
        regimes = {}

        dates = spy_df.index.intersection(vix_df.index)
        if tnx_df is not None:
            dates = dates.intersection(tnx_df.index)

        for dt in dates:
            try:
                spy_slice = spy_df.loc[:dt]
                if len(spy_slice) < 21:
                    continue
                    
                close_col = 'Close' if 'Close' in spy_df.columns else spy_df.columns[0]
                spy_ret = spy_slice[close_col].pct_change(20).iloc[-1]
                
                vix_close = 'Close' if 'Close' in vix_df.columns else vix_df.columns[0]
                vix = vix_df.loc[dt][vix_close]
                
                rate_20d = 0.0
                if tnx_df is not None and dt in tnx_df.index:
                    tnx_slice = tnx_df.loc[:dt]
                    if len(tnx_slice) >= 21:
                        tnx_close = 'Close' if 'Close' in tnx_df.columns else tnx_df.columns[0]
                        rate_20d = tnx_slice[tnx_close].diff(20).iloc[-1]

                if vix >= self.vix_high and spy_ret < 0:
                    regime = "risk_off"
                elif vix <= self.vix_low and spy_ret > 0:
                    regime = "risk_on"
                elif vix >= self.vix_high:
                    regime = "vol_spike"
                elif rate_20d >= self.rate_move_threshold:
                    regime = "rates_rising"
                elif rate_20d <= -self.rate_move_threshold:
                    regime = "rates_falling"
                else:
                    regime = "neutral"

                regimes[dt] = regime
            except Exception:
                continue

        return regimes


def attach_regimes(
    backtest_records: List[Dict],
    regime_map: Dict
) -> List[Dict]:
    """
    Enrich backtest records with regime labels.
    No agent changes. No scheduler changes.
    """
    for r in backtest_records:
        asof = r.get("asof") or r.get("timestamp")
        if isinstance(asof, str):
            asof = pd.to_datetime(asof)
        r["regime"] = regime_map.get(asof, "unknown")
    return backtest_records


def regime_performance(
    records: List[Dict],
    level: str = "agent"
) -> Dict:
    """
    Compute regime performance by agent or cluster.
    
    Args:
        records: backtest records with regime labels
        level: "agent" or "cluster"
    
    Returns:
        Dict mapping (name, regime) -> {mean_return, hit_rate, count}
    """
    stats = defaultdict(list)

    for r in records:
        key_name = r.get(level) or r.get("agent_name") or r.get("agent")
        regime = r.get("regime", "unknown")
        fwd_ret = r.get("forward_return_20d") or r.get("fwd_ret_20d")
        
        if key_name and fwd_ret is not None:
            key = (key_name, regime)
            stats[key].append(fwd_ret)

    summary = {}
    for (name, regime), vals in stats.items():
        arr = np.array(vals)
        summary[(name, regime)] = {
            "mean_return": float(np.mean(arr)),
            "hit_rate": float((arr > 0).mean()),
            "count": len(vals)
        }

    return summary


def get_current_regime(
    spy_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    tnx_df: Optional[pd.DataFrame] = None
) -> str:
    """
    Get the current regime based on latest data.
    """
    classifier = RegimeClassifier()
    regimes = classifier.classify(spy_df, vix_df, tnx_df)
    
    if not regimes:
        return "unknown"
    
    latest_date = max(regimes.keys())
    return regimes[latest_date]


def compute_regime_weight_adjustment(
    agent_name: str,
    current_regime: str,
    regime_perf: Dict,
    bad_threshold: float = 0.0
) -> float:
    """
    Returns weight multiplier based on agent's performance in current regime.
    
    Returns:
        1.0 if good in regime
        0.3 if bad in regime
        0.7 if unknown/neutral
    """
    key = (agent_name, current_regime)
    
    if key not in regime_perf:
        return 0.7
    
    perf = regime_perf[key]
    
    if perf["mean_return"] < bad_threshold:
        return 0.3
    
    return 1.0
