"""
Distressed Platform Routes
==========================
Flask routes for distressed investing dashboard.
Integrates portfolio management, backtesting, and data feeds.
"""

import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify
from dataclasses import asdict

from portfolio.portfolio_manager import (
    PortfolioManager, RiskLimits, SecurityType, PositionStatus
)
from backtesting.backtest_engine import (
    BacktestEngine, HistoricalCaseDatabase, create_fulcrum_strategy, create_deep_value_strategy, create_z_score_strategy
)
from data_feeds.feed_manager import FeedManager, DataSourceType

logger = logging.getLogger(__name__)

distressed_platform_bp = Blueprint('distressed_platform', __name__, url_prefix='/distressed')

portfolio_manager = PortfolioManager()
backtest_engine = BacktestEngine()
case_db = HistoricalCaseDatabase()
feed_manager = FeedManager()

default_portfolio = portfolio_manager.create_portfolio(
    "main",
    initial_capital=10_000_000,
    risk_limits=RiskLimits()
)


@distressed_platform_bp.route('/')
def distressed_dashboard():
    """Main distressed investing dashboard."""
    return render_template('distressed_dashboard.html')


@distressed_platform_bp.route('/api/portfolio/summary')
def get_portfolio_summary():
    """Get portfolio summary."""
    portfolio_id = request.args.get('portfolio_id', 'main')
    portfolio = portfolio_manager.get_portfolio(portfolio_id)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    
    snapshot = portfolio.take_snapshot()
    return jsonify({
        "portfolio_id": portfolio_id,
        "nav": snapshot.nav,
        "cash": snapshot.cash,
        "invested": snapshot.gross_exposure,
        "total_pnl": snapshot.total_pnl,
        "total_pnl_pct": snapshot.daily_return,
        "position_count": len(portfolio.positions),
        "timestamp": snapshot.timestamp,
        "exposure_by_status": snapshot.exposure_by_status,
        "exposure_by_industry": snapshot.exposure_by_sector,
        "exposure_by_seniority": snapshot.exposure_by_seniority,
        "risk_alerts": []
    })


@distressed_platform_bp.route('/api/portfolio/positions')
def get_positions():
    """Get all positions."""
    portfolio_id = request.args.get('portfolio_id', 'main')
    status_filter = request.args.get('status', None)
    
    portfolio = portfolio_manager.get_portfolio(portfolio_id)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    
    positions = list(portfolio.positions.values())
    
    if status_filter:
        try:
            status = PositionStatus(status_filter)
            positions = [p for p in positions if p.status == status]
        except ValueError:
            pass
    
    return jsonify({
        "portfolio_id": portfolio_id,
        "positions": [asdict(p) for p in positions],
        "count": len(positions)
    })


@distressed_platform_bp.route('/api/portfolio/positions', methods=['POST'])
def add_position():
    """Add a new position."""
    portfolio_id = request.args.get('portfolio_id', 'main')
    data = request.get_json()
    
    portfolio = portfolio_manager.get_portfolio(portfolio_id)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    
    try:
        security_type = SecurityType(data.get('security_type', 'senior_unsecured'))
    except ValueError:
        security_type = SecurityType.SENIOR_UNSECURED
    
    position = portfolio.add_position(
        company_name=data.get('company_name', 'Unknown'),
        company_id=data.get('company_id', f"comp-{datetime.utcnow().timestamp()}"),
        security_type=security_type,
        security_id=data.get('security_id', f"sec-{datetime.utcnow().timestamp()}"),
        face_amount=float(data.get('face_amount', 0)),
        entry_price=float(data.get('entry_price', 0)),
        industry=data.get('industry', ''),
        case_status=data.get('case_status', 'performing'),
        coupon_rate=float(data.get('coupon_rate', 0)),
        recovery_estimate=float(data.get('recovery_estimate', 50)),
        notes=data.get('notes', '')
    )
    
    return jsonify({"success": True, "position": asdict(position)})


@distressed_platform_bp.route('/api/portfolio/risk')
def get_risk_metrics():
    """Get portfolio risk metrics."""
    portfolio_id = request.args.get('portfolio_id', 'main')
    
    portfolio = portfolio_manager.get_portfolio(portfolio_id)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    
    metrics = portfolio.calculate_risk_metrics()
    return jsonify(metrics)


@distressed_platform_bp.route('/api/portfolio/stress-test', methods=['POST'])
def run_stress_test():
    """Run stress test on portfolio."""
    portfolio_id = request.args.get('portfolio_id', 'main')
    data = request.get_json() or {}
    
    portfolio = portfolio_manager.get_portfolio(portfolio_id)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    
    scenarios = data.get('scenarios', [
        {"name": "Credit Crisis", "price_shock": -0.30, "description": "30% price decline across all positions"},
        {"name": "Sector Selloff", "sector": "energy", "price_shock": -0.50, "description": "50% decline in energy sector"},
        {"name": "Recovery Rally", "price_shock": 0.20, "description": "20% price increase across all positions"}
    ])
    
    results = portfolio.stress_test(scenarios)
    return jsonify({"scenarios": results})


