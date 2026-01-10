from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from backtests.context import BacktestContext
from backtests.data_yahoo import slice_asof


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
    days = pd.bdate_range(s, e, freq="B")
    return list(days)


def load_agent_class(module_path: str, class_name: str):
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def agent_supports_ctx(agent) -> bool:
    return callable(getattr(agent, "analyze_ctx", None))


def run_backtest_for_agents(
    agents: List[Tuple[str, str]],
    data: Dict[str, pd.DataFrame],
    symbols: List[str],
    start: str,
    end: str,
    lookback: int = 252,
    output_jsonl: str = "backtests/results.jsonl",
) -> Dict[str, Any]:
    """
    Runs backtest over business days, calling agent.analyze_ctx(ctx) when available.
    Skips agents lacking analyze_ctx to avoid fake backtests.
    """
    rows: List[BacktestResultRow] = []
    days = iter_trading_days(start, end)

    agent_instances = []
    skipped = []
    for module_path, class_name in agents:
        AgentCls = load_agent_class(module_path, class_name)
        inst = AgentCls()
        if not agent_supports_ctx(inst):
            skipped.append(f"{class_name} (no analyze_ctx)")
        agent_instances.append(inst)

    for day in days:
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

        for agent in agent_instances:
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

    summary = {
        "start": start,
        "end": end,
        "days": len(days),
        "rows": len(rows),
        "skipped_agents": skipped,
        "output": output_jsonl,
    }
    return summary
