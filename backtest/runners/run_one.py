from __future__ import annotations
from datetime import datetime
import pandas as pd

from backtest.data.calendar import trading_days
from backtest.data.loaders_yf import load_yf_history, slice_asof
from backtest.engine import BacktestEngine
from backtest.adapters.agent_adapter import BacktestContext, AnalysisAgentAdapter
from backtest.metrics import compute_forward_returns
from backtest.results_io import write_result
from backtest.registry import load_manifest, import_agent_class


DEFAULT_START = "2007-01-01"
DEFAULT_END = "2025-12-31"

BASE_SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "^VIX", "^TNX", "TLT"]


def run_one(agent_name: str, start: str = DEFAULT_START, end: str = DEFAULT_END):
    manifest = load_manifest()
    entry = next((a for a in manifest["agents"] if a["name"] == agent_name), None)
    if not entry:
        raise SystemExit(f"Agent not found in manifest: {agent_name}")

    cls = import_agent_class(entry["module"], entry["callable"])
    agent = cls()
    adapter = AnalysisAgentAdapter(agent)

    frames = {}
    for sym in BASE_SYMBOLS:
        frames[sym] = load_yf_history(sym, start=start, end=end)

    cal = trading_days(start, end)
    engine = BacktestEngine(cal)

    def context_factory(dt):
        asof = pd.Timestamp(dt).normalize()
        sliced = {sym: slice_asof(df, asof, lookback_days=252) for sym, df in frames.items()}
        return BacktestContext(asof=dt, frames=sliced, meta={"symbols": BASE_SYMBOLS})

    result = engine.run_agent(
        agent_name=agent_name,
        agent_callable=adapter,
        context_factory=context_factory,
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
    )

    metrics = compute_forward_returns(result.signals, frames)

    payload = {
        "agent": agent_name,
        "period": {"start": start, "end": end},
        "signals": metrics,
        "errors": {"count": len(result.errors), "sample": result.errors[:5]},
    }
    out = write_result(agent_name, payload)
    print(f"Wrote: {out}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m backtest.runners.run_one <AgentName>")
    run_one(sys.argv[1])
