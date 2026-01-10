"""
Distressed Portfolio & Risk Management System
=============================================
Track positions, P&L, exposure, and risk limits.

Features:
- Position tracking with mark-to-market
- Risk limits (concentration, sector, seniority)
- Real-time P&L and exposure reporting
- VaR and stress testing
- Correlation analysis
- Alert system
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import math
import uuid

logger = logging.getLogger(__name__)


class SecurityType(Enum):
    SECURED_LOAN = "secured_loan"
    SECURED_BOND = "secured_bond"
    SENIOR_UNSECURED = "senior_unsecured"
    SUBORDINATED = "subordinated"
    CONVERTIBLE = "convertible"
    TRADE_CLAIM = "trade_claim"
    DIP_LOAN = "dip_loan"
    EQUITY = "equity"
    CDS = "cds"  # For hedging


class PositionStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"


@dataclass
class Position:
    """Individual position in the portfolio."""
    position_id: str
    company_name: str
    company_id: str  # Internal identifier
    security_type: SecurityType
    security_id: str  # CUSIP, ISIN, or internal ID
    
    # Position details
    face_amount: float  # Par/face value
    entry_price: float  # Price paid (cents on dollar)
    entry_date: str
    
    # Current state
    current_price: float = 0
    current_value: float = 0
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0
    
    # Realized P&L (partial exits)
    realized_pnl: float = 0
    
    # Accrued interest/income
    accrued_interest: float = 0
    coupon_rate: float = 0
    
    # Risk metrics
    duration: float = 0
    spread_duration: float = 0
    recovery_estimate: float = 50  # Expected recovery
    
    # Classification
    industry: str = ""
    case_status: str = ""  # performing, stressed, distressed, bankruptcy
    seniority_rank: int = 1  # 1 = most senior
    
    # Metadata
    status: PositionStatus = PositionStatus.OPEN
    notes: str = ""
    last_updated: str = ""
    
    def update_mark(self, new_price: float):
        """Update position with new price."""
        self.current_price = new_price
        self.current_value = self.face_amount * (new_price / 100)
        cost_basis = self.face_amount * (self.entry_price / 100)
        self.unrealized_pnl = self.current_value - cost_basis + self.realized_pnl
        self.unrealized_pnl_pct = self.unrealized_pnl / cost_basis if cost_basis > 0 else 0
        self.last_updated = datetime.utcnow().isoformat()


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    # Position limits
    max_single_position_pct: float = 0.10        # 10% max single position
    max_single_issuer_pct: float = 0.15          # 15% max single issuer
    
    # Sector limits
    max_sector_exposure_pct: float = 0.25        # 25% max per sector
    
    # Seniority limits
    max_subordinated_pct: float = 0.30           # 30% max subordinated
    max_equity_pct: float = 0.10                 # 10% max equity
    
    # Status limits
    max_bankruptcy_pct: float = 0.50             # 50% max in bankruptcy
    max_distressed_pct: float = 0.70             # 70% max distressed
    
    # Risk metrics
    max_portfolio_var_pct: float = 0.15          # 15% max daily VaR
    max_drawdown_pct: float = 0.25               # 25% max drawdown trigger
    
    # Concentration
    min_positions: int = 5                        # Minimum diversification
    max_positions: int = 50                       # Maximum positions
    
    # Leverage
    max_gross_leverage: float = 1.5              # 150% gross
    max_net_leverage: float = 1.0                # 100% net (no leverage)


@dataclass
class RiskAlert:
    """Alert when risk limit breached."""
    alert_id: str
    alert_type: str  # limit_breach, drawdown, concentration, etc.
    severity: str    # warning, critical
    message: str
    metric_name: str
    current_value: float
    limit_value: float
    timestamp: str
    acknowledged: bool = False


@dataclass 
class PortfolioSnapshot:
    """Point-in-time portfolio snapshot."""
    snapshot_id: str
    timestamp: str
    
    # Values
    nav: float = 0                    # Net Asset Value
    gross_exposure: float = 0
    net_exposure: float = 0
    cash: float = 0
    
    # P&L
    total_pnl: float = 0
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    daily_pnl: float = 0
    mtd_pnl: float = 0
    ytd_pnl: float = 0
    
    # Returns
    daily_return: float = 0
    mtd_return: float = 0
    ytd_return: float = 0
    
    # Exposures
    exposure_by_sector: Dict[str, float] = field(default_factory=dict)
    exposure_by_seniority: Dict[str, float] = field(default_factory=dict)
    exposure_by_status: Dict[str, float] = field(default_factory=dict)
    
    # Risk metrics
    var_95: float = 0
    expected_shortfall: float = 0
    portfolio_duration: float = 0
    avg_recovery_estimate: float = 0
    
    # Counts
    position_count: int = 0
    issuer_count: int = 0


class Portfolio:
    """
    Main portfolio management class.
    Tracks positions, calculates risk, enforces limits.
    """
    
    def __init__(
        self,
        portfolio_id: str,
        initial_capital: float,
        risk_limits: Optional[RiskLimits] = None
    ):
        self.portfolio_id = portfolio_id
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.risk_limits = risk_limits or RiskLimits()
        
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.snapshots: List[PortfolioSnapshot] = []
        self.alerts: List[RiskAlert] = []
        self.trades: List[Dict[str, Any]] = []
        
        # Historical tracking
        self.high_water_mark = initial_capital
        self.max_drawdown = 0
        
    # === Position Management ===
    
    def add_position(self, position: Position) -> Tuple[bool, str]:
        """Add a new position after checking limits."""
        # Check risk limits before adding
        violations = self._check_position_limits(position)
        if violations:
            return False, f"Risk limit violations: {', '.join(violations)}"
        
        # Check cash availability
        cost = position.face_amount * (position.entry_price / 100)
        if cost > self.cash:
            return False, f"Insufficient cash: need {cost:,.0f}, have {self.cash:,.0f}"
        
        # Add position
        self.positions[position.position_id] = position
        self.cash -= cost
        
        # Record trade
        self.trades.append({
            "trade_id": str(uuid.uuid4()),
            "position_id": position.position_id,
            "action": "buy",
            "face_amount": position.face_amount,
            "price": position.entry_price,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # Update position mark
        position.update_mark(position.entry_price)
        
        logger.info(f"[Portfolio] Added position: {position.company_name} {position.security_type.value}")
        return True, "Position added successfully"
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_date: Optional[str] = None
    ) -> Tuple[bool, str, float]:
        """Close a position and realize P&L."""
        if position_id not in self.positions:
            return False, "Position not found", 0
        
        position = self.positions[position_id]
        
        # Calculate realized P&L
        cost_basis = position.face_amount * (position.entry_price / 100)
        proceeds = position.face_amount * (exit_price / 100)
        realized_pnl = proceeds - cost_basis + position.accrued_interest
        
        # Update position
        position.status = PositionStatus.CLOSED
        position.current_price = exit_price
        position.realized_pnl = realized_pnl
        position.unrealized_pnl = 0
        
        # Move to closed
        self.closed_positions.append(position)
        del self.positions[position_id]
        
        # Update cash
        self.cash += proceeds
        
        # Record trade
        self.trades.append({
            "trade_id": str(uuid.uuid4()),
            "position_id": position_id,
            "action": "sell",
            "face_amount": position.face_amount,
            "price": exit_price,
            "realized_pnl": realized_pnl,
            "timestamp": exit_date or datetime.utcnow().isoformat(),
        })
        
        logger.info(f"[Portfolio] Closed position: {position.company_name}, P&L: {realized_pnl:,.0f}")
        return True, "Position closed", realized_pnl
    
    def partial_exit(
        self,
        position_id: str,
        exit_amount: float,
        exit_price: float
    ) -> Tuple[bool, str, float]:
        """Partially exit a position."""
        if position_id not in self.positions:
            return False, "Position not found", 0
        
        position = self.positions[position_id]
        
        if exit_amount > position.face_amount:
            return False, "Exit amount exceeds position size", 0
        
        # Calculate proportional P&L
        exit_pct = exit_amount / position.face_amount
        cost_basis = exit_amount * (position.entry_price / 100)
        proceeds = exit_amount * (exit_price / 100)
        realized_pnl = proceeds - cost_basis
        
        # Update position
        position.face_amount -= exit_amount
        position.realized_pnl += realized_pnl
        
        # Update cash
        self.cash += proceeds
        
        # If fully exited
        if position.face_amount <= 0:
            return self.close_position(position_id, exit_price)
        
        position.update_mark(position.current_price)
        
        return True, "Partial exit executed", realized_pnl
    
    def update_marks(self, prices: Dict[str, float]):
        """Update all position marks with new prices."""
        for pos_id, position in self.positions.items():
            if position.security_id in prices:
                position.update_mark(prices[position.security_id])
    
    # === Risk Limit Checking ===
    
    def _check_position_limits(self, new_position: Position) -> List[str]:
        """Check if new position would violate limits."""
        violations = []
        nav = self._calculate_nav()
        
        # Single position limit
        position_value = new_position.face_amount * (new_position.entry_price / 100)
        if position_value / nav > self.risk_limits.max_single_position_pct:
            violations.append(f"Single position limit ({self.risk_limits.max_single_position_pct*100:.0f}%)")
        
        # Issuer limit
        issuer_exposure = sum(
            p.current_value for p in self.positions.values()
            if p.company_id == new_position.company_id
        )
        if (issuer_exposure + position_value) / nav > self.risk_limits.max_single_issuer_pct:
            violations.append(f"Single issuer limit ({self.risk_limits.max_single_issuer_pct*100:.0f}%)")
        
        # Sector limit
        sector_exposure = sum(
            p.current_value for p in self.positions.values()
            if p.industry == new_position.industry
        )
        if (sector_exposure + position_value) / nav > self.risk_limits.max_sector_exposure_pct:
            violations.append(f"Sector limit ({self.risk_limits.max_sector_exposure_pct*100:.0f}%)")
        
        # Seniority limits
        if new_position.security_type in [SecurityType.SUBORDINATED, SecurityType.CONVERTIBLE]:
            sub_exposure = sum(
                p.current_value for p in self.positions.values()
                if p.security_type in [SecurityType.SUBORDINATED, SecurityType.CONVERTIBLE]
            )
            if (sub_exposure + position_value) / nav > self.risk_limits.max_subordinated_pct:
                violations.append(f"Subordinated limit ({self.risk_limits.max_subordinated_pct*100:.0f}%)")
        
        if new_position.security_type == SecurityType.EQUITY:
            equity_exposure = sum(
                p.current_value for p in self.positions.values()
                if p.security_type == SecurityType.EQUITY
            )
            if (equity_exposure + position_value) / nav > self.risk_limits.max_equity_pct:
                violations.append(f"Equity limit ({self.risk_limits.max_equity_pct*100:.0f}%)")
        
        # Status limits
        if new_position.case_status == "bankruptcy":
            bk_exposure = sum(
                p.current_value for p in self.positions.values()
                if p.case_status == "bankruptcy"
            )
            if (bk_exposure + position_value) / nav > self.risk_limits.max_bankruptcy_pct:
                violations.append(f"Bankruptcy limit ({self.risk_limits.max_bankruptcy_pct*100:.0f}%)")
        
        # Position count
        if len(self.positions) >= self.risk_limits.max_positions:
            violations.append(f"Max positions ({self.risk_limits.max_positions})")
        
        return violations
    
    def check_all_limits(self) -> List[RiskAlert]:
        """Check all risk limits and generate alerts."""
        alerts = []
        nav = self._calculate_nav()
        
        if nav <= 0:
            return alerts
        
        # Concentration by issuer
        issuer_exposures: Dict[str, float] = {}
        for pos in self.positions.values():
            issuer_exposures[pos.company_id] = issuer_exposures.get(pos.company_id, 0) + pos.current_value
        
        for issuer, exposure in issuer_exposures.items():
            pct = exposure / nav
            if pct > self.risk_limits.max_single_issuer_pct:
                alerts.append(RiskAlert(
                    alert_id=str(uuid.uuid4()),
                    alert_type="concentration",
                    severity="critical" if pct > self.risk_limits.max_single_issuer_pct * 1.2 else "warning",
                    message=f"Issuer {issuer} at {pct*100:.1f}% (limit: {self.risk_limits.max_single_issuer_pct*100:.0f}%)",
                    metric_name="issuer_concentration",
                    current_value=pct,
                    limit_value=self.risk_limits.max_single_issuer_pct,
                    timestamp=datetime.utcnow().isoformat(),
                ))
        
        # Sector concentration
        sector_exposures: Dict[str, float] = {}
        for pos in self.positions.values():
            sector_exposures[pos.industry] = sector_exposures.get(pos.industry, 0) + pos.current_value
        
        for sector, exposure in sector_exposures.items():
            pct = exposure / nav
            if pct > self.risk_limits.max_sector_exposure_pct:
                alerts.append(RiskAlert(
                    alert_id=str(uuid.uuid4()),
                    alert_type="sector_concentration",
                    severity="warning",
                    message=f"Sector {sector} at {pct*100:.1f}%",
                    metric_name="sector_concentration",
                    current_value=pct,
                    limit_value=self.risk_limits.max_sector_exposure_pct,
                    timestamp=datetime.utcnow().isoformat(),
                ))
        
        # Drawdown check
        current_dd = (self.high_water_mark - nav) / self.high_water_mark
        if current_dd > self.risk_limits.max_drawdown_pct:
            alerts.append(RiskAlert(
                alert_id=str(uuid.uuid4()),
                alert_type="drawdown",
                severity="critical",
                message=f"Drawdown at {current_dd*100:.1f}% exceeds limit",
                metric_name="drawdown",
                current_value=current_dd,
                limit_value=self.risk_limits.max_drawdown_pct,
                timestamp=datetime.utcnow().isoformat(),
            ))
        
        # Minimum diversification
        if len(self.positions) < self.risk_limits.min_positions and len(self.positions) > 0:
            alerts.append(RiskAlert(
                alert_id=str(uuid.uuid4()),
                alert_type="diversification",
                severity="warning",
                message=f"Only {len(self.positions)} positions (min: {self.risk_limits.min_positions})",
                metric_name="position_count",
                current_value=len(self.positions),
                limit_value=self.risk_limits.min_positions,
                timestamp=datetime.utcnow().isoformat(),
            ))
        
        self.alerts.extend(alerts)
        return alerts
    
    # === Calculations ===
    
    def _calculate_nav(self) -> float:
        """Calculate Net Asset Value."""
        position_value = sum(p.current_value for p in self.positions.values())
        return self.cash + position_value
    
    def _calculate_exposure(self, exposure_type: str) -> Dict[str, float]:
        """Calculate exposure breakdown."""
        exposures: Dict[str, float] = {}
        
        for pos in self.positions.values():
            if exposure_type == "sector":
                key = pos.industry
            elif exposure_type == "seniority":
                key = pos.security_type.value
            elif exposure_type == "status":
                key = pos.case_status
            else:
                key = "other"
            
            exposures[key] = exposures.get(key, 0) + pos.current_value
        
        return exposures
    
    def _calculate_var(self, confidence: float = 0.95, lookback: int = 20) -> float:
        """
        Calculate Value at Risk using historical simulation.
        Uses recent P&L changes.
        """
        if len(self.snapshots) < lookback:
            return 0
        
        # Get recent daily returns
        returns = []
        for i in range(1, min(lookback + 1, len(self.snapshots))):
            if self.snapshots[i-1].nav > 0:
                ret = (self.snapshots[i].nav - self.snapshots[i-1].nav) / self.snapshots[i-1].nav
                returns.append(ret)
        
        if not returns:
            return 0
        
        # Sort and find VaR percentile
        sorted_returns = sorted(returns)
        var_index = int((1 - confidence) * len(sorted_returns))
        
        return abs(sorted_returns[var_index]) if var_index < len(sorted_returns) else 0
    
    def _calculate_expected_shortfall(self, confidence: float = 0.95, lookback: int = 20) -> float:
        """Calculate Expected Shortfall (CVaR)."""
        if len(self.snapshots) < lookback:
            return 0
        
        returns = []
        for i in range(1, min(lookback + 1, len(self.snapshots))):
            if self.snapshots[i-1].nav > 0:
                ret = (self.snapshots[i].nav - self.snapshots[i-1].nav) / self.snapshots[i-1].nav
                returns.append(ret)
        
        if not returns:
            return 0
        
        sorted_returns = sorted(returns)
        var_index = int((1 - confidence) * len(sorted_returns))
        tail = sorted_returns[:var_index + 1]
        
        return abs(sum(tail) / len(tail)) if tail else 0
    
    # === Snapshot & Reporting ===
    
    def take_snapshot(self) -> PortfolioSnapshot:
        """Take current portfolio snapshot."""
        nav = self._calculate_nav()
        
        # Update high water mark and drawdown
        if nav > self.high_water_mark:
            self.high_water_mark = nav
        current_dd = (self.high_water_mark - nav) / self.high_water_mark if self.high_water_mark > 0 else 0
        self.max_drawdown = max(self.max_drawdown, current_dd)
        
        # Calculate P&L
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        total_realized = sum(p.realized_pnl for p in self.closed_positions)
        total_pnl = total_unrealized + total_realized
        
        # Daily P&L (vs last snapshot)
        daily_pnl = 0
        daily_return = 0
        if self.snapshots:
            last = self.snapshots[-1]
            daily_pnl = nav - last.nav
            daily_return = daily_pnl / last.nav if last.nav > 0 else 0
        
        # MTD/YTD (simplified - assumes daily snapshots)
        mtd_pnl = 0
        ytd_pnl = 0
        now = datetime.utcnow()
        for snap in reversed(self.snapshots):
            snap_date = datetime.fromisoformat(snap.timestamp)
            if snap_date.month == now.month and snap_date.year == now.year:
                mtd_pnl = nav - snap.nav
            if snap_date.year == now.year and snap_date.month == 1 and snap_date.day <= 5:
                ytd_pnl = nav - snap.nav
                break
        
        snapshot = PortfolioSnapshot(
            snapshot_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            nav=nav,
            gross_exposure=sum(p.current_value for p in self.positions.values()),
            net_exposure=sum(p.current_value for p in self.positions.values()),  # Simplified
            cash=self.cash,
            total_pnl=total_pnl,
            realized_pnl=total_realized,
            unrealized_pnl=total_unrealized,
            daily_pnl=daily_pnl,
            mtd_pnl=mtd_pnl,
            ytd_pnl=ytd_pnl,
            daily_return=daily_return,
            exposure_by_sector=self._calculate_exposure("sector"),
            exposure_by_seniority=self._calculate_exposure("seniority"),
            exposure_by_status=self._calculate_exposure("status"),
            var_95=self._calculate_var(0.95),
            expected_shortfall=self._calculate_expected_shortfall(0.95),
            portfolio_duration=sum(p.duration * p.current_value for p in self.positions.values()) / nav if nav > 0 else 0,
            avg_recovery_estimate=sum(p.recovery_estimate * p.current_value for p in self.positions.values()) / nav if nav > 0 else 0,
            position_count=len(self.positions),
            issuer_count=len(set(p.company_id for p in self.positions.values())),
        )
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def get_position_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all positions."""
        return [
            {
                "position_id": p.position_id,
                "company": p.company_name,
                "security_type": p.security_type.value,
                "face_amount": p.face_amount,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "current_value": p.current_value,
                "unrealized_pnl": p.unrealized_pnl,
                "pnl_pct": p.unrealized_pnl_pct * 100,
                "industry": p.industry,
                "status": p.case_status,
            }
            for p in self.positions.values()
        ]
    
    def get_exposure_report(self) -> Dict[str, Any]:
        """Get detailed exposure report."""
        nav = self._calculate_nav()
        
        return {
            "nav": nav,
            "cash": self.cash,
            "cash_pct": self.cash / nav * 100 if nav > 0 else 0,
            "invested": nav - self.cash,
            "invested_pct": (nav - self.cash) / nav * 100 if nav > 0 else 0,
            "by_sector": {
                k: {"value": v, "pct": v / nav * 100}
                for k, v in self._calculate_exposure("sector").items()
            },
            "by_seniority": {
                k: {"value": v, "pct": v / nav * 100}
                for k, v in self._calculate_exposure("seniority").items()
            },
            "by_status": {
                k: {"value": v, "pct": v / nav * 100}
                for k, v in self._calculate_exposure("status").items()
            },
            "top_positions": sorted(
                self.get_position_summary(),
                key=lambda x: x["current_value"],
                reverse=True
            )[:10],
        }
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Get risk metrics report."""
        nav = self._calculate_nav()
        
        return {
            "nav": nav,
            "initial_capital": self.initial_capital,
            "total_return": (nav - self.initial_capital) / self.initial_capital * 100,
            "high_water_mark": self.high_water_mark,
            "current_drawdown": (self.high_water_mark - nav) / self.high_water_mark * 100 if self.high_water_mark > 0 else 0,
            "max_drawdown": self.max_drawdown * 100,
            "var_95": self._calculate_var(0.95) * 100,
            "expected_shortfall": self._calculate_expected_shortfall(0.95) * 100,
            "position_count": len(self.positions),
            "issuer_count": len(set(p.company_id for p in self.positions.values())),
            "avg_position_size": nav / len(self.positions) if self.positions else 0,
            "largest_position_pct": max(
                (p.current_value / nav * 100 for p in self.positions.values()),
                default=0
            ),
            "active_alerts": len([a for a in self.alerts if not a.acknowledged]),
        }
    
    # === Stress Testing ===
    
    def run_stress_test(self, scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run stress tests on portfolio.
        
        Each scenario is a dict with:
        - name: Scenario name
        - price_shocks: Dict of security_type -> price change (e.g., -0.20 for -20%)
        - recovery_shocks: Dict of status -> recovery change
        """
        results = []
        current_nav = self._calculate_nav()
        
        for scenario in scenarios:
            scenario_pnl = 0
            
            for pos in self.positions.values():
                # Apply price shock
                price_shock = scenario.get("price_shocks", {}).get(
                    pos.security_type.value, 
                    scenario.get("price_shocks", {}).get("default", 0)
                )
                
                # Apply recovery shock based on status
                recovery_shock = scenario.get("recovery_shocks", {}).get(
                    pos.case_status,
                    0
                )
                
                # Combined shock
                total_shock = price_shock + recovery_shock
                position_pnl = pos.current_value * total_shock
                scenario_pnl += position_pnl
            
            results.append({
                "scenario": scenario.get("name", "Unknown"),
                "pnl": scenario_pnl,
                "pnl_pct": scenario_pnl / current_nav * 100 if current_nav > 0 else 0,
                "nav_after": current_nav + scenario_pnl,
            })
        
        return results
    
    def get_default_stress_scenarios(self) -> List[Dict[str, Any]]:
        """Get standard stress test scenarios."""
        return [
            {
                "name": "2008 Financial Crisis",
                "price_shocks": {
                    "secured_loan": -0.15,
                    "secured_bond": -0.20,
                    "senior_unsecured": -0.35,
                    "subordinated": -0.50,
                    "equity": -0.80,
                    "default": -0.25,
                },
            },
            {
                "name": "Sector Blowup",
                "price_shocks": {
                    "default": -0.30,
                },
                "recovery_shocks": {
                    "bankruptcy": -0.20,
                    "distressed": -0.15,
                },
            },
            {
                "name": "Liquidity Crisis",
                "price_shocks": {
                    "senior_unsecured": -0.20,
                    "subordinated": -0.40,
                    "trade_claim": -0.30,
                    "default": -0.15,
                },
            },
            {
                "name": "Recovery Rally",
                "price_shocks": {
                    "secured_bond": 0.10,
                    "senior_unsecured": 0.25,
                    "subordinated": 0.40,
                    "equity": 0.60,
                    "default": 0.20,
                },
            },
            {
                "name": "Bankruptcy Wave",
                "recovery_shocks": {
                    "bankruptcy": -0.15,
                    "distressed": -0.25,
                    "stressed": -0.10,
                },
            },
        ]


