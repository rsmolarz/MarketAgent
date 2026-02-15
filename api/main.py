"""
FastAPI + Uvicorn entry point for the MarketAgent multi-agent platform.

Provides:
- REST API endpoints per asset class
- WebSocket streaming for real-time updates
- Orchestration control (run analysis, check status)
- Health checks and monitoring
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from orchestrator.portfolio_orchestrator import PortfolioOrchestrator
from orchestrator.regime_detector import MacroRegimeDetector
from orchestrator.risk_aggregator import RiskAggregator
from orchestrator.capital_allocator import CapitalAllocator
from sub_orchestrators.bonds_orchestrator import BondsOrchestrator
from sub_orchestrators.crypto_orchestrator import CryptoOrchestrator
from sub_orchestrators.real_estate_orchestrator import RealEstateOrchestrator
from sub_orchestrators.distressed_orchestrator import DistressedOrchestrator
from agents.code_guardian.rule_validator import RuleValidator
from agents.code_guardian.drift_detector import DriftDetector
from shared.circuit_breaker import breaker_registry
from data.cache import market_cache
from api.routes.orchestrator_routes import router as orchestrator_router
from api.routes.asset_class_routes import router as asset_class_router
from api.routes.monitoring_routes import router as monitoring_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global instances (lazily loaded for memory efficiency)
# ---------------------------------------------------------------------------

_orchestrator: Optional[PortfolioOrchestrator] = None


def get_orchestrator() -> PortfolioOrchestrator:
    """Lazy-load the portfolio orchestrator and all sub-orchestrators."""
    global _orchestrator
    if _orchestrator is None:
        bonds = BondsOrchestrator()
        crypto = CryptoOrchestrator()
        real_estate = RealEstateOrchestrator()
        distressed = DistressedOrchestrator()

        _orchestrator = PortfolioOrchestrator(
            sub_orchestrators={
                "bonds": bonds,
                "crypto": crypto,
                "real_estate": real_estate,
                "distressed": distressed,
            },
            regime_detector=MacroRegimeDetector(),
            risk_aggregator=RiskAggregator(),
            capital_allocator=CapitalAllocator(),
            rule_validator=RuleValidator(),
            drift_detector=DriftDetector(),
            breaker_registry=breaker_registry,
        )
        logger.info("Portfolio orchestrator initialized with all sub-orchestrators")
    return _orchestrator


# ---------------------------------------------------------------------------
# Lifespan (startup/shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("MarketAgent API starting up")
    yield
    logger.info("MarketAgent API shutting down")
    market_cache.clear()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MarketAgent Multi-Agent Platform",
    description=(
        "Three-tier hierarchical multi-agent financial analysis platform. "
        "Portfolio orchestrator -> Asset-class sub-orchestrators -> Specialized agents."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(orchestrator_router, prefix="/api/v1/orchestrator", tags=["orchestrator"])
app.include_router(asset_class_router, prefix="/api/v1/assets", tags=["asset-classes"])
app.include_router(monitoring_router, prefix="/api/v1/monitoring", tags=["monitoring"])


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "cache_size": market_cache.size,
        "breaker_states": breaker_registry.get_all_states(),
    }


@app.get("/")
async def root():
    return {
        "name": "MarketAgent Multi-Agent Platform",
        "version": "1.0.0",
        "tiers": {
            "tier1": "Portfolio Orchestrator",
            "tier2": ["Bonds", "Crypto", "Real Estate", "Distressed Debt"],
            "tier3": "Specialized Analysis Agents",
        },
        "endpoints": {
            "orchestrator": "/api/v1/orchestrator",
            "assets": "/api/v1/assets",
            "monitoring": "/api/v1/monitoring",
            "health": "/health",
            "ws": "/ws/stream",
        },
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint for real-time streaming
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manage WebSocket connections for real-time streaming."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


ws_manager = ConnectionManager()


@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time analysis streaming."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back with timestamp
            await websocket.send_json({
                "type": "ack",
                "received": data,
                "timestamp": datetime.utcnow().isoformat(),
            })
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Factory function for the FastAPI app."""
    return app


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV", "development") == "development",
        log_level="info",
    )
