from __future__ import annotations
import json
from typing import Dict, Any
import pandas as pd

from analytics.regime import classify_regime
from backtests.data_yahoo import fetch_daily, slice_asof

def main():
    findings_path = "backtests/market_correction_findings_2007.jsonl"
    out_path = "backtests/market_correction_findings_2007_regime.jsonl"

    start, end = "2007-01-01", "2026-01-10"
    symbols = ["SPY", "^VIX"]
    data = fetch_daily(symbols, start=start, end=end)

    with open(findings_path, "r", encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            row: Dict[str, Any] = json.loads(line)
            asof = pd.to_datetime(row["asof"]).to_pydatetime()

            spy = slice_asof(data["SPY"], asof).tail(252)
            vix = slice_asof(data["^VIX"], asof).tail(252)

            rr = classify_regime(spy, vix)
            row["regime"] = rr.regime
            row["risk_state"] = rr.risk
            row["vol_label"] = rr.vol_label
            row["regime_score"] = rr.score
            row["regime_details"] = rr.details

            fout.write(json.dumps(row, ensure_ascii=False) + "\n")

    print({"ok": True, "output": out_path})

if __name__ == "__main__":
    main()
