#!/usr/bin/env python3
"""
Distressed Investing Platform - Main Runner
============================================
Demonstrates all components working together:
- Data Feeds
- Portfolio Management
- Backtesting
- Dashboard API

Usage:
    python run_platform.py [command]

Commands:
    demo        Run demo with sample data
    backtest    Run backtesting on historical cases
    api         Start the dashboard API server
    all         Run complete demo

Examples:
    python run_platform.py demo
    python run_platform.py backtest
    python run_platform.py api
"""

import os
import sys
import json
import argparse
from datetime import datetime
from dataclasses import asdict

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from portfolio.portfolio_manager import (
    Portfolio, PortfolioManager, Position, RiskLimits,
    SecurityType, PositionStatus
)
from backtesting.backtest_engine import (
    BacktestEngine, 
    create_fulcrum_strategy, 
    create_deep_value_strategy, 
    create_z_score_strategy
)
from data_feeds.feed_manager import FeedManager, DataSourceType


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def print_table(headers: list, rows: list, widths: list = None):
    """Print a simple ASCII table."""
    if not widths:
        widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 for i in range(len(headers))]
    
    # Header
    header_row = "|".join(str(h).center(w) for h, w in zip(headers, widths))
    separator = "+".join("-" * w for w in widths)
    print(f"+{separator}+")
    print(f"|{header_row}|")
    print(f"+{separator}+")
    
    # Rows
    for row in rows:
        row_str = "|".join(str(cell).center(w) for cell, w in zip(row, widths))
        print(f"|{row_str}|")
    print(f"+{separator}+")


