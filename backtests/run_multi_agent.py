#!/usr/bin/env python
"""Run backtest for multiple agents (standalone version)."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from backtests.context import BacktestContext
from backtests.data_yahoo import fetch_daily, slice_asof

from agents.market_correction_agent import MarketCorrectionAgent
from agents.equity_momentum_agent import EquityMomentumAgent
from agents.bond_stress_agent import BondStressAgent


@dataclass
class BacktestResultRow:
    asof: str
    agent: str
    symbol: Optional[str]
    market_type: Optional[str]
    severity: str
    confidence: float
    title: str
    description: str
    metadata: Dict[str, Any]


def iter_trading_days(start: str, end: str) -> List[pd.Timestamp]:
    s = pd.to_datetime(start)
    e = pd.to_datetime(end)
    return list(pd.bdate_range(s, e, freq="B"))


def agent_supports_ctx(agent) -> bool:
    return callable(getattr(agent, "analyze_ctx", None))


def main():
    start = "2007-01-01"
    end = "2026-01-08"
    lookback = 252
    output_jsonl = "backtests/results_multi.jsonl"

    symbols = ["SPY", "QQQ", "IWM", "DIA", "^VIX", "^TNX", "TLT"]
    print(f"Fetching data for {symbols} from {start} to {end}...")
    data = fetch_daily(symbols, start=start, end=end)
    print(f"Fetched data for {len(data)} symbols")

    agents = [
        MarketCorrectionAgent(),
        EquityMomentumAgent(),
        BondStressAgent(),
    ]
    
    for agent in agents:
        has_ctx = agent_supports_ctx(agent)
        print(f"  {agent.__class__.__name__}: analyze_ctx={'yes' if has_ctx else 'NO'}")

    days = iter_trading_days(start, end)
    rows: List[BacktestResultRow] = []

    print(f"\nRunning backtest for {len(agents)} agents over {len(days)} trading days...")
    
    progress_step = max(1, len(days) // 20)
    for i, day in enumerate(days):
        if i % progress_step == 0:
            print(f"  Progress: {i}/{len(days)} days ({i*100//len(days)}%)")
        
        asof = day.to_pydatetime()
        frames = {}
        for sym in symbols:
            df_full = data.get(sym, pd.DataFrame())
            df_cut = slice_asof(df_full, asof)
            if df_cut is not None and not df_cut.empty and lookback:
                df_cut = df_cut.tail(lookback)
            frames[sym] = df_cut

        ctx = BacktestContext(
            asof=asof,
            frames=frames,
            meta={"symbols": symbols, "lookback": lookback}
        )

        for agent in agents:
            if not agent_supports_ctx(agent):
                continue
            try:
                findings = agent.analyze_ctx(ctx) or []
            except Exception as e:
                rows.append(BacktestResultRow(
                    asof=asof.isoformat(),
                    agent=agent.__class__.__name__,
                    symbol=None,
                    market_type="system",
                    severity="high",
                    confidence=0.1,
                    title="BacktestError",
                    description=str(e),
                    metadata={"error": repr(e)},
                ))
                continue

            for f in findings:
                rows.append(BacktestResultRow(
                    asof=asof.isoformat(),
                    agent=f.get("agent") or agent.__class__.__name__,
                    symbol=f.get("symbol"),
                    market_type=f.get("market_type"),
                    severity=f.get("severity", "medium"),
                    confidence=float(f.get("confidence", 0.5)),
                    title=f.get("title", ""),
                    description=f.get("description", ""),
                    metadata=f.get("metadata") or {},
                ))

    os.makedirs(os.path.dirname(output_jsonl) or ".", exist_ok=True)
    with open(output_jsonl, "w", encoding="utf-8") as fp:
        for r in rows:
            fp.write(json.dumps(asdict(r), ensure_ascii=False, default=str) + "\n")

    print("\n=== Backtest Summary ===")
    print(f"Period: {start} to {end}")
    print(f"Trading days: {len(days)}")
    print(f"Total signals: {len(rows)}")
    print(f"Output: {output_jsonl}")
    
    by_agent = {}
    for r in rows:
        by_agent[r.agent] = by_agent.get(r.agent, 0) + 1
    print("\nBy agent:")
    for agent, count in sorted(by_agent.items()):
        print(f"  {agent}: {count}")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
    main()
