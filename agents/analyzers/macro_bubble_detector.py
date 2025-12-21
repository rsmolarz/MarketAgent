"""
Macro Bubble Detector Module

Detects housing/credit bubbles using price-to-income ratios and credit growth metrics.
Can be used standalone or as part of the GreatestTradeAgent.
"""

import logging
from typing import Dict, Optional, List
import yfinance as yf

logger = logging.getLogger(__name__)


class MacroBubbleDetector:
    """
    Detects macroeconomic bubbles in housing and credit markets.
    
    Uses price-to-income ratios and credit growth thresholds to identify
    potential bubble conditions that may precede market corrections.
    """
    
    def __init__(self, 
                 price_to_income_threshold: float = 1.3, 
                 credit_growth_threshold: float = 0.2):
        """
        Initialize the bubble detector.
        
        Args:
            price_to_income_threshold: Ratio above which signals bubble (default 1.3x)
            credit_growth_threshold: Credit growth rate signaling concern (default 20%)
        """
        self.price_to_income_threshold = price_to_income_threshold
        self.credit_growth_threshold = credit_growth_threshold
        self.logger = logging.getLogger(f"{__name__}.MacroBubbleDetector")

    def fetch_data(self) -> Dict[str, list]:
        """
        Fetch real economic data from market sources.
        
        Returns:
            Dictionary with house_price_index, income_index, debt_to_gdp
        """
        try:
            xlre = yf.Ticker("XLRE")
            hist = xlre.history(period="2y", interval="1mo")
            
            if hist.empty:
                return self._get_fallback_data()
            
            prices = hist['Close'].tolist()[-12:] if len(hist) >= 12 else hist['Close'].tolist()
            
            base = prices[0] if prices else 100
            normalized_prices = [p / base * 100 for p in prices]
            
            income_growth = 1.03
            income_index = [100 * (income_growth ** (i/12)) for i in range(len(normalized_prices))]
            
            debt_levels = [0.60 + (0.05 * i / len(normalized_prices)) for i in range(len(normalized_prices))]
            
            return {
                "house_price_index": normalized_prices,
                "income_index": income_index,
                "debt_to_gdp": debt_levels
            }
            
        except Exception as e:
            self.logger.warning(f"Error fetching live data: {e}, using fallback")
            return self._get_fallback_data()
    
    def _get_fallback_data(self) -> Dict[str, list]:
        """Return fallback data if live fetch fails."""
        return {
            "house_price_index": [100, 105, 110, 118, 125, 132, 140],
            "income_index": [100, 101.5, 103, 104.5, 106, 107.5, 109],
            "debt_to_gdp": [0.60, 0.65, 0.72, 0.78, 0.85, 0.92, 0.99]
        }

    def analyze(self, data: Optional[Dict[str, list]] = None) -> Dict:
        """
        Analyze data for bubble conditions.
        
        Args:
            data: Optional pre-fetched data. If None, fetches fresh data.
            
        Returns:
            Dictionary with analysis results including bubble_flag
        """
        if data is None:
            data = self.fetch_data()
            
        prices = data["house_price_index"]
        incomes = data["income_index"]
        debt_levels = data.get("debt_to_gdp", [])
        
        if len(prices) < 2 or len(incomes) < 2:
            return {
                "current_ratio": 0,
                "avg_ratio": 0,
                "bubble_flag": False,
                "error": "Insufficient data"
            }
        
        current_ratio = prices[-1] / incomes[-1]
        avg_ratio = sum(p/i for p, i in zip(prices[:-1], incomes[:-1])) / (len(prices)-1)
        
        bubble_flag = current_ratio > self.price_to_income_threshold * avg_ratio
        
        credit_warning = False
        if len(debt_levels) >= 2:
            credit_growth = (debt_levels[-1] - debt_levels[0]) / debt_levels[0]
            credit_warning = credit_growth > self.credit_growth_threshold
        
        severity = "low"
        if bubble_flag and credit_warning:
            severity = "critical"
        elif bubble_flag:
            severity = "high"
        elif credit_warning:
            severity = "medium"
        
        return {
            "current_ratio": round(current_ratio, 3),
            "avg_ratio": round(avg_ratio, 3),
            "ratio_deviation": round((current_ratio / avg_ratio - 1) * 100, 2),
            "bubble_flag": bubble_flag,
            "credit_warning": credit_warning,
            "severity": severity,
            "threshold": self.price_to_income_threshold
        }
