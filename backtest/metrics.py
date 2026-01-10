from __future__ import annotations
from dataclasses import asdict
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

from .engine import SignalEvent

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

def _to_df(signals: List[SignalEvent]) -> pd.DataFrame:
    if not signals:
        return pd.DataFrame()
    rows = []
    for s in signals:
        r = asdict(s)
        r["ts"] = pd.to_datetime(r["ts"])
        r["sev_rank"] = SEVERITY_ORDER.get(str(r["severity"]).lower(), 0)
        rows.append(r)
    return pd.DataFrame(rows).sort_values("ts")

def compute_forward_returns(
    signals: List[SignalEvent],
    price_frames: Dict[str, pd.DataFrame],
    horizons: Tuple[int, ...] = (1, 5, 20, 60),
) -> Dict[str, Any]:
    df = _to_df(signals)
    if df.empty:
        return {"signal_count": 0, "forward": {}, "by_severity": {}, "by_confidence_bucket": {}}

    forward_stats: Dict[str, Any] = {}
    for h in horizons:
        rets = []
        for _, row in df.iterrows():
            sym = row["symbol"]
            if not sym or sym not in price_frames:
                continue
            px = price_frames[sym]
            if px.empty or "close" not in px.columns:
                continue
            ts = pd.to_datetime(row["ts"]).normalize()
            if ts not in px.index:
                prior = px.index[px.index <= ts]
                if len(prior) == 0:
                    continue
                ts = prior[-1]
            i = px.index.get_loc(ts)
            if isinstance(i, slice):
                continue
            j = i + h
            if j >= len(px.index):
                continue
            p0 = float(px["close"].iloc[i])
            p1 = float(px["close"].iloc[j])
            rets.append((p1 / p0) - 1.0)

        if len(rets) == 0:
            forward_stats[f"{h}d"] = {"n": 0, "mean": None, "median": None, "hit_rate": None}
        else:
            arr = np.array(rets, dtype=float)
            forward_stats[f"{h}d"] = {
                "n": int(len(arr)),
                "mean": float(np.mean(arr)),
                "median": float(np.median(arr)),
                "hit_rate": float(np.mean(arr > 0.0)),
            }

    by_sev = {}
    for sev in ["low", "medium", "high", "critical"]:
        sub = df[df["severity"].str.lower() == sev]
        by_sev[sev] = {"count": int(len(sub))}

    buckets = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.01)]
    by_conf = {}
    for lo, hi in buckets:
        sub = df[(df["confidence"] >= lo) & (df["confidence"] < hi)]
        by_conf[f"{lo:.2f}-{hi:.2f}"] = {"count": int(len(sub))}

    return {
        "signal_count": int(len(df)),
        "forward": forward_stats,
        "by_severity": by_sev,
        "by_confidence_bucket": by_conf,
    }
