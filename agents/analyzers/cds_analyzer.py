"""
CDS (Credit Default Swap) Analyzer Module

Evaluates CDS pricing relative to expected loss to identify under/overpriced contracts.
Inspired by 'The Greatest Trade Ever' analysis methodology.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CDSAnalyzer:
    """
    Analyzes Credit Default Swap pricing for inefficiencies.
    
    Compares CDS premiums against expected loss calculations to identify
    mispriced protection that could represent trading opportunities.
    """
    
    RATING_TO_PD = {
        "AAA": 0.005,
        "AA+": 0.01,
        "AA": 0.015,
        "AA-": 0.02,
        "A+": 0.025,
        "A": 0.03,
        "A-": 0.035,
        "BBB+": 0.04,
        "BBB": 0.05,
        "BBB-": 0.07,
        "BB+": 0.10,
        "BB": 0.15,
        "BB-": 0.20,
        "B+": 0.25,
        "B": 0.30,
        "B-": 0.35,
        "CCC": 0.50,
        "CC": 0.65,
        "C": 0.80,
        "D": 1.0
    }
    
    def __init__(self, horizon: int = 5, lgd: float = 0.6):
        """
        Initialize the CDS analyzer.
        
        Args:
            horizon: Time horizon in years for analysis (default 5)
            lgd: Loss Given Default rate (default 0.6 or 60%)
        """
        self.horizon = horizon
        self.lgd = lgd
        self.logger = logging.getLogger(f"{__name__}.CDSAnalyzer")

    def get_default_probability(self, rating: str) -> float:
        """
        Get probability of default for a given credit rating.
        
        Args:
            rating: Credit rating string (e.g., 'AAA', 'BBB')
            
        Returns:
            Annual probability of default
        """
        return self.RATING_TO_PD.get(rating.upper(), 0.05)

    def analyze_cds(self, 
                    rating: str, 
                    annual_spread_bps: float,
                    recovery_rate: Optional[float] = None) -> Dict:
        """
        Analyze a CDS contract for pricing inefficiency.
        
        Args:
            rating: Credit rating of the reference entity
            annual_spread_bps: CDS spread in basis points
            recovery_rate: Optional custom recovery rate (1 - LGD)
            
        Returns:
            Dictionary with analysis results and verdict
        """
        pd = self.get_default_probability(rating)
        lgd = self.lgd if recovery_rate is None else (1 - recovery_rate)
        
        expected_loss = pd * lgd
        
        total_premium = (annual_spread_bps * 1e-4) * self.horizon
        
        total_expected_loss = expected_loss * self.horizon
        
        diff = total_premium - total_expected_loss
        diff_ratio = diff / total_expected_loss if total_expected_loss > 0 else 0
        
        if diff < -0.01:
            verdict = "underpriced"
            severity = "high" if diff < -0.05 else "medium"
            opportunity = "BUY_PROTECTION"
        elif diff > 0.01:
            verdict = "overpriced"
            severity = "medium" if diff > 0.05 else "low"
            opportunity = "SELL_PROTECTION"
        else:
            verdict = "fair"
            severity = "low"
            opportunity = None
        
        breakeven_spread = (expected_loss / 1e-4)
        
        return {
            "rating": rating.upper(),
            "spread_bps": annual_spread_bps,
            "probability_of_default": round(pd * 100, 2),
            "loss_given_default": round(lgd * 100, 2),
            "expected_annual_loss_pct": round(expected_loss * 100, 3),
            "premium_paid_pct": round((annual_spread_bps * 1e-4) * 100, 3),
            "mispricing_pct": round(diff_ratio * 100, 2),
            "breakeven_spread_bps": round(breakeven_spread, 1),
            "verdict": verdict,
            "severity": severity,
            "opportunity": opportunity,
            "horizon_years": self.horizon
        }
    
    def analyze_multiple(self, contracts: list) -> list:
        """
        Analyze multiple CDS contracts.
        
        Args:
            contracts: List of dicts with 'rating' and 'spread_bps'
            
        Returns:
            List of analysis results
        """
        results = []
        for contract in contracts:
            rating = contract.get('rating', 'BBB')
            spread = contract.get('spread_bps', 100)
            recovery = contract.get('recovery_rate')
            results.append(self.analyze_cds(rating, spread, recovery))
        return results