@distressed_platform_bp.route('/api/backtest/strategies')
def get_strategies():
    """Get available backtest strategies."""
    strategies = [
        {
            "name": "fulcrum_hunter",
            "description": "Buy fulcrum securities trading below recovery value",
            "parameters": {"min_discount": 0.20, "max_leverage": 6.0}
        },
        {
            "name": "deep_value",
            "description": "Buy deeply discounted secured debt with high recovery",
            "parameters": {"max_price": 40, "min_recovery": 80}
        },
        {
            "name": "z_score_distress",
            "description": "Trade based on Altman Z-Score signals",
            "parameters": {"z_threshold": 1.8, "entry_price_max": 70}
        }
    ]
    return jsonify({"strategies": strategies})


@distressed_platform_bp.route('/api/backtest/cases')
def get_historical_cases():
    """Get historical bankruptcy cases."""
    industry = request.args.get('industry', None)
    outcome = request.args.get('outcome', None)
    limit = int(request.args.get('limit', 50))
    
    cases = case_db.get_all_cases()
    
    if industry:
        cases = [c for c in cases if c.industry.lower() == industry.lower()]
    if outcome:
        cases = [c for c in cases if c.outcome.value == outcome]
    
    cases = cases[:limit]
    
    def serialize_case(c):
        d = asdict(c)
        if 'outcome' in d and hasattr(c.outcome, 'value'):
            d['outcome'] = c.outcome.value
        return d
    
    all_cases = case_db.get_all_cases()
    return jsonify({
        "cases": [serialize_case(c) for c in cases],
        "count": len(cases),
        "industries": list(set(c.industry for c in all_cases)),
        "outcomes": ["reorganization", "liquidation", "acquisition", "out_of_court", "conversion"]
    })


@distressed_platform_bp.route('/api/backtest/run', methods=['POST'])
def run_backtest():
    """Run a backtest."""
    data = request.get_json()
    
    strategy_name = data.get('strategy_name', 'fulcrum_hunter')
    start_date = data.get('start_date', '2001-01-01')
    end_date = data.get('end_date', '2023-12-31')
    initial_capital = float(data.get('initial_capital', 10_000_000))
    
    if strategy_name == 'fulcrum_hunter':
        strategy = create_fulcrum_strategy()
    elif strategy_name == 'deep_value':
        strategy = create_deep_value_strategy()
    elif strategy_name == 'z_score_distress':
        strategy = create_z_score_strategy()
    else:
        return jsonify({"error": f"Unknown strategy: {strategy_name}"}), 400
    
    result = backtest_engine.run_backtest(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital
    )
    
    return jsonify({
        "success": True,
        "result": asdict(result)
    })


@distressed_platform_bp.route('/api/backtest/monte-carlo', methods=['POST'])
def run_monte_carlo():
    """Run Monte Carlo simulation."""
    data = request.get_json()
    
    strategy_name = data.get('strategy_name', 'fulcrum_hunter')
    n_simulations = int(data.get('n_simulations', 1000))
    
    if strategy_name == 'fulcrum_hunter':
        strategy = create_fulcrum_strategy()
    elif strategy_name == 'deep_value':
        strategy = create_deep_value_strategy()
    elif strategy_name == 'z_score_distress':
        strategy = create_z_score_strategy()
    else:
        return jsonify({"error": f"Unknown strategy: {strategy_name}"}), 400
    
    result = backtest_engine.monte_carlo_simulation(
        strategy=strategy,
        n_simulations=n_simulations
    )
    
    return jsonify({
        "success": True,
        "result": result
    })


@distressed_platform_bp.route('/api/feeds/status')
def get_feed_status():
    """Get data feed status."""
    status = feed_manager.get_status()
    return jsonify(status)


@distressed_platform_bp.route('/api/feeds/sources')
def get_data_sources():
    """Get available data sources."""
    sources = [
        {"type": "pacer", "name": "PACER", "description": "US Bankruptcy Court filings"},
        {"type": "bloomberg", "name": "Bloomberg", "description": "Bond prices and analytics"},
        {"type": "trace", "name": "TRACE", "description": "Corporate bond transactions"},
        {"type": "sec", "name": "SEC EDGAR", "description": "SEC filings and 10-K/10-Q"},
        {"type": "moody", "name": "Moody's", "description": "Credit ratings and research"}
    ]
    return jsonify({"sources": sources})


@distressed_platform_bp.route('/api/feeds/refresh', methods=['POST'])
def refresh_feeds():
    """Refresh data feeds."""
    data = request.get_json() or {}
    source_type = data.get('source_type', None)
    
    try:
        if source_type:
            feed_manager.refresh_source(DataSourceType(source_type))
        else:
            feed_manager.refresh_all()
        return jsonify({"success": True, "message": "Feeds refreshed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@distressed_platform_bp.route('/api/alerts')
def get_alerts():
    """Get portfolio alerts."""
    portfolio_id = request.args.get('portfolio_id', 'main')
    
    portfolio = portfolio_manager.get_portfolio(portfolio_id)
    if not portfolio:
        return jsonify({"error": "Portfolio not found"}), 404
    
    alerts = portfolio.get_risk_alerts()
    return jsonify({
        "alerts": [asdict(a) for a in alerts],
        "count": len(alerts)
    })
