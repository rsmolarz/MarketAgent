from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd

@dataclass
class BacktestContext:
    asof: datetime
    frames: Dict[str, pd.DataFrame]
    meta: Dict[str, Any]


class AnalysisAgentAdapter:
    """
    Adapter to run agents safely in backtests.

    Contract:
      - agent must implement analyze(context) -> List[findings]
      - agent must NOT call network in analyze() for backtests
    """
    def __init__(self, agent):
        self.agent = agent

    def __call__(self, ctx: BacktestContext) -> List[Dict[str, Any]]:
        if hasattr(self.agent, "analyze"):
            return self.agent.analyze(ctx)
        if hasattr(self.agent, "act") and hasattr(self.agent, "plan"):
            plan = self.agent.plan()
            return self.agent.act(plan)
        return []
