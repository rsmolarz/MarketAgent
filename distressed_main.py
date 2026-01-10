#!/usr/bin/env python3
"""
Distressed Investing Platform - Replit Entry Point
===================================================
Main entry point for running on Replit.
Serves both the API and the dashboard UI.

Click "Run" to start the server, then open the webview.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def create_app():
    """Create and configure the FastAPI application."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import HTMLResponse, FileResponse
    except ImportError:
        logger.error("FastAPI not installed. Installing...")
        os.system("pip install fastapi uvicorn python-multipart aiofiles")
        from fastapi import FastAPI, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import HTMLResponse, FileResponse

    # Import our API routes
    from dashboard.api import app as api_app
    
    # Create main app
    app = FastAPI(
        title="Distressed Investing Platform",
        description="Portfolio management, backtesting, and analysis for distressed debt investing",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )
    
    # CORS - allow all for Replit
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount API routes
    app.mount("/api", api_app)
    
    # Serve dashboard at root
    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard():
        """Serve the main dashboard."""
        dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")
        if os.path.exists(dashboard_path):
            with open(dashboard_path, "r") as f:
                return HTMLResponse(content=f.read())
        else:
            return HTMLResponse(content=get_embedded_dashboard())
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "platform": "distressed-investing"}
    
    return app


def get_embedded_dashboard():
    """Return embedded dashboard HTML if file not found."""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Distressed Investing Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="max-w-4xl mx-auto py-12 px-4">
        <div class="bg-white rounded-xl shadow-lg p-8">
            <h1 class="text-3xl font-bold text-gray-900 mb-4">📊 Distressed Investing Platform</h1>
            <p class="text-gray-600 mb-6">Welcome! The platform is running successfully.</p>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                <a href="/api/docs" class="block p-4 bg-blue-50 rounded-lg hover:bg-blue-100 transition">
                    <h3 class="font-semibold text-blue-900">📚 API Documentation</h3>
                    <p class="text-sm text-blue-700">Interactive Swagger UI</p>
                </a>
                <a href="/api/portfolio/summary" class="block p-4 bg-green-50 rounded-lg hover:bg-green-100 transition">
                    <h3 class="font-semibold text-green-900">💼 Portfolio Summary</h3>
                    <p class="text-sm text-green-700">View current portfolio</p>
                </a>
                <a href="/api/backtest/cases" class="block p-4 bg-purple-50 rounded-lg hover:bg-purple-100 transition">
                    <h3 class="font-semibold text-purple-900">📈 Historical Cases</h3>
                    <p class="text-sm text-purple-700">Bankruptcy case database</p>
                </a>
                <a href="/api/backtest/strategies" class="block p-4 bg-orange-50 rounded-lg hover:bg-orange-100 transition">
                    <h3 class="font-semibold text-orange-900">🎯 Strategies</h3>
                    <p class="text-sm text-orange-700">Available backtest strategies</p>
                </a>
            </div>
            
            <div class="bg-gray-50 rounded-lg p-4">
                <h3 class="font-semibold text-gray-800 mb-2">Quick Start</h3>
                <pre class="text-sm text-gray-600 overflow-x-auto">
# Get portfolio summary
curl /api/portfolio/summary

# Run a backtest
curl -X POST /api/backtest/run \\
  -H "Content-Type: application/json" \\
  -d '{"strategy_name": "fulcrum_hunter"}'

# View historical cases
curl /api/backtest/cases
                </pre>
            </div>
        </div>
    </div>
</body>
</html>
'''


def main():
    """Main entry point."""
    import uvicorn
    
    # Get port from environment (Replit sets this)
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    logger.info(f"""
╔══════════════════════════════════════════════════════════════╗
║     🏦 DISTRESSED INVESTING PLATFORM                         ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Dashboard:  http://{host}:{port}/                              ║
║  API Docs:   http://{host}:{port}/api/docs                      ║
║  Health:     http://{host}:{port}/health                        ║
║                                                              ║
║  Features:                                                   ║
║  • Portfolio Management & P&L Tracking                       ║
║  • Risk Limits & Stress Testing                              ║
║  • Backtesting on Historical Bankruptcies                    ║
║  • Data Feed Integration                                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    app = create_app()
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