class PortfolioManager:
    """
    High-level portfolio manager for multiple portfolios.
    """
    
    def __init__(self):
        self.portfolios: Dict[str, Portfolio] = {}
    
    def create_portfolio(
        self,
        portfolio_id: str,
        initial_capital: float,
        risk_limits: Optional[RiskLimits] = None
    ) -> Portfolio:
        """Create a new portfolio."""
        portfolio = Portfolio(portfolio_id, initial_capital, risk_limits)
        self.portfolios[portfolio_id] = portfolio
        return portfolio
    
    def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Get portfolio by ID."""
        return self.portfolios.get(portfolio_id)
    
    def get_aggregate_exposure(self) -> Dict[str, Any]:
        """Get aggregate exposure across all portfolios."""
        total_nav = 0
        total_exposure_by_sector: Dict[str, float] = {}
        total_exposure_by_seniority: Dict[str, float] = {}
        
        for portfolio in self.portfolios.values():
            nav = portfolio._calculate_nav()
            total_nav += nav
            
            for sector, exposure in portfolio._calculate_exposure("sector").items():
                total_exposure_by_sector[sector] = total_exposure_by_sector.get(sector, 0) + exposure
            
            for seniority, exposure in portfolio._calculate_exposure("seniority").items():
                total_exposure_by_seniority[seniority] = total_exposure_by_seniority.get(seniority, 0) + exposure
        
        return {
            "total_nav": total_nav,
            "portfolio_count": len(self.portfolios),
            "by_sector": total_exposure_by_sector,
            "by_seniority": total_exposure_by_seniority,
        }
    
    def check_all_alerts(self) -> List[RiskAlert]:
        """Check alerts across all portfolios."""
        all_alerts = []
        for portfolio in self.portfolios.values():
            alerts = portfolio.check_all_limits()
            all_alerts.extend(alerts)
        return all_alerts
