from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd


@dataclass
class FixturesContext:
    """Context for testing with pre-defined fixture data."""
    asof: datetime
    frames: Dict[str, pd.DataFrame]
    meta: Dict[str, Any]


def create_test_context(
    asof: datetime,
    symbols: List[str] = None,
    days: int = 100
) -> FixturesContext:
    """
    Create a synthetic test context with random price data.
    Useful for unit testing agents without real data.
    """
    import numpy as np
    
    symbols = symbols or ["SPY", "QQQ"]
    frames = {}
    
    for sym in symbols:
        dates = pd.date_range(end=asof, periods=days, freq="B")
        np.random.seed(hash(sym) % 2**31)
        
        base_price = 100.0 + np.random.rand() * 200
        returns = np.random.randn(days) * 0.02
        prices = base_price * np.cumprod(1 + returns)
        
        frames[sym] = pd.DataFrame({
            "open": prices * (1 + np.random.randn(days) * 0.005),
            "high": prices * (1 + np.abs(np.random.randn(days) * 0.01)),
            "low": prices * (1 - np.abs(np.random.randn(days) * 0.01)),
            "close": prices,
            "volume": np.random.randint(1000000, 10000000, days),
        }, index=dates)
    
    return FixturesContext(
        asof=asof,
        frames=frames,
        meta={"symbols": symbols, "synthetic": True}
    )
