from __future__ import annotations
from datetime import datetime
from typing import List
import pandas as pd


def trading_days(start: str, end: str) -> List[datetime]:
    """
    Simple NYSE-ish weekday calendar. Good enough for signal backtests.
    If you later want true exchange calendars, swap implementation.
    """
    idx = pd.date_range(start=start, end=end, freq="B")
    return [d.to_pydatetime() for d in idx]
