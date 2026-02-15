"""
Cross-asset risk aggregation engine.

Aggregates risk metrics from all four asset-class sub-orchestrators into
a unified portfolio-level risk view. Computes portfolio VaR, CVaR,
cross-asset correlations, and enforces risk limits.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from shared.state_schema import AssetClass, RiskMetrics

logger = logging.getLogger(__name__)


@dataclass
class RiskLimit:
    """A single risk limit with current value and threshold."""
    name: str
    current_value: float = 0.0
    warning_threshold: float = 0.0
    critical_threshold: float = 0.0
    hard_limit: float = 0.0

    @property
    def status(self) -> str:
        if abs(self.current_value) >= abs(self.hard_limit):
            return "breached"
        if abs(self.current_value) >= abs(self.critical_threshold):
            return "critical"
        if abs(self.current_value) >= abs(self.warning_threshold):
            return "warning"
        return "ok"


@dataclass
class PortfolioRiskSummary:
    """Aggregated portfolio risk summary."""
    portfolio_var_95: float = 0.0
    portfolio_cvar_95: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    asset_class_risks: Dict[str, Dict[str, float]] = field(default_factory=dict)
    cross_asset_correlations: Dict[str, float] = field(default_factory=dict)
    risk_limits: List[RiskLimit] = field(default_factory=list)
    breached_limits: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_var_95": self.portfolio_var_95,
            "portfolio_cvar_95": self.portfolio_cvar_95,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "asset_class_risks": self.asset_class_risks,
            "cross_asset_correlations": self.cross_asset_correlations,
            "breached_limits": self.breached_limits,
            "timestamp": self.timestamp.isoformat(),
        }


class RiskAggregator:
    """
    Aggregates risk from all sub-orchestrators.

    Computes:
    - Portfolio-level VaR/CVaR from individual asset class VaRs and correlations
    - Cross-asset correlation matrix
    - Gross/net exposure
    - Risk limit monitoring
    """

    DEFAULT_LIMITS = [
        RiskLimit("portfolio_var_95", 0, 0.02, 0.04, 0.05),
        RiskLimit("max_drawdown", 0, -0.10, -0.15, -0.20),
        RiskLimit("gross_exposure", 0, 0.80, 0.90, 1.0),
        RiskLimit("single_asset_concentration", 0, 0.30, 0.40, 0.50),
        RiskLimit("crypto_allocation", 0, 0.25, 0.30, 0.35),
    ]

    # Default cross-asset correlation assumptions
    DEFAULT_CORRELATIONS = {
        ("bonds", "crypto"): -0.15,
        ("bonds", "real_estate"): 0.30,
        ("bonds", "distressed"): 0.25,
        ("crypto", "real_estate"): 0.10,
        ("crypto", "distressed"): 0.05,
        ("real_estate", "distressed"): 0.40,
    }

    def __init__(
        self,
        risk_limits: Optional[List[RiskLimit]] = None,
        correlations: Optional[Dict[Tuple[str, str], float]] = None,
    ):
        self.risk_limits = risk_limits or [RiskLimit(l.name, l.current_value, l.warning_threshold, l.critical_threshold, l.hard_limit) for l in self.DEFAULT_LIMITS]
        self.correlations = correlations or dict(self.DEFAULT_CORRELATIONS)
        self._asset_class_risks: Dict[str, RiskMetrics] = {}
        self._asset_class_allocations: Dict[str, float] = {}

    def update_asset_risk(self, asset_class: str, risk: RiskMetrics) -> None:
        """Update risk metrics for a single asset class."""
        self._asset_class_risks[asset_class] = risk

    def update_allocations(self, allocations: Dict[str, float]) -> None:
        """Update current portfolio allocations."""
        self._asset_class_allocations = allocations

    def get_correlation(self, ac1: str, ac2: str) -> float:
        """Get correlation between two asset classes."""
        if ac1 == ac2:
            return 1.0
        pair = tuple(sorted([ac1, ac2]))
        return self.correlations.get(pair, 0.0)

    def compute_portfolio_var(self) -> float:
        """
        Compute portfolio VaR using variance-covariance method.

        Portfolio variance = sum_i sum_j w_i * w_j * sigma_i * sigma_j * rho_ij
        """
        classes = list(self._asset_class_allocations.keys())
        if not classes:
            return 0.0

        portfolio_variance = 0.0
        for i, ac_i in enumerate(classes):
            w_i = self._asset_class_allocations.get(ac_i, 0)
            risk_i = self._asset_class_risks.get(ac_i)
            sigma_i = risk_i.var_95 if risk_i and risk_i.var_95 else 0.02

            for j, ac_j in enumerate(classes):
                w_j = self._asset_class_allocations.get(ac_j, 0)
                risk_j = self._asset_class_risks.get(ac_j)
                sigma_j = risk_j.var_95 if risk_j and risk_j.var_95 else 0.02

                rho = self.get_correlation(ac_i, ac_j)
                portfolio_variance += w_i * w_j * sigma_i * sigma_j * rho

        return math.sqrt(max(portfolio_variance, 0))

    def aggregate(self) -> PortfolioRiskSummary:
        """
        Aggregate all asset class risks into a portfolio summary.
        """
        # Compute portfolio-level metrics
        portfolio_var = self.compute_portfolio_var()
        portfolio_cvar = portfolio_var * 1.4  # Approximation: CVaR ~ 1.4 * VaR for normal dist

        # Compute exposures
        gross = sum(abs(w) for w in self._asset_class_allocations.values())
        net = sum(self._asset_class_allocations.values())

        # Gather per-asset class summaries
        ac_risks = {}
        for ac, risk in self._asset_class_risks.items():
            ac_risks[ac] = {
                "var_95": risk.var_95,
                "cvar_95": risk.cvar_95,
                "max_drawdown": risk.max_drawdown,
                "allocation": self._asset_class_allocations.get(ac, 0),
            }
            # Add asset-specific metrics
            if risk.asset_class == AssetClass.BONDS:
                ac_risks[ac].update({"dv01": risk.dv01, "cs01": risk.cs01, "oas": risk.oas})
            elif risk.asset_class == AssetClass.CRYPTO:
                ac_risks[ac].update({
                    "realized_vol": risk.realized_volatility,
                    "implied_vol": risk.implied_volatility,
                    "liquidity_depth": risk.liquidity_depth,
                })
            elif risk.asset_class == AssetClass.REAL_ESTATE:
                ac_risks[ac].update({
                    "cap_rate": risk.cap_rate,
                    "ltv_ratio": risk.ltv_ratio,
                    "vacancy_rate": risk.vacancy_rate,
                })
            elif risk.asset_class == AssetClass.DISTRESSED:
                ac_risks[ac].update({
                    "expected_recovery": risk.expected_recovery,
                    "prob_default": risk.prob_default,
                    "time_to_resolution": risk.time_to_resolution,
                })

        # Build correlation map
        corr_map = {}
        classes = list(self._asset_class_allocations.keys())
        for i, ac_i in enumerate(classes):
            for j, ac_j in enumerate(classes):
                if i < j:
                    key = f"{ac_i}__{ac_j}"
                    corr_map[key] = self.get_correlation(ac_i, ac_j)

        # Update and check risk limits
        breached = []
        for limit in self.risk_limits:
            if limit.name == "portfolio_var_95":
                limit.current_value = portfolio_var
            elif limit.name == "max_drawdown":
                # Use worst drawdown from any asset class
                drawdowns = [
                    r.max_drawdown for r in self._asset_class_risks.values()
                    if r.max_drawdown is not None
                ]
                limit.current_value = min(drawdowns) if drawdowns else 0
            elif limit.name == "gross_exposure":
                limit.current_value = gross
            elif limit.name == "single_asset_concentration":
                limit.current_value = max(
                    abs(w) for w in self._asset_class_allocations.values()
                ) if self._asset_class_allocations else 0
            elif limit.name == "crypto_allocation":
                limit.current_value = abs(self._asset_class_allocations.get("crypto", 0))

            if limit.status in ("breached", "critical"):
                breached.append(f"{limit.name}: {limit.status} ({limit.current_value:.4f})")

        return PortfolioRiskSummary(
            portfolio_var_95=portfolio_var,
            portfolio_cvar_95=portfolio_cvar,
            gross_exposure=gross,
            net_exposure=net,
            asset_class_risks=ac_risks,
            cross_asset_correlations=corr_map,
            risk_limits=self.risk_limits,
            breached_limits=breached,
        )
