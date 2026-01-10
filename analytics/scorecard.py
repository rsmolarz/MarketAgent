from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd

@dataclass
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

def compute_drawdown_event_flags(spy: pd.DataFrame, lookback_high: int = 252, dd_thresh: float = -0.10) -> pd.Series:
    close = spy["Close"].astype(float)
    rolling_high = close.rolling(lookback_high, min_periods=60).max()
    dd = (close / rolling_high) - 1.0
    return (dd <= dd_thresh)

def load_findings(path: str) -> pd.DataFrame:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    df["asof"] = pd.to_datetime(df["asof"])
    return df.sort_values("asof")

def main():
    findings_path = "backtests/market_correction_findings_2007_regime.jsonl"

    import yfinance as yf
    spy = yf.download("SPY", start="2007-01-01", end="2026-01-10", interval="1d", auto_adjust=False, progress=False)
    spy.index = pd.to_datetime(spy.index).tz_localize(None)
    spy = spy[["Open","High","Low","Close","Volume"]].dropna()

    event_flag = compute_drawdown_event_flags(spy, lookback_high=252, dd_thresh=-0.10)

    f = load_findings(findings_path)

    sig = f[(f["severity"].isin(["high","critical"]))].copy()
    sig["date"] = sig["asof"].dt.normalize()

    horizon = 63
    spy_dates = spy.index.normalize()
    event_dates = set(spy_dates[event_flag.values])

    spy_idx = pd.Index(spy_dates.unique())
    date_to_pos = {d: i for i, d in enumerate(spy_idx)}

    def has_event_within(d: pd.Timestamp) -> bool:
        if d not in date_to_pos:
            return False
        i = date_to_pos[d]
        j = min(i + horizon, len(spy_idx) - 1)
        window = spy_idx[i:j+1]
        return any(w in event_dates for w in window)

    sig["tp"] = sig["date"].apply(has_event_within)
    sig["fp"] = ~sig["tp"]

    signal_dates = set(sig["date"].unique())

    def had_signal_before_event(ev: pd.Timestamp) -> bool:
        if ev not in date_to_pos:
            return False
        i = date_to_pos[ev]
        k = max(i - horizon, 0)
        window = spy_idx[k:i+1]
        return any(w in signal_dates for w in window)

    fn_events = [ev for ev in event_dates if not had_signal_before_event(ev)]

    by_regime: Dict[str, Score] = {}
    for _, row in sig.iterrows():
        r = row.get("regime", "unknown") or "unknown"
        by_regime.setdefault(r, Score())
        if bool(row["tp"]):
            by_regime[r].tp += 1
        else:
            by_regime[r].fp += 1

    global_score = Score(
        tp=int(sig["tp"].sum()),
        fp=int(sig["fp"].sum()),
        fn=len(fn_events),
    )

    print("GLOBAL", {"tp": global_score.tp, "fp": global_score.fp, "fn": global_score.fn,
                    "precision": global_score.precision, "recall": global_score.recall})

    print("\nBY REGIME (signal-time)")
    for r, s in by_regime.items():
        print(r, {"tp": s.tp, "fp": s.fp, "fn": 0, "precision": s.precision, "recall": 0.0})

    report = {
        "global": {"tp": global_score.tp, "fp": global_score.fp, "fn": global_score.fn,
                   "precision": global_score.precision, "recall": global_score.recall},
        "by_regime": {r: {"tp": s.tp, "fp": s.fp, "precision": s.precision} for r, s in by_regime.items()},
        "fn_event_dates": [str(d.date()) for d in sorted(fn_events)],
    }
    with open("backtests/market_correction_scorecard.json", "w", encoding="utf-8") as f_out:
        json.dump(report, f_out, indent=2)
    print("\nWROTE backtests/market_correction_scorecard.json")

if __name__ == "__main__":
    main()
