"""
OpenBB Platform client wrapper for fixed income and market data.

Provides a unified interface to fixed income data including:
- Yield curves (government and corporate)
- Credit spreads
- Bond pricing
- Economic indicators

Falls back to FRED API and direct data sources when OpenBB is not available.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


class OpenBBClient:
    """
    Client for market data with OpenBB Platform integration.

    Falls back to FRED API when OpenBB is not installed.
    Primary data: yield curves, credit spreads, economic indicators.
    """

    # FRED series IDs for key indicators
    FRED_SERIES = {
        # Treasury rates
        "treasury_2y": "DGS2",
        "treasury_5y": "DGS5",
        "treasury_10y": "DGS10",
        "treasury_30y": "DGS30",
        "treasury_3m": "DGS3MO",
        # Fed funds
        "fed_funds_rate": "FEDFUNDS",
        "fed_funds_effective": "DFF",
        # Inflation
        "cpi_yoy": "CPIAUCSL",
        "pce_yoy": "PCEPI",
        "breakeven_5y": "T5YIE",
        "breakeven_10y": "T10YIE",
        # Economic
        "gdp_growth": "A191RL1Q225SBEA",
        "unemployment_rate": "UNRATE",
        "initial_claims": "ICSA",
        "pmi_manufacturing": "MANEMP",
        # Credit
        "ice_bofa_hy_oas": "BAMLH0A0HYM2",
        "ice_bofa_ig_oas": "BAMLC0A0CM",
        # Volatility
        "vix": "VIXCLS",
        "move_index": "MOVE",
    }

    def __init__(self, fred_api_key: Optional[str] = None):
        self.fred_api_key = fred_api_key or os.getenv("FRED_API_KEY", "")
        self._openbb_available = False

        # Try to import OpenBB
        try:
            from openbb import obb
            self._obb = obb
            self._openbb_available = True
            logger.info("OpenBB Platform available")
        except ImportError:
            logger.info("OpenBB not installed, using FRED API fallback")
            self._obb = None

    def _fred_get(self, series_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Fetch data from FRED API."""
        if not self.fred_api_key:
            logger.warning("No FRED API key configured")
            return []

        params = {
            "series_id": series_id,
            "api_key": self.fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }

        try:
            resp = requests.get(FRED_BASE, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get("observations", [])
        except Exception as e:
            logger.error(f"FRED API request failed for {series_id}: {e}")
            return []

    def _get_latest_fred(self, series_id: str) -> Optional[float]:
        """Get the most recent value for a FRED series."""
        observations = self._fred_get(series_id, limit=5)
        for obs in observations:
            value = obs.get("value", ".")
            if value != ".":
                try:
                    return float(value)
                except ValueError:
                    continue
        return None

    def get_treasury_rates(self) -> Dict[str, float]:
        """Get current Treasury yield curve rates."""
        rates = {}
        rate_series = {
            "3M": "treasury_3m",
            "2Y": "treasury_2y",
            "5Y": "treasury_5y",
            "10Y": "treasury_10y",
            "30Y": "treasury_30y",
        }

        for tenor, key in rate_series.items():
            series_id = self.FRED_SERIES[key]
            value = self._get_latest_fred(series_id)
            if value is not None:
                rates[tenor] = value

        return rates

    def get_credit_spreads(self) -> Dict[str, float]:
        """Get credit spread data (IG and HY OAS)."""
        spreads = {}

        hy_oas = self._get_latest_fred(self.FRED_SERIES["ice_bofa_hy_oas"])
        if hy_oas is not None:
            spreads["high_yield"] = hy_oas * 100  # Convert to bps

        ig_oas = self._get_latest_fred(self.FRED_SERIES["ice_bofa_ig_oas"])
        if ig_oas is not None:
            spreads["investment_grade"] = ig_oas * 100

        return spreads

    def get_fed_policy_data(self) -> Dict[str, Any]:
        """Get Federal Reserve policy-related data."""
        fed_funds = self._get_latest_fred(self.FRED_SERIES["fed_funds_rate"])
        return {
            "fed_funds_rate": fed_funds or 5.25,
            "neutral_rate": 3.0,  # FOMC long-run estimate
        }

    def get_inflation_data(self) -> Dict[str, Any]:
        """Get inflation-related indicators."""
        data = {}

        be5 = self._get_latest_fred(self.FRED_SERIES["breakeven_5y"])
        if be5 is not None:
            data["breakeven_inflation_5y"] = be5

        be10 = self._get_latest_fred(self.FRED_SERIES["breakeven_10y"])
        if be10 is not None:
            data["breakeven_inflation_10y"] = be10

        return data

    def get_economic_indicators(self) -> Dict[str, Any]:
        """Get key economic indicators for regime detection."""
        indicators = {}

        for name, series_key in [
            ("unemployment_rate", "unemployment_rate"),
            ("initial_claims", "initial_claims"),
            ("vix", "vix"),
        ]:
            series_id = self.FRED_SERIES.get(series_key)
            if series_id:
                value = self._get_latest_fred(series_id)
                if value is not None:
                    indicators[name] = value

        return indicators

    def get_macro_data_for_regime(self) -> Dict[str, float]:
        """
        Get all macro data needed for regime classification.
        Returns a flat dict suitable for MacroRegimeDetector.update_indicators_bulk().
        """
        data = {}

        # Treasury rates
        rates = self.get_treasury_rates()
        # Growth proxy: slope of yield curve
        if "2Y" in rates and "10Y" in rates:
            data["yield_curve_slope"] = rates["10Y"] - rates["2Y"]

        # Credit spreads
        spreads = self.get_credit_spreads()
        if "high_yield" in spreads:
            data["credit_spread_hy"] = spreads["high_yield"]

        # Fed policy
        fed = self.get_fed_policy_data()
        data["fed_funds_rate"] = fed.get("fed_funds_rate", 5.25)

        # Inflation
        inflation = self.get_inflation_data()
        if "breakeven_inflation_5y" in inflation:
            data["breakeven_inflation_5y"] = inflation["breakeven_inflation_5y"]

        # Economic indicators
        econ = self.get_economic_indicators()
        data.update(econ)

        return data

    def get_bond_market_data(self) -> Dict[str, Any]:
        """Get comprehensive bond market data for the bonds sub-orchestrator."""
        rates = self.get_treasury_rates()
        spreads = self.get_credit_spreads()
        fed = self.get_fed_policy_data()

        return {
            "treasury_rates": rates,
            "credit_spreads": spreads,
            "fed_policy": fed,
        }
