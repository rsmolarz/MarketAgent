from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd


@dataclass
class BacktestContext:
    """
    BacktestContext carries historical data and the current "as-of" timestamp.

    frames: dict[symbol -> DataFrame] where DF index is datetime-like and includes
            at least: ['Open','High','Low','Close','Volume'] (yfinance format).
            DataFrames are expected to be filtered to <= asof for no look-ahead.
    """
    asof: datetime
    frames: Dict[str, pd.DataFrame] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def frame(self, symbol: str) -> Optional[pd.DataFrame]:
        return self.frames.get(symbol)

    def window(self, symbol: str, lookback: int) -> Optional[pd.DataFrame]:
        df = self.frame(symbol)
        if df is None or df.empty:
            return None
        return df.tail(lookback)
