"""
Crypto Risk Gate Analyzer

Crypto-specific risk gating based on funding rates, OI extremes,
exchange health, and market-wide stress indicators.
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CryptoRiskGate:
    """
    Crypto-specific risk gating system.
    
    Evaluates:
    - Extreme funding rates (crowded trades)
    - Open interest anomalies
    - Exchange health indicators
    - Market-wide volatility
    - Recent liquidation events
    """
    
    def __init__(self):
        self.extreme_funding_threshold = 0.015
        self.high_funding_threshold = 0.008
        self.extreme_oi_change = 25.0
        self.high_volatility_threshold = 5.0
    
    def evaluate(self, 
                 funding_rate: Optional[float] = None,
                 oi_change_pct: Optional[float] = None,
                 price_volatility_pct: Optional[float] = None,
                 vwap_z: Optional[float] = None,
                 adx: Optional[float] = None) -> Dict[str, Any]:
        """
        Evaluate crypto-specific risk conditions.
        
        Args:
            funding_rate: Current funding rate
            oi_change_pct: Percent change in open interest
            price_volatility_pct: Recent price volatility percentage
            vwap_z: Z-score relative to VWAP
            adx: Average Directional Index
            
        Returns:
            Dictionary with risk assessment and gate multiplier
        """
        try:
            reasons = []
            risk_score = 0.0
            
            funding_risk, funding_reasons = self._evaluate_funding_risk(funding_rate)
            risk_score += funding_risk
            reasons.extend(funding_reasons)
            
            oi_risk, oi_reasons = self._evaluate_oi_risk(oi_change_pct)
            risk_score += oi_risk
            reasons.extend(oi_reasons)
            
            vol_risk, vol_reasons = self._evaluate_volatility_risk(price_volatility_pct, vwap_z)
            risk_score += vol_risk
            reasons.extend(vol_reasons)
            
            trend_risk, trend_reasons = self._evaluate_trend_risk(adx)
            risk_score += trend_risk
            reasons.extend(trend_reasons)
            
            time_risk, time_reasons = self._evaluate_timing_risk()
            risk_score += time_risk
            reasons.extend(time_reasons)
            
            risk_level = self._determine_risk_level(risk_score)
            gate_multiplier = self._calculate_gate_multiplier(risk_score)
            
            return {
                'risk_score': round(risk_score, 2),
                'risk_level': risk_level,
                'gate_multiplier': round(gate_multiplier, 3),
                'reasons': reasons,
                'funding_risk': round(funding_risk, 2),
                'oi_risk': round(oi_risk, 2),
                'volatility_risk': round(vol_risk, 2),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Risk gate evaluation error: {e}")
            return {
                'risk_score': 0.5,
                'risk_level': 'medium',
                'gate_multiplier': 0.5,
                'reasons': ['Error evaluating risk'],
                'status': 'error'
            }
    
    def _evaluate_funding_risk(self, funding_rate: Optional[float]) -> tuple:
        """Evaluate funding rate risk"""
        reasons = []
        risk = 0.0
        
        if funding_rate is None:
            return 0.0, []
        
        abs_funding = abs(funding_rate)
        
        if abs_funding > self.extreme_funding_threshold:
            risk = 1.0
            direction = "long" if funding_rate > 0 else "short"
            reasons.append(f"EXTREME funding rate: {funding_rate:.4f} - crowded {direction}s")
        elif abs_funding > self.high_funding_threshold:
            risk = 0.5
            direction = "long" if funding_rate > 0 else "short"
            reasons.append(f"High funding rate: {funding_rate:.4f} - elevated {direction} positioning")
        elif abs_funding > 0.003:
            risk = 0.2
            reasons.append(f"Moderate funding rate: {funding_rate:.4f}")
        
        return risk, reasons
    
    def _evaluate_oi_risk(self, oi_change_pct: Optional[float]) -> tuple:
        """Evaluate open interest risk"""
        reasons = []
        risk = 0.0
        
        if oi_change_pct is None:
            return 0.0, []
        
        abs_oi_change = abs(oi_change_pct)
        
        if abs_oi_change > self.extreme_oi_change:
            risk = 0.8
            direction = "surge" if oi_change_pct > 0 else "collapse"
            reasons.append(f"EXTREME OI {direction}: {oi_change_pct:.1f}% - potential liquidation cascade risk")
        elif abs_oi_change > 15:
            risk = 0.4
            direction = "increase" if oi_change_pct > 0 else "decrease"
            reasons.append(f"Large OI {direction}: {oi_change_pct:.1f}%")
        elif abs_oi_change > 10:
            risk = 0.2
            reasons.append(f"Notable OI change: {oi_change_pct:.1f}%")
        
        return risk, reasons
    
    def _evaluate_volatility_risk(self, volatility_pct: Optional[float], 
                                   vwap_z: Optional[float]) -> tuple:
        """Evaluate volatility and price extension risk"""
        reasons = []
        risk = 0.0
        
        if volatility_pct is not None and volatility_pct > self.high_volatility_threshold:
            risk += 0.5
            reasons.append(f"High volatility: {volatility_pct:.1f}% - increased uncertainty")
        
        if vwap_z is not None:
            if abs(vwap_z) > 3:
                risk += 0.6
                direction = "overbought" if vwap_z > 0 else "oversold"
                reasons.append(f"Extreme VWAP deviation: {vwap_z:.1f}σ - {direction}")
            elif abs(vwap_z) > 2:
                risk += 0.3
                reasons.append(f"Extended from VWAP: {vwap_z:.1f}σ")
        
        return min(risk, 1.0), reasons
    
    def _evaluate_trend_risk(self, adx: Optional[float]) -> tuple:
        """Evaluate trend strength risk"""
        reasons = []
        risk = 0.0
        
        if adx is None:
            return 0.0, []
        
        if adx < 15:
            risk = 0.3
            reasons.append(f"Low trend strength (ADX={adx:.0f}) - choppy market")
        elif adx > 50:
            risk = 0.2
            reasons.append(f"Very strong trend (ADX={adx:.0f}) - potential exhaustion")
        
        return risk, reasons
    
    def _evaluate_timing_risk(self) -> tuple:
        """Evaluate timing-based risks"""
        reasons = []
        risk = 0.0
        
        now = datetime.utcnow()
        
        if now.weekday() >= 5:
            risk += 0.2
            reasons.append("Weekend trading - lower liquidity")
        
        if 12 <= now.hour <= 15:
            reasons.append("Asia session close / Europe open overlap")
        
        return risk, reasons
    
    def _determine_risk_level(self, risk_score: float) -> str:
        """Determine overall risk level"""
        if risk_score >= 1.5:
            return "extreme"
        elif risk_score >= 1.0:
            return "high"
        elif risk_score >= 0.5:
            return "medium"
        else:
            return "low"
    
    def _calculate_gate_multiplier(self, risk_score: float) -> float:
        """
        Calculate confidence gate multiplier.
        Higher risk = lower multiplier = reduced conviction.
        """
        if risk_score >= 2.0:
            return 0.2
        elif risk_score >= 1.5:
            return 0.4
        elif risk_score >= 1.0:
            return 0.6
        elif risk_score >= 0.5:
            return 0.8
        else:
            return 1.0
