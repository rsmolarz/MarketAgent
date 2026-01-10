"""
Geopolitical Risk Context Adapter for backtesting.

Provides a time-aligned interface for GeopoliticalRiskAgent to query
historical risk scores without forward-looking bias.
"""
import pandas as pd
from datetime import date, datetime
from typing import Optional, Union, Dict, List
import logging

logger = logging.getLogger(__name__)


class GeoRiskContext:
    """
    Context adapter for geopolitical risk backtesting.
    
    Provides point-in-time risk queries that respect backtest date boundaries.
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Initialize with risk index DataFrame.
        
        Args:
            df: DataFrame with columns [date, region, risk_score, ...]
        """
        self.df = df.copy()
        if not self.df.empty:
            self.df["date"] = pd.to_datetime(self.df["date"])
            self.df = self.df.sort_values("date")
        
        self._cache: Dict[str, pd.DataFrame] = {}
    
    def risk_on(self, as_of: Union[date, datetime, pd.Timestamp], region: str) -> int:
        """
        Get the most recent risk score for a region as of a given date.
        
        Args:
            as_of: The backtest date (no future data used)
            region: Region name (e.g., "TAIWAN", "UKRAINE", "MIDDLE_EAST")
        
        Returns:
            Risk score 0-100, or 0 if no data
        """
        if self.df.empty:
            return 0
        
        as_of_ts = pd.Timestamp(as_of)
        region_upper = region.upper().replace("-", "_").replace(" ", "_")
        
        cache_key = f"{region_upper}"
        if cache_key not in self._cache:
            self._cache[cache_key] = self.df[
                self.df["region"].str.upper().str.replace("-", "_").str.replace(" ", "_") == region_upper
            ]
        
        region_df = self._cache[cache_key]
        if region_df.empty:
            return 0
        
        valid = region_df[region_df["date"] <= as_of_ts]
        if valid.empty:
            return 0
        
        return int(valid.iloc[-1]["risk_score"])
    
    def risk_window(
        self,
        as_of: Union[date, datetime, pd.Timestamp],
        region: str,
        lookback_days: int = 30
    ) -> Dict[str, float]:
        """
        Get risk statistics over a lookback window.
        
        Returns:
            Dict with max, mean, current risk scores
        """
        as_of_ts = pd.Timestamp(as_of)
        start_ts = as_of_ts - pd.Timedelta(days=lookback_days)
        region_upper = region.upper().replace("-", "_")
        
        region_df = self.df[
            (self.df["region"].str.upper().str.replace("-", "_") == region_upper) &
            (self.df["date"] >= start_ts) &
            (self.df["date"] <= as_of_ts)
        ]
        
        if region_df.empty:
            return {"max": 0, "mean": 0, "current": 0, "event_count": 0}
        
        return {
            "max": int(region_df["risk_score"].max()),
            "mean": round(region_df["risk_score"].mean(), 1),
            "current": int(region_df.iloc[-1]["risk_score"]),
            "event_count": int(region_df["event_count"].sum()),
        }
    
    def active_regions(
        self,
        as_of: Union[date, datetime, pd.Timestamp],
        threshold: int = 50
    ) -> List[str]:
        """
        Get list of regions with risk above threshold.
        """
        as_of_ts = pd.Timestamp(as_of)
        results = []
        
        for region in self.df["region"].unique():
            score = self.risk_on(as_of_ts, region)
            if score >= threshold:
                results.append(region)
        
        return results
    
    def has_data(self, as_of: Union[date, datetime, pd.Timestamp]) -> bool:
        """Check if we have any geo risk data up to the given date."""
        if self.df.empty:
            return False
        return (self.df["date"] <= pd.Timestamp(as_of)).any()


def load_geo_context() -> GeoRiskContext:
    """
    Load geo risk context from best available source.
    """
    try:
        from data_sources.geopolitical_loader import get_or_build_risk_index
        df = get_or_build_risk_index()
        return GeoRiskContext(df)
    except Exception as e:
        logger.warning(f"Could not load geo risk index: {e}")
        return GeoRiskContext(pd.DataFrame())


def create_context_from_events(events: List[Dict]) -> GeoRiskContext:
    """
    Create context from a list of event dicts.
    
    Args:
        events: List of dicts with keys [date, region, risk_score, ...]
    """
    rows = []
    for e in events:
        rows.append({
            "date": pd.Timestamp(e["date"]),
            "region": e.get("region", "UNKNOWN").upper(),
            "risk_score": e.get("risk_score", 50),
            "event_count": e.get("event_count", 1),
            "conflict_events": e.get("conflict_events", 0),
            "severity_score": e.get("severity_score", 0),
        })
    
    return GeoRiskContext(pd.DataFrame(rows))