def run_demo():
    """Run a complete demo with sample data."""
    print_header("DISTRESSED INVESTING PLATFORM DEMO")
    
    # 1. Create Portfolio
    print("1. Creating Portfolio...")
    pm = PortfolioManager()
    portfolio = pm.create_portfolio(
        "demo_portfolio",
        initial_capital=10_000_000,
        risk_limits=RiskLimits(
            max_single_position_pct=0.15,
            max_sector_exposure_pct=0.30,
            max_bankruptcy_pct=0.60
        )
    )
    print(f"   ✓ Created portfolio with ${portfolio.initial_capital:,.0f} capital")
    
    # 2. Add Sample Positions
    print("\n2. Adding Sample Positions...")
    
    positions_data = [
        {
            "company_name": "Hertz Global",
            "company_id": "hertz",
            "security_type": SecurityType.SENIOR_UNSECURED,
            "security_id": "HTZ_5.5_2024",
            "face_amount": 2_000_000,
            "entry_price": 40,
            "industry": "transportation",
            "case_status": "bankruptcy",
            "recovery_estimate": 100,
        },
        {
            "company_name": "J.Crew Group",
            "company_id": "jcrew",
            "security_type": SecurityType.SECURED_BOND,
            "security_id": "JCRW_SEC_2021",
            "face_amount": 1_500_000,
            "entry_price": 55,
            "industry": "retail",
            "case_status": "bankruptcy",
            "recovery_estimate": 82,
        },
        {
            "company_name": "Caesars Entertainment",
            "company_id": "caesars",
            "security_type": SecurityType.SUBORDINATED,
            "security_id": "CZR_SUB_2025",
            "face_amount": 1_000_000,
            "entry_price": 8,
            "industry": "gaming",
            "case_status": "distressed",
            "recovery_estimate": 9,
        },
        {
            "company_name": "PG&E Corporation",
            "company_id": "pge",
            "security_type": SecurityType.SENIOR_UNSECURED,
            "security_id": "PCG_6.0_2028",
            "face_amount": 2_500_000,
            "entry_price": 93,
            "industry": "utilities",
            "case_status": "bankruptcy",
            "recovery_estimate": 100,
        },
    ]
    
    for i, pos_data in enumerate(positions_data):
        pos = Position(
            position_id=f"pos_{i+1}",
            entry_date=datetime.now().isoformat(),
            **pos_data
        )
        success, msg = portfolio.add_position(pos)
        print(f"   {'✓' if success else '✗'} {pos_data['company_name']}: {msg}")
    
    # 3. Update Marks (simulate price changes)
    print("\n3. Updating Market Prices...")
    price_updates = {
        "HTZ_5.5_2024": 65,      # +25 pts
        "JCRW_SEC_2021": 82,     # +27 pts
        "CZR_SUB_2025": 9,       # +1 pt
        "PCG_6.0_2028": 100,     # +7 pts
    }
    portfolio.update_marks(price_updates)
    print("   ✓ Prices updated")
    
    # 4. Take Snapshot & Show Summary
    print("\n4. Portfolio Summary:")
    snapshot = portfolio.take_snapshot()
    
    print(f"""
   NAV:              ${snapshot.nav:,.0f}
   Cash:             ${snapshot.cash:,.0f}
   Gross Exposure:   ${snapshot.gross_exposure:,.0f}
   Positions:        {snapshot.position_count}
   Issuers:          {snapshot.issuer_count}
   
   P&L:
   - Total:          ${snapshot.total_pnl:,.0f}
   - Unrealized:     ${snapshot.unrealized_pnl:,.0f}
   
   Risk:
   - VaR (95%):      {snapshot.var_95*100:.2f}%
   - Avg Recovery:   {snapshot.avg_recovery_estimate:.1f}%
""")
    
    # 5. Positions Table
    print("5. Position Details:")
    headers = ["Company", "Type", "Face", "Entry", "Current", "P&L", "P&L %"]
    rows = []
    for pos in portfolio.get_position_summary():
        rows.append([
            pos["company"][:15],
            pos["security_type"][:12],
            f"${pos['face_amount']/1e6:.1f}M",
            f"{pos['entry_price']:.0f}",
            f"{pos['current_price']:.0f}",
            f"${pos['unrealized_pnl']/1e3:.0f}K",
            f"{pos['pnl_pct']:.1f}%"
        ])
    print_table(headers, rows)
    
    # 6. Check Risk Limits
    print("\n6. Risk Limit Check:")
    alerts = portfolio.check_all_limits()
    if alerts:
        for alert in alerts:
            print(f"   ⚠ [{alert.severity.upper()}] {alert.message}")
    else:
        print("   ✓ All risk limits within bounds")
    
    # 7. Exposure Breakdown
    print("\n7. Exposure by Sector:")
    exposure = portfolio.get_exposure_report()
    for sector, data in exposure.get("by_sector", {}).items():
        print(f"   {sector}: ${data['value']:,.0f} ({data['pct']:.1f}%)")
    
    # 8. Stress Test
    print("\n8. Stress Test Results:")
    scenarios = portfolio.get_default_stress_scenarios()
    stress_results = portfolio.run_stress_test(scenarios)
    
    headers = ["Scenario", "P&L Impact", "% Impact", "NAV After"]
    rows = []
    for result in stress_results:
        rows.append([
            result["scenario"][:25],
            f"${result['pnl']/1e3:,.0f}K",
            f"{result['pnl_pct']:.1f}%",
            f"${result['nav_after']/1e6:.1f}M"
        ])
    print_table(headers, rows)
    
    print("\n" + "=" * 60)
    print("  Demo Complete!")
    print("=" * 60 + "\n")


