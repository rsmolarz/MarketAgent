"""
Monitoring and observability API routes.

Endpoints for circuit breaker states, drift detection alerts,
cache statistics, and agent performance metrics.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from shared.circuit_breaker import breaker_registry
from data.cache import market_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/circuit-breakers")
async def get_all_breaker_states():
    """Get circuit breaker states for all registered agents."""
    return {
        "breaker_states": breaker_registry.get_all_states(),
        "open_breakers": breaker_registry.get_open_breakers(),
        "stats": breaker_registry.get_stats(),
    }


@router.post("/circuit-breakers/reset")
async def reset_all_breakers():
    """Reset all circuit breakers to closed state."""
    breaker_registry.reset_all()
    return {"message": "All circuit breakers reset", "states": breaker_registry.get_all_states()}


@router.get("/cache")
async def get_cache_stats():
    """Get cache statistics."""
    return market_cache.get_stats()


@router.post("/cache/clear")
async def clear_cache():
    """Clear the market data cache."""
    market_cache.clear()
    return {"message": "Cache cleared"}


@router.post("/cache/cleanup")
async def cleanup_cache():
    """Run cache cleanup (remove expired entries)."""
    removed = market_cache.cleanup()
    return {"removed": removed, "remaining": market_cache.size}


@router.get("/drift-alerts")
async def get_drift_alerts(severity: Optional[str] = None):
    """Get drift detection alerts from the code guardian."""
    from api.main import get_orchestrator

    try:
        orchestrator = get_orchestrator()
        alerts = orchestrator.drift_detector.get_alerts(severity)
        return {
            "alerts": [
                {
                    "agent_name": a.agent_name,
                    "metric_name": a.metric_name,
                    "drift_type": a.drift_type,
                    "severity": a.severity,
                    "baseline_value": a.baseline_value,
                    "current_value": a.current_value,
                    "z_score": a.z_score,
                    "description": a.description,
                }
                for a in alerts
            ],
            "count": len(alerts),
        }
    except Exception as e:
        return {"alerts": [], "count": 0, "error": str(e)}


@router.get("/agent-summaries")
async def get_agent_summaries():
    """Get drift detector summaries for all agents."""
    from api.main import get_orchestrator

    try:
        orchestrator = get_orchestrator()
        return orchestrator.drift_detector.get_all_summaries()
    except Exception as e:
        return {"error": str(e)}


@router.get("/system")
async def system_status():
    """Get overall system status."""
    from api.main import get_orchestrator

    try:
        orchestrator = get_orchestrator()
        open_breakers = breaker_registry.get_open_breakers()

        return {
            "status": "degraded" if open_breakers else "healthy",
            "orchestrator_runs": len(orchestrator.get_run_history(100)),
            "open_circuit_breakers": open_breakers,
            "cache": market_cache.get_stats(),
            "sub_orchestrators": list(orchestrator.sub_orchestrators.keys()),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
