"""
Orchestrator API routes.

Endpoints for running the portfolio orchestrator, checking regime,
viewing allocation plans, and managing the orchestration lifecycle.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class RunAnalysisRequest(BaseModel):
    """Request to run a full portfolio analysis."""
    ticker: str = ""
    asset_class: str = ""
    market_data: Dict[str, Any] = Field(default_factory=dict)
    macro_data: Dict[str, Any] = Field(default_factory=dict)


class RunAnalysisResponse(BaseModel):
    """Response from portfolio analysis run."""
    run_id: str
    status: str
    regime: str = "unknown"
    regime_confidence: float = 0.0
    allocation_plan: Dict[str, Any] = Field(default_factory=dict)
    position_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    guardian_approved: bool = False
    errors: List[str] = Field(default_factory=list)
    timestamp: str = ""


@router.post("/run", response_model=RunAnalysisResponse)
async def run_analysis(request: RunAnalysisRequest):
    """
    Run a full portfolio orchestration cycle.

    Executes the complete DAG:
    detect_regime -> dispatch_sub_orchestrators -> aggregate_risk
    -> allocate_capital -> code_guardian_check -> synthesize
    """
    from api.main import get_orchestrator

    try:
        orchestrator = get_orchestrator()
        state = await orchestrator.run(
            ticker=request.ticker,
            asset_class=request.asset_class,
            market_data=request.market_data,
            macro_data=request.macro_data,
        )

        final = state.get("final_recommendation", {})
        return RunAnalysisResponse(
            run_id=state.get("run_id", ""),
            status=state.get("status", "unknown"),
            regime=state.get("regime", "unknown"),
            regime_confidence=state.get("regime_confidence", 0),
            allocation_plan=final.get("allocation_plan", {}),
            position_recommendations=final.get("position_recommendations", []),
            guardian_approved=state.get("guardian_approved", False),
            errors=state.get("errors", []),
            timestamp=state.get("timestamp", ""),
        )
    except Exception as e:
        logger.error(f"Analysis run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime")
async def get_current_regime():
    """Get the current macro regime classification."""
    from api.main import get_orchestrator

    orchestrator = get_orchestrator()
    history = orchestrator.regime_detector.get_history(1)
    if history:
        return history[-1].to_dict()
    return {"regime": "unknown", "confidence": 0, "message": "No regime classification yet"}


@router.get("/allocation")
async def get_allocation_plan():
    """Get the latest capital allocation plan."""
    from api.main import get_orchestrator

    orchestrator = get_orchestrator()
    history = orchestrator.capital_allocator.get_history(1)
    if history:
        return history[-1].to_dict()
    return {"message": "No allocation plan yet"}


@router.get("/history")
async def get_run_history(n: int = 20):
    """Get recent orchestration run history."""
    from api.main import get_orchestrator

    orchestrator = get_orchestrator()
    return {"runs": orchestrator.get_run_history(n)}


@router.get("/breakers")
async def get_circuit_breaker_states():
    """Get circuit breaker states for all agents."""
    from api.main import get_orchestrator

    orchestrator = get_orchestrator()
    return {"breaker_states": orchestrator.get_breaker_states()}
