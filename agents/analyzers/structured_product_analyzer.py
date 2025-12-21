"""
Structured Product Analyzer Module

Assesses tranche risk in structured products (CDOs, CLOs) under different
default correlation scenarios. Key to understanding systemic risk.
"""

import math
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class StructuredProductAnalyzer:
    """
    Analyzes structured product tranches for risk under various scenarios.
    
    Evaluates how different tranches (equity, mezzanine, senior) perform
    under independent vs correlated default scenarios - a key insight from
    the 2008 financial crisis analysis.
    """
    
    DEFAULT_TRANCHES = [
        {"name": "Equity", "attach_pct": 0, "detach_pct": 5},
        {"name": "Mezzanine", "attach_pct": 5, "detach_pct": 15},
        {"name": "Senior", "attach_pct": 15, "detach_pct": 30},
        {"name": "Super Senior", "attach_pct": 30, "detach_pct": 100}
    ]
    
    def __init__(self, num_assets: int = 100):
        """
        Initialize the analyzer.
        
        Args:
            num_assets: Number of underlying assets in the pool (default 100)
        """
        self.num_assets = num_assets
        self.logger = logging.getLogger(f"{__name__}.StructuredProductAnalyzer")

    def _prob_loss_exceeds(self, k: int, pd: float) -> float:
        """
        Calculate probability that losses exceed k assets (binomial).
        
        Args:
            k: Number of defaults threshold
            pd: Probability of default per asset
            
        Returns:
            Probability of k or more defaults
        """
        N = self.num_assets
        if k > N:
            return 0.0
        if k <= 0:
            return 1.0
            
        prob = 0.0
        for i in range(k, min(N + 1, k + 50)):
            try:
                comb = math.comb(N, i)
                prob += comb * (pd ** i) * ((1 - pd) ** (N - i))
            except (OverflowError, ValueError):
                break
        return prob

    def _prob_loss_correlated(self, attach_pct: float, pd: float, correlation: float = 0.3) -> float:
        """
        Estimate loss probability under correlated defaults (simplified Gaussian copula).
        
        Args:
            attach_pct: Attachment point percentage
            pd: Individual asset default probability
            correlation: Asset correlation (default 0.3)
            
        Returns:
            Estimated probability of tranche being hit under correlation
        """
        if attach_pct <= 0:
            return 1.0
        
        if attach_pct >= 100:
            return 0.0
        
        effective_pd = min(1.0, pd * (1 + correlation * 5))
        
        if attach_pct < 10:
            return effective_pd * 2
        elif attach_pct < 30:
            return effective_pd
        else:
            return effective_pd * 0.5

    def analyze_tranches(self, 
                        pd: float, 
                        tranches: Optional[List[Dict]] = None,
                        correlation: float = 0.3) -> List[Dict]:
        """
        Analyze tranches under both independent and correlated scenarios.
        
        Args:
            pd: Probability of default for underlying assets
            tranches: List of tranche definitions, or use defaults
            correlation: Asset correlation for stress scenario
            
        Returns:
            List of tranche analysis results
        """
        if tranches is None:
            tranches = self.DEFAULT_TRANCHES
            
        results = []
        
        for t in tranches:
            name = t.get('name', 'Unknown')
            attach_pct = t.get('attach_pct', 0)
            detach_pct = t.get('detach_pct', 100)
            
            attach_count = math.ceil((attach_pct / 100) * self.num_assets)
            
            prob_loss_independent = self._prob_loss_exceeds(attach_count, pd)
            
            prob_loss_correlated = self._prob_loss_correlated(attach_pct, pd, correlation)
            
            risk_multiplier = (prob_loss_correlated / prob_loss_independent 
                              if prob_loss_independent > 0.0001 else 1.0)
            
            if attach_pct == 0:
                risk_rating = "extreme"
            elif risk_multiplier > 5:
                risk_rating = "high"
            elif risk_multiplier > 2:
                risk_rating = "elevated"
            else:
                risk_rating = "moderate"
            
            results.append({
                "name": name,
                "attach_pct": attach_pct,
                "detach_pct": detach_pct,
                "loss_prob_independent": round(prob_loss_independent * 100, 4),
                "loss_prob_correlated": round(prob_loss_correlated * 100, 4),
                "risk_multiplier": round(risk_multiplier, 2),
                "risk_rating": risk_rating,
                "hidden_risk": risk_multiplier > 3 and attach_pct > 10
            })
            
        return results
    
    def get_summary(self, pd: float, correlation: float = 0.3) -> Dict:
        """
        Get a summary of structured product risk.
        
        Args:
            pd: Probability of default
            correlation: Asset correlation
            
        Returns:
            Summary dictionary with key findings
        """
        tranches = self.analyze_tranches(pd, correlation=correlation)
        
        hidden_risks = [t for t in tranches if t.get('hidden_risk', False)]
        
        return {
            "num_tranches": len(tranches),
            "tranches_with_hidden_risk": len(hidden_risks),
            "hidden_risk_names": [t['name'] for t in hidden_risks],
            "correlation_assumption": correlation,
            "underlying_pd": pd,
            "warning": len(hidden_risks) > 0,
            "details": tranches
        }
