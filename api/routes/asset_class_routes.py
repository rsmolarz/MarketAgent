"""
Asset class-specific API routes.

Endpoints for running individual sub-orchestrators, fetching
asset-class-specific data, and viewing per-asset analysis results.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class SubOrchRunRequest(BaseModel):
    """Request to run a single sub-orchestrator."""
    tickers: List[str] = Field(default_factory=list)
    market_data: Dict[str, Any] = Field(default_factory=dict)
    regime: str = "unknown"
    regime_confidence: float = 0.0


class SubOrchRunResponse(BaseModel):
    """Response from sub-orchestrator run."""
    asset_class: str
    run_id: str = ""
    conviction_scores: Dict[str, Any] = Field(default_factory=dict)
    risk_metrics: Dict[str, Any] = Field(default_factory=dict)
    completed_agents: List[str] = Field(default_factory=list)
    failed_agents: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)


async def _run_sub_orch(asset_class: str, request: SubOrchRunRequest) -> SubOrchRunResponse:
    """Helper to run a specific sub-orchestrator."""
    from api.main import get_orchestrator

    orchestrator = get_orchestrator()
    sub_orch = orchestrator.sub_orchestrators.get(asset_class)
    if not sub_orch:
        raise HTTPException(status_code=404, detail=f"Sub-orchestrator '{asset_class}' not found")

    state = {
        "tickers": request.tickers,
        "market_data": request.market_data,
        "regime": request.regime,
        "regime_confidence": request.regime_confidence,
    }

    try:
        result = await sub_orch.run(state)
        return SubOrchRunResponse(
            asset_class=asset_class,
            run_id=result.get("run_id", ""),
            conviction_scores=result.get("conviction_scores", {}),
            risk_metrics=result.get("risk_metrics", {}),
            completed_agents=result.get("completed_agents", []),
            failed_agents=result.get("failed_agents", []),
            validation_errors=result.get("validation_errors", []),
        )
    except Exception as e:
        logger.error(f"Sub-orchestrator {asset_class} failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bonds/run", response_model=SubOrchRunResponse)
async def run_bonds(request: SubOrchRunRequest):
    """Run bonds sub-orchestrator analysis."""
    return await _run_sub_orch("bonds", request)


@router.post("/crypto/run", response_model=SubOrchRunResponse)
async def run_crypto(request: SubOrchRunRequest):
    """Run crypto sub-orchestrator analysis."""
    return await _run_sub_orch("crypto", request)


@router.post("/real-estate/run", response_model=SubOrchRunResponse)
async def run_real_estate(request: SubOrchRunRequest):
    """Run real estate sub-orchestrator analysis."""
    return await _run_sub_orch("real_estate", request)


@router.post("/distressed/run", response_model=SubOrchRunResponse)
async def run_distressed(request: SubOrchRunRequest):
    """Run distressed debt sub-orchestrator analysis."""
    return await _run_sub_orch("distressed", request)


@router.get("/bonds/history")
async def bonds_history(n: int = 20):
    from api.main import get_orchestrator
    orch = get_orchestrator()
    sub = orch.sub_orchestrators.get("bonds")
    return {"runs": sub.get_run_history(n) if sub else []}


@router.get("/crypto/history")
async def crypto_history(n: int = 20):
    from api.main import get_orchestrator
    orch = get_orchestrator()
    sub = orch.sub_orchestrators.get("crypto")
    return {"runs": sub.get_run_history(n) if sub else []}


@router.get("/real-estate/history")
async def re_history(n: int = 20):
    from api.main import get_orchestrator
    orch = get_orchestrator()
    sub = orch.sub_orchestrators.get("real_estate")
    return {"runs": sub.get_run_history(n) if sub else []}


@router.get("/distressed/history")
async def distressed_history(n: int = 20):
    from api.main import get_orchestrator
    orch = get_orchestrator()
    sub = orch.sub_orchestrators.get("distressed")
    return {"runs": sub.get_run_history(n) if sub else []}


@router.get("/{asset_class}/breakers")
async def asset_breakers(asset_class: str):
    """Get circuit breaker states for a specific asset class."""
    from api.main import get_orchestrator
    orch = get_orchestrator()
    sub = orch.sub_orchestrators.get(asset_class)
    if not sub:
        raise HTTPException(status_code=404, detail=f"Asset class '{asset_class}' not found")
    return {"asset_class": asset_class, "breaker_states": sub.get_breaker_states()}
