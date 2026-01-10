"""
Distressed Investing Backtesting Framework
==========================================
Test distressed investing strategies against historical bankruptcies.

Features:
- Historical case database (Enron, Lehman, etc.)
- Signal backtesting with recovery outcomes
- Performance metrics (Sharpe, max drawdown, etc.)
- Monte Carlo simulation
- Walk-forward optimization
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import random
import math

logger = logging.getLogger(__name__)


class OutcomeType(Enum):
    REORGANIZATION = "reorganization"      # Chapter 11 emergence
    LIQUIDATION = "liquidation"            # Chapter 7
    ACQUISITION = "acquisition"            # 363 sale
    OUT_OF_COURT = "out_of_court"          # Exchange/workout
    CONVERSION = "conversion"              # Ch 11 -> Ch 7


@dataclass
class HistoricalCase:
    """Historical bankruptcy case for backtesting."""
    case_id: str
    company_name: str
    industry: str
    filing_date: str
    resolution_date: str
    outcome: OutcomeType
    total_debt: float
    enterprise_value_at_filing: float
    enterprise_value_at_resolution: float
    
    # Capital structure at filing
    secured_debt: float = 0
    senior_unsecured_debt: float = 0
    subordinated_debt: float = 0
    trade_claims: float = 0
    
    # Actual recoveries by class (cents on dollar)
    secured_recovery: float = 100
    senior_unsecured_recovery: float = 0
    subordinated_recovery: float = 0
    equity_recovery: float = 0
    trade_claims_recovery: float = 0
    
    # Trading prices at various points
    prices_at_filing: Dict[str, float] = field(default_factory=dict)
    prices_at_resolution: Dict[str, float] = field(default_factory=dict)
    price_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timeline
    days_in_bankruptcy: int = 0
    key_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    z_score_at_filing: Optional[float] = None
    ebitda_at_filing: Optional[float] = None
    leverage_at_filing: Optional[float] = None


@dataclass
class Trade:
    """Individual trade in backtest."""
    trade_id: str
    case_id: str
    security_class: str  # secured, senior_unsecured, subordinated, equity
    entry_date: str
    entry_price: float
    position_size: float  # notional amount
    
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: float = 0
    pnl_pct: float = 0
    holding_days: int = 0
    
    signal_score: Optional[float] = None
    signal_reason: Optional[str] = None


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    strategy_name: str
    start_date: str
    end_date: str
    
    # Performance metrics
    total_return: float = 0
    annualized_return: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    max_drawdown: float = 0
    win_rate: float = 0
    profit_factor: float = 0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0
    avg_loss: float = 0
    avg_holding_period: float = 0
    
    # Risk metrics
    volatility: float = 0
    var_95: float = 0  # Value at Risk
    expected_shortfall: float = 0
    
    # By security class
    returns_by_class: Dict[str, float] = field(default_factory=dict)
    trades_by_class: Dict[str, int] = field(default_factory=dict)
    
    # Equity curve
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    
    # All trades
    trades: List[Trade] = field(default_factory=list)


class HistoricalCaseDatabase:
    """
    Database of historical bankruptcy cases for backtesting.
    Includes major cases with actual recovery data.
    """
    
    def __init__(self):
        self.cases: Dict[str, HistoricalCase] = {}
        self._load_historical_cases()
    
    def _load_historical_cases(self):
        """Load historical bankruptcy cases."""
        
        # Enron (2001) - Fraud/Liquidation
        self.cases["enron_2001"] = HistoricalCase(
            case_id="enron_2001",
            company_name="Enron Corp",
            industry="energy",
            filing_date="2001-12-02",
            resolution_date="2004-11-17",
            outcome=OutcomeType.LIQUIDATION,
            total_debt=31_200_000_000,
            enterprise_value_at_filing=63_400_000_000,
            enterprise_value_at_resolution=11_000_000_000,
            secured_debt=4_000_000_000,
            senior_unsecured_debt=18_000_000_000,
            subordinated_debt=5_000_000_000,
            trade_claims=4_200_000_000,
            secured_recovery=100,
            senior_unsecured_recovery=53,
            subordinated_recovery=0,
            equity_recovery=0,
            trade_claims_recovery=17,
            prices_at_filing={"senior_unsecured": 20, "subordinated": 5, "equity": 0.26},
            prices_at_resolution={"senior_unsecured": 53, "subordinated": 0, "equity": 0},
            days_in_bankruptcy=1081,
            z_score_at_filing=0.85,
            ebitda_at_filing=1_000_000_000,
            leverage_at_filing=31.2,
        )
        
        # Lehman Brothers (2008) - Financial Crisis
        self.cases["lehman_2008"] = HistoricalCase(
            case_id="lehman_2008",
            company_name="Lehman Brothers Holdings",
            industry="financial_services",
            filing_date="2008-09-15",
            resolution_date="2017-03-28",
            outcome=OutcomeType.LIQUIDATION,
            total_debt=613_000_000_000,
            enterprise_value_at_filing=639_000_000_000,
            enterprise_value_at_resolution=91_000_000_000,
            secured_debt=50_000_000_000,
            senior_unsecured_debt=400_000_000_000,
            subordinated_debt=100_000_000_000,
            trade_claims=63_000_000_000,
            secured_recovery=100,
            senior_unsecured_recovery=21,
            subordinated_recovery=4,
            equity_recovery=0,
            trade_claims_recovery=21,
            prices_at_filing={"senior_unsecured": 35, "subordinated": 12, "equity": 0.21},
            prices_at_resolution={"senior_unsecured": 21, "subordinated": 4, "equity": 0},
            days_in_bankruptcy=3116,
            z_score_at_filing=0.45,
            leverage_at_filing=30.7,
        )
        
        # General Motors (2009) - Auto Bailout
        self.cases["gm_2009"] = HistoricalCase(
            case_id="gm_2009",
            company_name="General Motors Corporation",
            industry="automotive",
            filing_date="2009-06-01",
            resolution_date="2009-07-10",
            outcome=OutcomeType.REORGANIZATION,
            total_debt=172_000_000_000,
            enterprise_value_at_filing=82_000_000_000,
            enterprise_value_at_resolution=55_000_000_000,
            secured_debt=6_000_000_000,
            senior_unsecured_debt=27_000_000_000,
            subordinated_debt=0,
            trade_claims=20_000_000_000,
            secured_recovery=100,
            senior_unsecured_recovery=10,  # New GM equity
            subordinated_recovery=0,
            equity_recovery=0,
            trade_claims_recovery=100,  # Trade claims paid in full
            prices_at_filing={"senior_unsecured": 8, "equity": 0.75},
            prices_at_resolution={"senior_unsecured": 10, "equity": 0},
            days_in_bankruptcy=40,  # Very fast 363 sale
            z_score_at_filing=0.15,
            ebitda_at_filing=-38_000_000_000,
            leverage_at_filing=999,  # Negative EBITDA
        )
        
        # Toys R Us (2017) - Retail Apocalypse
        self.cases["toysrus_2017"] = HistoricalCase(
            case_id="toysrus_2017",
            company_name="Toys R Us Inc",
            industry="retail",
            filing_date="2017-09-18",
            resolution_date="2018-06-29",
            outcome=OutcomeType.LIQUIDATION,
            total_debt=7_900_000_000,
            enterprise_value_at_filing=6_600_000_000,
            enterprise_value_at_resolution=1_000_000_000,
            secured_debt=2_600_000_000,
            senior_unsecured_debt=1_800_000_000,
            subordinated_debt=2_000_000_000,
            trade_claims=1_500_000_000,
            secured_recovery=21,
            senior_unsecured_recovery=0,
            subordinated_recovery=0,
            equity_recovery=0,
            trade_claims_recovery=0,
            prices_at_filing={"secured": 85, "senior_unsecured": 40, "subordinated": 15},
            prices_at_resolution={"secured": 21, "senior_unsecured": 0, "subordinated": 0},
            days_in_bankruptcy=284,
            z_score_at_filing=0.92,
            ebitda_at_filing=460_000_000,
            leverage_at_filing=17.2,
        )
        
        # Hertz (2020) - COVID-19
        self.cases["hertz_2020"] = HistoricalCase(
            case_id="hertz_2020",
            company_name="Hertz Global Holdings",
            industry="transportation",
            filing_date="2020-05-22",
            resolution_date="2021-06-30",
            outcome=OutcomeType.REORGANIZATION,
            total_debt=19_000_000_000,
            enterprise_value_at_filing=15_000_000_000,
            enterprise_value_at_resolution=24_000_000_000,
            secured_debt=14_400_000_000,
            senior_unsecured_debt=2_700_000_000,
            subordinated_debt=0,
            trade_claims=1_900_000_000,
            secured_recovery=100,
            senior_unsecured_recovery=100,
            subordinated_recovery=0,
            equity_recovery=100,  # Rare - old equity got value
            trade_claims_recovery=100,
            prices_at_filing={"senior_unsecured": 40, "equity": 0.56},
            prices_at_resolution={"senior_unsecured": 100, "equity": 26.24},
            days_in_bankruptcy=404,
            z_score_at_filing=1.1,
            ebitda_at_filing=1_200_000_000,
            leverage_at_filing=15.8,
        )
        
        # Pacific Gas & Electric (2019) - Wildfire Liabilities
        self.cases["pge_2019"] = HistoricalCase(
            case_id="pge_2019",
            company_name="PG&E Corporation",
            industry="utilities",
            filing_date="2019-01-29",
            resolution_date="2020-07-01",
            outcome=OutcomeType.REORGANIZATION,
            total_debt=51_700_000_000,
            enterprise_value_at_filing=25_000_000_000,
            enterprise_value_at_resolution=45_000_000_000,
            secured_debt=17_500_000_000,
            senior_unsecured_debt=20_000_000_000,
            subordinated_debt=0,
            trade_claims=14_200_000_000,  # Wildfire claims
            secured_recovery=100,
            senior_unsecured_recovery=100,
            subordinated_recovery=0,
            equity_recovery=5,  # Heavy dilution
            trade_claims_recovery=80,  # Fire victims trust
            prices_at_filing={"senior_unsecured": 93, "equity": 17.09},
            prices_at_resolution={"senior_unsecured": 100, "equity": 9.38},
            days_in_bankruptcy=519,
            z_score_at_filing=2.8,
            ebitda_at_filing=4_800_000_000,
            leverage_at_filing=10.8,
        )
        
        # J.Crew (2020) - COVID Retail
        self.cases["jcrew_2020"] = HistoricalCase(
            case_id="jcrew_2020",
            company_name="J.Crew Group",
            industry="retail",
            filing_date="2020-05-04",
            resolution_date="2020-09-10",
            outcome=OutcomeType.REORGANIZATION,
            total_debt=1_700_000_000,
            enterprise_value_at_filing=600_000_000,
            enterprise_value_at_resolution=1_100_000_000,
            secured_debt=1_100_000_000,
            senior_unsecured_debt=500_000_000,
            subordinated_debt=0,
            trade_claims=100_000_000,
            secured_recovery=82,  # Equitized
            senior_unsecured_recovery=0,
            subordinated_recovery=0,
            equity_recovery=0,
            trade_claims_recovery=0,
            prices_at_filing={"secured": 55, "senior_unsecured": 5},
            prices_at_resolution={"secured": 82, "senior_unsecured": 0},
            days_in_bankruptcy=129,
            z_score_at_filing=0.35,
            ebitda_at_filing=50_000_000,
            leverage_at_filing=34,
        )
        
        # Caesars Entertainment (2015) - Gaming
        self.cases["caesars_2015"] = HistoricalCase(
            case_id="caesars_2015",
            company_name="Caesars Entertainment Operating Company",
            industry="gaming",
            filing_date="2015-01-15",
            resolution_date="2017-10-06",
            outcome=OutcomeType.REORGANIZATION,
            total_debt=18_400_000_000,
            enterprise_value_at_filing=10_000_000_000,
            enterprise_value_at_resolution=18_000_000_000,
            secured_debt=8_600_000_000,
            senior_unsecured_debt=5_200_000_000,
            subordinated_debt=4_600_000_000,
            trade_claims=0,
            secured_recovery=100,
            senior_unsecured_recovery=66,
            subordinated_recovery=9,
            equity_recovery=0,
            prices_at_filing={"secured": 92, "senior_unsecured": 45, "subordinated": 8},
            prices_at_resolution={"secured": 100, "senior_unsecured": 66, "subordinated": 9},
            days_in_bankruptcy=995,
            z_score_at_filing=0.72,
            ebitda_at_filing=1_500_000_000,
            leverage_at_filing=12.3,
        )
        
        # Sears Holdings (2018) - Retail
        self.cases["sears_2018"] = HistoricalCase(
            case_id="sears_2018",
            company_name="Sears Holdings Corporation",
            industry="retail",
            filing_date="2018-10-15",
            resolution_date="2020-02-07",
            outcome=OutcomeType.ACQUISITION,  # 363 sale to ESL
            total_debt=11_300_000_000,
            enterprise_value_at_filing=6_900_000_000,
            enterprise_value_at_resolution=5_200_000_000,
            secured_debt=5_200_000_000,
            senior_unsecured_debt=2_000_000_000,
            subordinated_debt=0,
            trade_claims=4_100_000_000,
            secured_recovery=90,
            senior_unsecured_recovery=3,
            subordinated_recovery=0,
            equity_recovery=0,
            trade_claims_recovery=3,
            prices_at_filing={"secured": 75, "senior_unsecured": 10, "equity": 0.41},
            prices_at_resolution={"secured": 90, "senior_unsecured": 3, "equity": 0},
            days_in_bankruptcy=480,
            z_score_at_filing=0.28,
            ebitda_at_filing=-500_000_000,
            leverage_at_filing=999,
        )
        
        # Washington Mutual (2008) - Bank Failure
        self.cases["wamu_2008"] = HistoricalCase(
            case_id="wamu_2008",
            company_name="Washington Mutual Inc",
            industry="financial_services",
            filing_date="2008-09-26",
            resolution_date="2012-02-24",
            outcome=OutcomeType.LIQUIDATION,
            total_debt=8_000_000_000,
            enterprise_value_at_filing=307_000_000_000,
            enterprise_value_at_resolution=7_000_000_000,
            secured_debt=0,
            senior_unsecured_debt=6_500_000_000,
            subordinated_debt=1_500_000_000,
            trade_claims=0,
            secured_recovery=0,
            senior_unsecured_recovery=85,  # Better than expected
            subordinated_recovery=36,
            equity_recovery=0,
            trade_claims_recovery=0,
            prices_at_filing={"senior_unsecured": 30, "subordinated": 10, "equity": 0.16},
            prices_at_resolution={"senior_unsecured": 85, "subordinated": 36, "equity": 0},
            days_in_bankruptcy=1247,
            z_score_at_filing=0.55,
        )
    
    def get_case(self, case_id: str) -> Optional[HistoricalCase]:
        """Get a specific case by ID."""
        return self.cases.get(case_id)
    
    def get_all_cases(self) -> List[HistoricalCase]:
        """Get all cases."""
        return list(self.cases.values())
    
    def get_cases_by_industry(self, industry: str) -> List[HistoricalCase]:
        """Get cases filtered by industry."""
        return [c for c in self.cases.values() if c.industry == industry]
    
    def get_cases_by_outcome(self, outcome: OutcomeType) -> List[HistoricalCase]:
        """Get cases filtered by outcome."""
        return [c for c in self.cases.values() if c.outcome == outcome]
    
    def get_cases_by_date_range(self, start: str, end: str) -> List[HistoricalCase]:
        """Get cases within a date range."""
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        return [
            c for c in self.cases.values()
            if start_dt <= datetime.fromisoformat(c.filing_date) <= end_dt
        ]
    
    def add_case(self, case: HistoricalCase):
        """Add a new case to the database."""
        self.cases[case.case_id] = case


@dataclass
class Strategy:
    """Trading strategy for backtesting."""
    name: str
    description: str
    
    # Entry criteria
    entry_signal: Callable[[HistoricalCase, Dict[str, Any]], Tuple[bool, str, float]]
    
    # Position sizing
    position_size_pct: float = 0.05  # 5% of portfolio per position
    max_positions: int = 10
    
    # Exit criteria
    target_return: float = 0.50  # 50% profit target
    stop_loss: float = -0.30     # 30% stop loss
    max_holding_days: int = 365
    
    # Security preferences
    allowed_classes: List[str] = field(default_factory=lambda: ["secured", "senior_unsecured", "subordinated"])
    
    # Risk parameters
    max_industry_exposure: float = 0.25
    max_single_position: float = 0.10


class BacktestEngine:
    """
    Engine for running backtests on distressed strategies.
    """
    
    def __init__(self, initial_capital: float = 10_000_000):
        self.initial_capital = initial_capital
        self.case_db = HistoricalCaseDatabase()
    
    def run_backtest(
        self,
        strategy: Strategy,
        start_date: str = "2001-01-01",
        end_date: str = "2023-12-31",
        cases: Optional[List[HistoricalCase]] = None
    ) -> BacktestResult:
        """
        Run a backtest on the given strategy.
        """
        if cases is None:
            cases = self.case_db.get_cases_by_date_range(start_date, end_date)
        
        # Sort cases by filing date
        cases = sorted(cases, key=lambda c: c.filing_date)
        
        result = BacktestResult(
            strategy_name=strategy.name,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Portfolio state
        capital = self.initial_capital
        positions: List[Trade] = []
        closed_trades: List[Trade] = []
        equity_curve = [{"date": start_date, "equity": capital}]
        
        # Process each case
        for case in cases:
            # Check for exits on existing positions
            for pos in positions[:]:
                exit_price, should_exit, exit_reason = self._check_exit(
                    pos, case, strategy
                )
                if should_exit:
                    pos.exit_date = case.filing_date
                    pos.exit_price = exit_price
                    pos.pnl = (exit_price - pos.entry_price) / 100 * pos.position_size
                    pos.pnl_pct = (exit_price - pos.entry_price) / pos.entry_price
                    pos.holding_days = (
                        datetime.fromisoformat(pos.exit_date) -
                        datetime.fromisoformat(pos.entry_date)
                    ).days
                    
                    capital += pos.pnl
                    closed_trades.append(pos)
                    positions.remove(pos)
            
            # Check for entry signal
            if len(positions) < strategy.max_positions:
                should_enter, security_class, signal_score = strategy.entry_signal(
                    case, {"capital": capital, "positions": positions}
                )
                
                if should_enter and security_class in strategy.allowed_classes:
                    entry_price = case.prices_at_filing.get(security_class, 50)
                    position_size = capital * strategy.position_size_pct
                    
                    trade = Trade(
                        trade_id=f"{case.case_id}_{security_class}_{len(closed_trades)}",
                        case_id=case.case_id,
                        security_class=security_class,
                        entry_date=case.filing_date,
                        entry_price=entry_price,
                        position_size=position_size,
                        signal_score=signal_score,
                        signal_reason=f"Signal on {case.company_name}",
                    )
                    positions.append(trade)
            
            # Update equity curve
            portfolio_value = capital + sum(p.position_size for p in positions)
            equity_curve.append({
                "date": case.filing_date,
                "equity": portfolio_value,
                "open_positions": len(positions),
            })
        
        # Close remaining positions at resolution prices
        for pos in positions:
            case = self.case_db.get_case(pos.case_id)
            if case:
                recovery_map = {
                    "secured": case.secured_recovery,
                    "senior_unsecured": case.senior_unsecured_recovery,
                    "subordinated": case.subordinated_recovery,
                    "equity": case.equity_recovery,
                }
                pos.exit_price = recovery_map.get(pos.security_class, 0)
                pos.exit_date = case.resolution_date
                pos.pnl = (pos.exit_price - pos.entry_price) / 100 * pos.position_size
                pos.pnl_pct = (pos.exit_price - pos.entry_price) / pos.entry_price if pos.entry_price > 0 else 0
                pos.holding_days = case.days_in_bankruptcy
                
                capital += pos.pnl
                closed_trades.append(pos)
        
        # Calculate metrics
        result.trades = closed_trades
        result.total_trades = len(closed_trades)
        result.equity_curve = equity_curve
        
        if closed_trades:
            result = self._calculate_metrics(result, closed_trades)
        
        return result
    
    def _check_exit(
        self,
        position: Trade,
        current_case: HistoricalCase,
        strategy: Strategy
    ) -> Tuple[float, bool, str]:
        """Check if position should be exited."""
        # Get case for this position
        pos_case = self.case_db.get_case(position.case_id)
        if not pos_case:
            return 0, False, ""
        
        # Check if case resolved
        if current_case.filing_date >= pos_case.resolution_date:
            recovery_map = {
                "secured": pos_case.secured_recovery,
                "senior_unsecured": pos_case.senior_unsecured_recovery,
                "subordinated": pos_case.subordinated_recovery,
                "equity": pos_case.equity_recovery,
            }
            exit_price = recovery_map.get(position.security_class, 0)
            return exit_price, True, "resolution"
        
        # Simulate intermediate price (random walk for now)
        days_elapsed = (
            datetime.fromisoformat(current_case.filing_date) -
            datetime.fromisoformat(position.entry_date)
        ).days
        
        if days_elapsed > strategy.max_holding_days:
            return position.entry_price * 0.9, True, "max_holding"
        
        return 0, False, ""
    
    def _calculate_metrics(
        self,
        result: BacktestResult,
        trades: List[Trade]
    ) -> BacktestResult:
        """Calculate performance metrics."""
        returns = [t.pnl_pct for t in trades]
        pnls = [t.pnl for t in trades]
        
        # Basic stats
        result.total_return = (result.equity_curve[-1]["equity"] - self.initial_capital) / self.initial_capital
        
        years = max(1, (
            datetime.fromisoformat(result.end_date) -
            datetime.fromisoformat(result.start_date)
        ).days / 365)
        result.annualized_return = (1 + result.total_return) ** (1 / years) - 1
        
        # Win/loss stats
        winning = [r for r in returns if r > 0]
        losing = [r for r in returns if r < 0]
        
        result.winning_trades = len(winning)
        result.losing_trades = len(losing)
        result.win_rate = len(winning) / len(returns) if returns else 0
        result.avg_win = sum(winning) / len(winning) if winning else 0
        result.avg_loss = sum(losing) / len(losing) if losing else 0
        
        # Profit factor
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Volatility and Sharpe
        if len(returns) > 1:
            avg_return = sum(returns) / len(returns)
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            result.volatility = math.sqrt(variance)
            result.sharpe_ratio = avg_return / result.volatility if result.volatility > 0 else 0
            
            # Sortino (downside deviation)
            downside_returns = [r for r in returns if r < 0]
            if downside_returns:
                downside_var = sum(r ** 2 for r in downside_returns) / len(downside_returns)
                downside_dev = math.sqrt(downside_var)
                result.sortino_ratio = avg_return / downside_dev if downside_dev > 0 else 0
        
        # Max drawdown from equity curve
        peak = self.initial_capital
        max_dd = 0
        for point in result.equity_curve:
            if point["equity"] > peak:
                peak = point["equity"]
            dd = (peak - point["equity"]) / peak
            max_dd = max(max_dd, dd)
        result.max_drawdown = max_dd
        
        # VaR (95%)
        sorted_returns = sorted(returns)
        var_index = int(0.05 * len(sorted_returns))
        result.var_95 = sorted_returns[var_index] if var_index < len(sorted_returns) else 0
        
        # Expected shortfall
        tail_returns = sorted_returns[:var_index + 1]
        result.expected_shortfall = sum(tail_returns) / len(tail_returns) if tail_returns else 0
        
        # Average holding period
        result.avg_holding_period = sum(t.holding_days for t in trades) / len(trades)
        
        # By security class
        for sec_class in ["secured", "senior_unsecured", "subordinated", "equity"]:
            class_trades = [t for t in trades if t.security_class == sec_class]
            if class_trades:
                result.trades_by_class[sec_class] = len(class_trades)
                result.returns_by_class[sec_class] = sum(t.pnl_pct for t in class_trades) / len(class_trades)
        
        return result
    
    def run_monte_carlo(
        self,
        strategy: Strategy,
        n_simulations: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation on strategy.
        Randomizes order of cases to assess robustness.
        """
        results = []
        cases = self.case_db.get_all_cases()
        
        for i in range(n_simulations):
            # Shuffle cases
            shuffled = cases.copy()
            random.shuffle(shuffled)
            
            result = self.run_backtest(strategy, cases=shuffled, **kwargs)
            results.append(result)
        
        # Aggregate results
        returns = [r.total_return for r in results]
        sharpes = [r.sharpe_ratio for r in results]
        drawdowns = [r.max_drawdown for r in results]
        
        return {
            "n_simulations": n_simulations,
            "return_mean": sum(returns) / len(returns),
            "return_std": math.sqrt(sum((r - sum(returns)/len(returns))**2 for r in returns) / len(returns)),
            "return_median": sorted(returns)[len(returns) // 2],
            "return_5th_pct": sorted(returns)[int(0.05 * len(returns))],
            "return_95th_pct": sorted(returns)[int(0.95 * len(returns))],
            "sharpe_mean": sum(sharpes) / len(sharpes),
            "max_drawdown_mean": sum(drawdowns) / len(drawdowns),
            "max_drawdown_worst": max(drawdowns),
            "win_rate_mean": sum(r.win_rate for r in results) / len(results),
        }


# Pre-built strategies
def fulcrum_hunter_signal(case: HistoricalCase, context: Dict[str, Any]) -> Tuple[bool, str, float]:
    """
    Strategy: Buy the fulcrum security.
    Targets securities where cumulative claims ≈ enterprise value.
    """
    ev = case.enterprise_value_at_filing
    
    cumulative = 0
    for sec_class, amount, recovery in [
        ("secured", case.secured_debt, case.secured_recovery),
        ("senior_unsecured", case.senior_unsecured_debt, case.senior_unsecured_recovery),
        ("subordinated", case.subordinated_debt, case.subordinated_recovery),
    ]:
        cumulative += amount
        if cumulative >= ev * 0.8 and cumulative <= ev * 1.2:
            # This is approximately the fulcrum
            entry_price = case.prices_at_filing.get(sec_class, 50)
            expected_recovery = recovery
            signal_score = (expected_recovery - entry_price) / entry_price if entry_price > 0 else 0
            
            if signal_score > 0.20:  # 20% expected upside
                return True, sec_class, signal_score
    
    return False, "", 0


def deep_value_signal(case: HistoricalCase, context: Dict[str, Any]) -> Tuple[bool, str, float]:
    """
    Strategy: Buy deeply discounted senior unsecured bonds.
    Targets bonds trading < 40 cents with reasonable coverage.
    """
    entry_price = case.prices_at_filing.get("senior_unsecured", 100)
    
    if entry_price < 40:
        # Check if assets cover senior
        coverage = case.enterprise_value_at_filing / (case.secured_debt + case.senior_unsecured_debt)
        
        if coverage > 0.5:  # At least 50% coverage
            signal_score = (case.senior_unsecured_recovery - entry_price) / entry_price if entry_price > 0 else 0
            if signal_score > 0:
                return True, "senior_unsecured", signal_score
    
    return False, "", 0


def z_score_signal(case: HistoricalCase, context: Dict[str, Any]) -> Tuple[bool, str, float]:
    """
    Strategy: Buy based on Altman Z-Score.
    Contrary: Low Z-Score with cheap bonds = opportunity.
    """
    if case.z_score_at_filing is None:
        return False, "", 0
    
    z = case.z_score_at_filing
    entry_price = case.prices_at_filing.get("senior_unsecured", 100)
    
    # Very distressed but not quite dead
    if 0.3 < z < 1.5 and entry_price < 50:
        signal_score = (100 - entry_price) / 100 * (1 / z)  # Lower Z = higher signal
        return True, "senior_unsecured", min(signal_score, 2.0)
    
    return False, "", 0


# Convenience functions
def create_fulcrum_strategy() -> Strategy:
    return Strategy(
        name="Fulcrum Hunter",
        description="Buy securities at the fulcrum of the capital structure",
        entry_signal=fulcrum_hunter_signal,
        position_size_pct=0.05,
        target_return=0.50,
        stop_loss=-0.40,
    )


def create_deep_value_strategy() -> Strategy:
    return Strategy(
        name="Deep Value",
        description="Buy deeply discounted senior bonds with asset coverage",
        entry_signal=deep_value_signal,
        position_size_pct=0.03,
        target_return=1.00,  # Target double
        stop_loss=-0.50,
    )


def create_z_score_strategy() -> Strategy:
    return Strategy(
        name="Z-Score Contrarian",
        description="Buy cheap bonds in low Z-Score companies",
        entry_signal=z_score_signal,
        position_size_pct=0.04,
        target_return=0.75,
        stop_loss=-0.35,
    )
