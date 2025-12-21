"""
Greatest Trade Agent

AI agent inspired by 'The Greatest Trade Ever' that detects:
- Macroeconomic bubbles (housing, credit)
- CDS pricing inefficiencies
- Structured product hidden risks

This agent combines multiple analysis modules to identify systemic
market inefficiencies that could signal major market dislocations.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent
from .analyzers import MacroBubbleDetector, CDSAnalyzer, StructuredProductAnalyzer

logger = logging.getLogger(__name__)


class GreatestTradeAgent(BaseAgent):
    """
    Detects systemic market inefficiencies using multi-factor analysis.
    
    Combines macro bubble detection, CDS pricing analysis, and structured
    product risk assessment to identify potential major market dislocations.
    """
    
    MONITORED_RATINGS = ['AAA', 'AA', 'A', 'BBB', 'BB']
    DEFAULT_SPREADS = {
        'AAA': 25,
        'AA': 50,
        'A': 80,
        'BBB': 150,
        'BB': 300
    }
    
    def __init__(self, name: str = None, execution_hook: Optional[callable] = None):
        """
        Initialize the Greatest Trade Agent.
        
        Args:
            name: Optional custom name
            execution_hook: Optional callback for trade signals
        """
        super().__init__(name or "GreatestTradeAgent")
        
        self.macro_detector = MacroBubbleDetector(
            price_to_income_threshold=1.25,
            credit_growth_threshold=0.15
        )
        self.cds_analyzer = CDSAnalyzer(horizon=5, lgd=0.6)
        self.struct_analyzer = StructuredProductAnalyzer(num_assets=100)
        
        self.execution_hook = execution_hook
        
        self.default_pd = 0.05
        self.correlation_assumption = 0.3
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Run full analysis across all modules.
        
        Returns:
            List of findings from macro, CDS, and structured product analysis
        """
        findings = []
        
        macro_findings = self._analyze_macro()
        findings.extend(macro_findings)
        
        cds_findings = self._analyze_cds()
        findings.extend(cds_findings)
        
        struct_findings = self._analyze_structured_products()
        findings.extend(struct_findings)
        
        combined_signal = self._generate_combined_signal(
            macro_findings, cds_findings, struct_findings
        )
        if combined_signal:
            findings.append(combined_signal)
        
        return findings
    
    def _analyze_macro(self) -> List[Dict[str, Any]]:
        """Analyze macro bubble conditions."""
        findings = []
        
        try:
            result = self.macro_detector.analyze()
            
            if result.get('bubble_flag') or result.get('credit_warning'):
                severity = result.get('severity', 'medium')
                
                description_parts = []
                if result.get('bubble_flag'):
                    description_parts.append(
                        f"Price-to-income ratio ({result['current_ratio']:.2f}) is "
                        f"{result['ratio_deviation']:.1f}% above historical average ({result['avg_ratio']:.2f})"
                    )
                if result.get('credit_warning'):
                    description_parts.append("Credit growth exceeds warning threshold")
                
                findings.append(self.create_finding(
                    title="Macro Bubble Warning Detected",
                    description=". ".join(description_parts),
                    severity=severity,
                    confidence=0.75 if result.get('bubble_flag') and result.get('credit_warning') else 0.6,
                    metadata={
                        "current_ratio": result['current_ratio'],
                        "avg_ratio": result['avg_ratio'],
                        "deviation_pct": result['ratio_deviation'],
                        "bubble_flag": result['bubble_flag'],
                        "credit_warning": result.get('credit_warning', False)
                    },
                    symbol="XLRE",
                    market_type="macro"
                ))
                
        except Exception as e:
            self.logger.error(f"Error in macro analysis: {e}")
        
        return findings
    
    def _analyze_cds(self) -> List[Dict[str, Any]]:
        """Analyze CDS pricing inefficiencies."""
        findings = []
        
        try:
            for rating in self.MONITORED_RATINGS:
                spread = self.DEFAULT_SPREADS.get(rating, 100)
                
                result = self.cds_analyzer.analyze_cds(rating, spread)
                
                if result['verdict'] != 'fair':
                    findings.append(self.create_finding(
                        title=f"CDS Mispricing: {rating} rated debt is {result['verdict']}",
                        description=(
                            f"{rating} CDS at {spread}bps appears {result['verdict']}. "
                            f"Expected loss: {result['expected_annual_loss_pct']:.2f}%, "
                            f"Premium: {result['premium_paid_pct']:.2f}%. "
                            f"Breakeven spread: {result['breakeven_spread_bps']:.0f}bps. "
                            f"Opportunity: {result['opportunity']}"
                        ),
                        severity=result['severity'],
                        confidence=0.7,
                        metadata={
                            "rating": rating,
                            "spread_bps": spread,
                            "verdict": result['verdict'],
                            "mispricing_pct": result['mispricing_pct'],
                            "breakeven_spread": result['breakeven_spread_bps'],
                            "opportunity": result['opportunity']
                        },
                        symbol=f"CDS-{rating}",
                        market_type="credit"
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error in CDS analysis: {e}")
        
        return findings
    
    def _analyze_structured_products(self) -> List[Dict[str, Any]]:
        """Analyze structured product hidden risks."""
        findings = []
        
        try:
            summary = self.struct_analyzer.get_summary(
                pd=self.default_pd,
                correlation=self.correlation_assumption
            )
            
            if summary.get('warning'):
                hidden_risk_tranches = summary['hidden_risk_names']
                
                findings.append(self.create_finding(
                    title="Structured Product Hidden Risk Detected",
                    description=(
                        f"Tranches with hidden correlation risk: {', '.join(hidden_risk_tranches)}. "
                        f"Under stress scenarios (correlation={summary['correlation_assumption']}), "
                        f"these tranches show significantly higher loss probability than "
                        f"independent default models suggest."
                    ),
                    severity="high",
                    confidence=0.65,
                    metadata={
                        "affected_tranches": hidden_risk_tranches,
                        "num_tranches_at_risk": summary['tranches_with_hidden_risk'],
                        "correlation_assumption": summary['correlation_assumption'],
                        "underlying_pd": summary['underlying_pd'],
                        "tranche_details": summary['details']
                    },
                    symbol="CDO-INDEX",
                    market_type="structured_credit"
                ))
            
            for tranche in summary.get('details', []):
                if tranche.get('risk_rating') == 'extreme' and tranche.get('attach_pct') == 0:
                    findings.append(self.create_finding(
                        title=f"Equity Tranche Extreme Risk: {tranche['name']}",
                        description=(
                            f"First-loss {tranche['name']} tranche shows {tranche['loss_prob_correlated']:.1f}% "
                            f"loss probability under correlated defaults. "
                            f"Risk multiplier: {tranche['risk_multiplier']:.1f}x vs independent model."
                        ),
                        severity="critical",
                        confidence=0.8,
                        metadata=tranche,
                        symbol="CDO-EQUITY",
                        market_type="structured_credit"
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error in structured product analysis: {e}")
        
        return findings
    
    def _generate_combined_signal(self,
                                  macro: List,
                                  cds: List,
                                  struct: List) -> Optional[Dict[str, Any]]:
        """
        Generate combined trading signal if conditions align.
        
        The "Greatest Trade" signal triggers when:
        - Macro bubble is detected
        - CDS protection is underpriced
        - Structured products show hidden risk
        """
        has_macro_bubble = any(
            f.get('metadata', {}).get('bubble_flag') for f in macro
        )
        
        underpriced_cds = [
            f for f in cds 
            if f.get('metadata', {}).get('verdict') == 'underpriced'
        ]
        
        has_hidden_risk = any(
            f.get('metadata', {}).get('affected_tranches') for f in struct
        )
        
        conditions_met = sum([has_macro_bubble, len(underpriced_cds) > 0, has_hidden_risk])
        
        if conditions_met >= 2:
            action = {
                "trade": "BUY_CDS_PROTECTION",
                "rationale": "Multiple systemic risk signals detected",
                "targets": [f.get('metadata', {}).get('rating') for f in underpriced_cds]
            }
            
            if self.execution_hook:
                try:
                    self.execution_hook(action)
                except Exception as e:
                    self.logger.error(f"Execution hook error: {e}")
            
            return self.create_finding(
                title="GREATEST TRADE SIGNAL: Systemic Risk Alignment",
                description=(
                    f"Multiple conditions aligned for potential systemic trade. "
                    f"Macro bubble: {'YES' if has_macro_bubble else 'NO'}, "
                    f"Underpriced CDS: {len(underpriced_cds)}, "
                    f"Hidden structured risk: {'YES' if has_hidden_risk else 'NO'}. "
                    f"Recommended action: {action['trade']}"
                ),
                severity="critical",
                confidence=0.85,
                metadata={
                    "macro_bubble": has_macro_bubble,
                    "underpriced_cds_count": len(underpriced_cds),
                    "hidden_risk": has_hidden_risk,
                    "conditions_met": conditions_met,
                    "recommended_action": action
                },
                symbol="SYSTEMIC",
                market_type="macro"
            )
        
        return None
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """
        Run full analysis and return structured results.
        
        Convenience method that returns results in the original format
        from the attached files for compatibility.
        
        Returns:
            Dictionary with macro, cds, and struct results
        """
        macro_res = self.macro_detector.analyze()
        cds_res = self.cds_analyzer.analyze_cds("AAA", 50)
        struct_res = self.struct_analyzer.analyze_tranches(0.05)
        
        signal = {
            "macro": macro_res,
            "cds": cds_res,
            "struct": struct_res,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if macro_res.get("bubble_flag") and cds_res.get("verdict") == "underpriced":
            action = {"trade": "BUY_CDS"}
            signal["recommended_action"] = action
            if self.execution_hook:
                self.execution_hook(action)
        
        return signal