def run_backtest():
    """Run backtesting on historical cases."""
    print_header("BACKTESTING HISTORICAL BANKRUPTCIES")
    
    engine = BacktestEngine(initial_capital=10_000_000)
    
    # List cases
    print("Historical Cases in Database:")
    cases = engine.case_db.get_all_cases()
    
    headers = ["Case", "Industry", "Filing", "Outcome", "Sr Recovery"]
    rows = []
    for case in cases:
        rows.append([
            case.company_name[:20],
            case.industry[:12],
            case.filing_date[:10],
            case.outcome.value[:12],
            f"{case.senior_unsecured_recovery}%"
        ])
    print_table(headers, rows)
    
    # Run each strategy
    strategies = [
        ("Fulcrum Hunter", create_fulcrum_strategy()),
        ("Deep Value", create_deep_value_strategy()),
        ("Z-Score Contrarian", create_z_score_strategy()),
    ]
    
    print("\nStrategy Backtest Results (2001-2023):")
    print("-" * 80)
    
    results_rows = []
    for name, strategy in strategies:
        result = engine.run_backtest(strategy, start_date="2001-01-01", end_date="2023-12-31")
        results_rows.append([
            name,
            f"{result.total_return*100:.1f}%",
            f"{result.annualized_return*100:.1f}%",
            f"{result.sharpe_ratio:.2f}",
            f"{result.win_rate*100:.1f}%",
            f"{result.max_drawdown*100:.1f}%",
            str(result.total_trades)
        ])
    
    headers = ["Strategy", "Total Ret", "Ann. Ret", "Sharpe", "Win Rate", "Max DD", "Trades"]
    print_table(headers, results_rows)
    
    # Monte Carlo on best strategy
    print("\nMonte Carlo Simulation (Fulcrum Hunter, 100 runs):")
    mc_results = engine.run_monte_carlo(create_fulcrum_strategy(), n_simulations=100)
    
    print(f"""
   Return (Mean):     {mc_results['return_mean']*100:.1f}%
   Return (Std Dev):  {mc_results['return_std']*100:.1f}%
   Return (5th %):    {mc_results['return_5th_pct']*100:.1f}%
   Return (95th %):   {mc_results['return_95th_pct']*100:.1f}%
   Sharpe (Mean):     {mc_results['sharpe_mean']:.2f}
   Max DD (Worst):    {mc_results['max_drawdown_worst']*100:.1f}%
""")
    
    print("=" * 60)
    print("  Backtest Complete!")
    print("=" * 60 + "\n")


def run_api():
    """Start the dashboard API server."""
    print_header("STARTING DASHBOARD API SERVER")
    
    try:
        import uvicorn
        from dashboard.api import app
        
        print("""
   Dashboard API starting on http://localhost:8000
   
   Endpoints:
   - GET  /api/portfolio/summary    - Portfolio summary
   - GET  /api/portfolio/positions  - All positions
   - POST /api/portfolio/positions  - Add position
   - GET  /api/portfolio/exposure   - Exposure breakdown
   - GET  /api/portfolio/risk       - Risk metrics
   - POST /api/portfolio/stress-test - Run stress test
   - GET  /api/alerts               - Risk alerts
   - GET  /api/backtest/strategies  - List strategies
   - POST /api/backtest/run         - Run backtest
   - GET  /api/backtest/cases       - Historical cases
   
   Open http://localhost:8000/docs for API documentation
   
   Press Ctrl+C to stop.
""")
        uvicorn.run(app, host="0.0.0.0", port=8000)
        
    except ImportError:
        print("   ⚠ FastAPI/Uvicorn not installed.")
        print("   Install with: pip install fastapi uvicorn")
        print("\n   Running simple HTTP server instead...")
        
        from dashboard.api import create_simple_server
        server = create_simple_server()
        print("   Server running on http://localhost:8000")
        server.serve_forever()


def run_data_feeds_demo():
    """Demonstrate data feeds (will use mock data without API keys)."""
    print_header("DATA FEEDS DEMO")
    
    fm = FeedManager()
    
    print("Registered Feeds:")
    for feed in fm.list_feeds():
        status = "✓" if feed["enabled"] else "✗"
        print(f"   {status} {feed['name']} ({feed['source_type']})")
    
    print("\n   Note: Configure API keys in environment variables for live data:")
    print("   - DEBTWIRE_API_KEY")
    print("   - BLOOMBERG_API_KEY")
    print("   - PACER_API_KEY")
    print("   - NEWS_API_KEY")


def main():
    parser = argparse.ArgumentParser(
        description="Distressed Investing Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_platform.py demo        Run portfolio demo
  python run_platform.py backtest    Run backtesting
  python run_platform.py api         Start API server
  python run_platform.py all         Run all demos
        """
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        default="demo",
        choices=["demo", "backtest", "api", "feeds", "all"],
        help="Command to run (default: demo)"
    )
    
    args = parser.parse_args()
    
    if args.command == "demo":
        run_demo()
    elif args.command == "backtest":
        run_backtest()
    elif args.command == "api":
        run_api()
    elif args.command == "feeds":
        run_data_feeds_demo()
    elif args.command == "all":
        run_demo()
        run_backtest()
        run_data_feeds_demo()
        print("\nTo start the API server, run: python run_platform.py api")


if __name__ == "__main__":
    main()
