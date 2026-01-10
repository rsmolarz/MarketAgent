import math
from typing import Tuple

def var_cvar(pnls: list[float], alpha: float = 0.95) -> Tuple[float, float]:
    """
    Compute Value at Risk (VaR) and Conditional VaR (CVaR).
    
    Args:
        pnls: List of PnL values in bps
        alpha: Confidence level (0.95 = 95%)
    
    Returns:
        Tuple of (VaR, CVaR) in bps
    """
    if not pnls or len(pnls) < 3:
        return 0, 0
    
    sorted_pnls = sorted(pnls)
    var_index = int((1 - alpha) * len(sorted_pnls))
    var_index = max(0, min(var_index, len(sorted_pnls) - 1))
    
    var = sorted_pnls[var_index]
    
    tail = sorted_pnls[:var_index + 1]
    cvar = sum(tail) / len(tail) if tail else var
    
    return round(var, 2), round(cvar, 2)

def max_drawdown_bps(pnls: list[float]) -> float:
    """
    Compute maximum drawdown in bps.
    
    Args:
        pnls: List of PnL values in bps
    
    Returns:
        Maximum drawdown in bps (positive number)
    """
    if not pnls:
        return 0
    
    cumulative = 0
    peak = 0
    max_dd = 0
    
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        drawdown = peak - cumulative
        max_dd = max(max_dd, drawdown)
    
    return round(max_dd, 2)

def volatility_bps(pnls: list[float]) -> float:
    """Compute volatility (std dev) in bps"""
    if len(pnls) < 2:
        return 0
    avg = sum(pnls) / len(pnls)
    variance = sum((p - avg) ** 2 for p in pnls) / len(pnls)
    return round(math.sqrt(variance), 2)

def downside_deviation(pnls: list[float]) -> float:
    """Compute downside deviation (std of negative returns)"""
    if not pnls:
        return 0
    neg = [p for p in pnls if p < 0]
    if not neg:
        return 0
    avg = sum(neg) / len(neg)
    variance = sum((p - avg) ** 2 for p in neg) / len(neg)
    return round(math.sqrt(variance), 2)

def sortino_ratio(pnls: list[float]) -> float:
    """Compute Sortino ratio (return / downside deviation)"""
    if not pnls:
        return 0
    avg = sum(pnls) / len(pnls)
    dd = downside_deviation(pnls)
    if dd == 0:
        return 0
    return round((avg / dd) * math.sqrt(252), 3)

def calmar_ratio(pnls: list[float]) -> float:
    """Compute Calmar ratio (return / max drawdown)"""
    if not pnls:
        return 0
    total = sum(pnls)
    dd = max_drawdown_bps(pnls)
    if dd == 0:
        return 0
    return round(total / dd, 3)
