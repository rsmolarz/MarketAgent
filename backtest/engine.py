from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Iterable, Callable
from datetime import datetime
import traceback


@dataclass
class SignalEvent:
    agent_name: str
    ts: datetime
    symbol: Optional[str]
    market_type: Optional[str]
    severity: str
    confidence: float
    title: str
    description: str
    metadata: Dict[str, Any]


@dataclass
class BacktestRunResult:
    agent_name: str
    start: str
    end: str
    bars_freq: str
    signals: List[SignalEvent]
    errors: List[Dict[str, Any]]


class BacktestEngine:
    """
    Runs agents historically by iterating dates and injecting a data context.

    Design rule:
      - Backtests must not call network APIs from inside agents.
      - All data comes from the context provided here (adapter layer).
    """

    def __init__(self, calendar: Iterable[datetime]):
        self.calendar = list(calendar)

    def run_agent(
        self,
        agent_name: str,
        agent_callable: Callable[[Any], List[Dict[str, Any]]],
        context_factory: Callable[[datetime], Any],
        start: datetime,
        end: datetime,
    ) -> BacktestRunResult:
        signals: List[SignalEvent] = []
        errors: List[Dict[str, Any]] = []

        for dt in self.calendar:
            if dt < start or dt > end:
                continue

            try:
                ctx = context_factory(dt)
                findings = agent_callable(ctx) or []

                for f in findings:
                    signals.append(
                        SignalEvent(
                            agent_name=agent_name,
                            ts=dt,
                            symbol=f.get("symbol"),
                            market_type=f.get("market_type"),
                            severity=str(f.get("severity", "low")),
                            confidence=float(f.get("confidence", 0.0) or 0.0),
                            title=str(f.get("title", "")),
                            description=str(f.get("description", "")),
                            metadata=dict(f.get("metadata", {}) or {}),
                        )
                    )

            except Exception as e:
                errors.append(
                    {
                        "agent": agent_name,
                        "ts": dt.isoformat(),
                        "error": repr(e),
                        "trace": traceback.format_exc(limit=20),
                    }
                )

        return BacktestRunResult(
            agent_name=agent_name,
            start=start.date().isoformat(),
            end=end.date().isoformat(),
            bars_freq="1d",
            signals=signals,
            errors=errors,
        )
