"""
Distressed Investing Dashboard API
==================================
FastAPI backend for the distressed investing dashboard.

Endpoints:
- Portfolio management
- Deal pipeline
- Risk monitoring
- Alerts
- Backtesting
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import asdict

# FastAPI imports (with fallback for when not installed)
try:
    from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Stub for type hints
    class BaseModel:
        pass

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio.portfolio_manager import (
    Portfolio, PortfolioManager, Position, RiskLimits,
    SecurityType, PositionStatus, RiskAlert
)
from backtesting.backtest_engine import (
    BacktestEngine, Strategy, BacktestResult,
    create_fulcrum_strategy, create_deep_value_strategy, create_z_score_strategy
)
from data_feeds.feed_manager import FeedManager, DataSourceType

logger = logging.getLogger(__name__)

# Initialize components
portfolio_manager = PortfolioManager()
backtest_engine = BacktestEngine()
feed_manager = FeedManager()

# Create default portfolio
default_portfolio = portfolio_manager.create_portfolio(
    "main",
    initial_capital=10_000_000,
    risk_limits=RiskLimits()
)

if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Distressed Investing Dashboard",
        description="API for distressed debt portfolio management and analysis",
        version="1.0.0"
    )
    
    # CORS for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # === Pydantic Models ===
    
    class PositionCreate(BaseModel):
        company_name: str
        company_id: str
        security_type: str
        security_id: str
        face_amount: float
        entry_price: float
        industry: str = ""
        case_status: str = "performing"
        coupon_rate: float = 0
        recovery_estimate: float = 50
        notes: str = ""
    
    class PositionClose(BaseModel):
        exit_price: float
        exit_date: Optional[str] = None
    
    class PriceUpdate(BaseModel):
        prices: Dict[str, float]  # security_id -> price
    
    class BacktestRequest(BaseModel):
        strategy_name: str
        start_date: str = "2001-01-01"
        end_date: str = "2023-12-31"
        initial_capital: float = 10_000_000
    
    class StressTestRequest(BaseModel):
        scenarios: Optional[List[Dict[str, Any]]] = None
    
    # === Health Check ===
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    
    # === Portfolio Endpoints ===
    
    @app.get("/portfolio/summary")
    async def get_portfolio_summary(portfolio_id: str = "main"):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        snapshot = portfolio.take_snapshot()
        return {
            "portfolio_id": portfolio_id,
            "nav": snapshot.nav,
            "cash": snapshot.cash,
            "gross_exposure": snapshot.gross_exposure,
            "position_count": snapshot.position_count,
            "issuer_count": snapshot.issuer_count,
            "total_pnl": snapshot.total_pnl,
            "daily_pnl": snapshot.daily_pnl,
            "daily_return": snapshot.daily_return * 100,
            "var_95": snapshot.var_95 * 100,
            "timestamp": snapshot.timestamp,
        }
    
    @app.get("/portfolio/positions")
    async def get_positions(portfolio_id: str = "main"):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        return {"positions": portfolio.get_position_summary()}
    
    @app.post("/portfolio/positions")
    async def add_position(position: PositionCreate, portfolio_id: str = "main"):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        try:
            security_type = SecurityType(position.security_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid security type: {position.security_type}")
        
        new_position = Position(
            position_id=f"pos_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            company_name=position.company_name,
            company_id=position.company_id,
            security_type=security_type,
            security_id=position.security_id,
            face_amount=position.face_amount,
            entry_price=position.entry_price,
            entry_date=datetime.utcnow().isoformat(),
            industry=position.industry,
            case_status=position.case_status,
            coupon_rate=position.coupon_rate,
            recovery_estimate=position.recovery_estimate,
            notes=position.notes,
        )
        
        success, message = portfolio.add_position(new_position)
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"success": True, "position_id": new_position.position_id, "message": message}
    
    @app.delete("/portfolio/positions/{position_id}")
    async def close_position(position_id: str, close_data: PositionClose, portfolio_id: str = "main"):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        success, message, pnl = portfolio.close_position(
            position_id, 
            close_data.exit_price,
            close_data.exit_date
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        return {"success": True, "realized_pnl": pnl, "message": message}
    
    @app.post("/portfolio/update-marks")
    async def update_marks(price_update: PriceUpdate, portfolio_id: str = "main"):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        portfolio.update_marks(price_update.prices)
        return {"success": True, "updated_count": len(price_update.prices)}
    
    # === Exposure & Risk Endpoints ===
    
    @app.get("/portfolio/exposure")
    async def get_exposure(portfolio_id: str = "main"):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        return portfolio.get_exposure_report()
    
    @app.get("/portfolio/risk")
    async def get_risk_metrics(portfolio_id: str = "main"):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        return portfolio.get_risk_report()
    
    @app.post("/portfolio/stress-test")
    async def run_stress_test(request: StressTestRequest, portfolio_id: str = "main"):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        scenarios = request.scenarios or portfolio.get_default_stress_scenarios()
        results = portfolio.run_stress_test(scenarios)
        
        return {"scenarios": results}
    
    # === Alerts Endpoints ===
    
    @app.get("/alerts")
    async def get_alerts(portfolio_id: str = "main", acknowledged: Optional[bool] = None):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        # Check for new alerts
        new_alerts = portfolio.check_all_limits()
        
        alerts = portfolio.alerts
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        
        return {
            "alerts": [asdict(a) for a in alerts],
            "new_alerts": len(new_alerts),
        }
    
    @app.post("/alerts/{alert_id}/acknowledge")
    async def acknowledge_alert(alert_id: str, portfolio_id: str = "main"):
        portfolio = portfolio_manager.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        for alert in portfolio.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return {"success": True}
        
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # === Deal Pipeline Endpoints ===
    
    @app.get("/deals")
    async def get_deals(
        status: Optional[str] = None,
        sector: Optional[str] = None,
        min_debt: Optional[float] = None
    ):
        """Get active distressed deals from data feeds."""
        deals = feed_manager.fetch_deals(
            status=status,
            sector=sector,
            min_debt=min_debt
        )
        
        return {
            "deals": [asdict(d) for d in deals],
            "count": len(deals),
        }
    
    @app.get("/deals/{company_name}")
    async def get_company_data(company_name: str, ticker: Optional[str] = None):
        """Get aggregated data for a company."""
        data = feed_manager.aggregate_company_data(company_name, ticker)
        return data
    
    @app.get("/filings")
    async def get_filings(
        case_number: Optional[str] = None,
        court: str = "deb",
        days: int = 30
    ):
        """Get recent court filings."""
        date_from = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        filings = feed_manager.fetch_filings(
            case_number=case_number,
            court=court,
            date_from=date_from
        )
        
        return {
            "filings": [asdict(f) for f in filings],
            "count": len(filings),
        }
    
    @app.get("/news")
    async def get_news(company: str, days: int = 7):
        """Get recent news for a company."""
        date_from = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        news = feed_manager.fetch_news(
            company=company,
            date_from=date_from
        )
        
        return {
            "articles": [asdict(n) for n in news],
            "count": len(news),
        }
    
    @app.get("/claims")
    async def get_trade_claims(debtor: Optional[str] = None, min_amount: Optional[float] = None):
        """Get available trade claims."""
        claims = feed_manager.fetch_claims(
            debtor=debtor,
            min_amount=min_amount
        )
        
        return {
            "claims": [asdict(c) for c in claims],
            "count": len(claims),
        }
    
    # === Backtesting Endpoints ===
    
    @app.get("/backtest/strategies")
    async def list_strategies():
        """List available backtest strategies."""
        return {
            "strategies": [
                {
                    "name": "fulcrum_hunter",
                    "description": "Buy securities at the fulcrum of the capital structure",
                },
                {
                    "name": "deep_value", 
                    "description": "Buy deeply discounted senior bonds with asset coverage",
                },
                {
                    "name": "z_score_contrarian",
                    "description": "Buy cheap bonds in low Z-Score companies",
                },
            ]
        }
    
    @app.post("/backtest/run")
    async def run_backtest(request: BacktestRequest):
        """Run a backtest on a strategy."""
        strategy_map = {
            "fulcrum_hunter": create_fulcrum_strategy(),
            "deep_value": create_deep_value_strategy(),
            "z_score_contrarian": create_z_score_strategy(),
        }
        
        strategy = strategy_map.get(request.strategy_name)
        if not strategy:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {request.strategy_name}")
        
        engine = BacktestEngine(initial_capital=request.initial_capital)
        result = engine.run_backtest(
            strategy,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        return {
            "strategy": result.strategy_name,
            "total_return": result.total_return * 100,
            "annualized_return": result.annualized_return * 100,
            "sharpe_ratio": result.sharpe_ratio,
            "sortino_ratio": result.sortino_ratio,
            "max_drawdown": result.max_drawdown * 100,
            "win_rate": result.win_rate * 100,
            "profit_factor": result.profit_factor,
            "total_trades": result.total_trades,
            "avg_holding_period": result.avg_holding_period,
            "var_95": result.var_95 * 100,
            "returns_by_class": result.returns_by_class,
            "equity_curve": result.equity_curve[:100],  # Limit for response size
        }
    
    @app.post("/backtest/monte-carlo")
    async def run_monte_carlo(request: BacktestRequest, n_simulations: int = 100):
        """Run Monte Carlo simulation on a strategy."""
        strategy_map = {
            "fulcrum_hunter": create_fulcrum_strategy(),
            "deep_value": create_deep_value_strategy(),
            "z_score_contrarian": create_z_score_strategy(),
        }
        
        strategy = strategy_map.get(request.strategy_name)
        if not strategy:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {request.strategy_name}")
        
        engine = BacktestEngine(initial_capital=request.initial_capital)
        results = engine.run_monte_carlo(strategy, n_simulations=n_simulations)
        
        return results
    
    @app.get("/backtest/cases")
    async def list_historical_cases():
        """List historical bankruptcy cases."""
        cases = backtest_engine.case_db.get_all_cases()
        
        return {
            "cases": [
                {
                    "case_id": c.case_id,
                    "company": c.company_name,
                    "industry": c.industry,
                    "filing_date": c.filing_date,
                    "outcome": c.outcome.value,
                    "total_debt": c.total_debt,
                    "senior_recovery": c.senior_unsecured_recovery,
                    "subordinated_recovery": c.subordinated_recovery,
                    "days_in_bankruptcy": c.days_in_bankruptcy,
                }
                for c in cases
            ],
            "count": len(cases),
        }
    
    # === Data Feed Status ===
    
    @app.get("/feeds/status")
    async def get_feed_status():
        """Get status of all data feeds."""
        return {
            "feeds": feed_manager.list_feeds(),
        }


# Fallback for when FastAPI not installed
def create_simple_server():
    """Create a simple HTTP server fallback."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    
    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                "message": "Distressed Investing Dashboard API",
                "status": "running",
                "note": "Install FastAPI for full functionality: pip install fastapi uvicorn"
            }
            self.wfile.write(json.dumps(response).encode())
    
    return HTTPServer(('localhost', 8000), SimpleHandler)


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("FastAPI not installed. Running simple fallback server...")
        print("Install with: pip install fastapi uvicorn")
        server = create_simple_server()
        print("Server running on http://localhost:8000")
        server.serve_forever()

# === Serve Dashboard HTML ===
from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard not found. Check dashboard/index.html</h1>")
