"""
Tier 1: Portfolio Orchestrator — LangGraph master graph.

Defines the top-level workflow as a StateGraph:
  START -> detect_regime -> dispatch_sub_orchestrators -> [bonds | crypto | real_estate | distressed]
  -> aggregate_risk -> capital_allocation -> code_guardian_check -> (approved -> synthesize | rejected -> retry)
  -> END

Each sub-orchestrator runs as an independent sub-graph with its own
barrier synchronization and consensus mechanism.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from shared.state_schema import (
    AssetClass,
    EvaluationStatus,
    MarketAgentState,
    MarketRegime,
    RiskMetrics,
)
from shared.signal_schema import PortfolioSignal, SignalBundle
from shared.circuit_breaker import CircuitBreakerRegistry, breaker_registry, with_retry
from orchestrator.regime_detector import MacroRegimeDetector, RegimeClassification
from orchestrator.risk_aggregator import RiskAggregator
from orchestrator.capital_allocator import CapitalAllocator
from agents.code_guardian.rule_validator import RuleValidator
from agents.code_guardian.drift_detector import DriftDetector

logger = logging.getLogger(__name__)


class PortfolioOrchestrator:
    """
    LangGraph-style portfolio orchestrator implementing a DAG of async nodes.

    Workflow:
    1. detect_regime — classify macro environment
    2. fetch_data — gather market data
    3. dispatch_sub_orchestrators — fan out to bonds/crypto/real_estate/distressed
    4. barrier_wait — wait for all sub-orchestrators to complete
    5. aggregate_risk — combine cross-asset risks
    6. allocate_capital — compute target allocations
    7. code_guardian_check — validate all outputs
    8. synthesize — produce final recommendation (or retry on rejection)

    Note: This is implemented as a pure-Python async DAG rather than requiring
    the langgraph library as a hard dependency, making it runnable on any
    Python 3.11+ environment. The graph structure mirrors what LangGraph's
    StateGraph would produce.
    """

    def __init__(
        self,
        sub_orchestrators: Optional[Dict[str, Any]] = None,
        regime_detector: Optional[MacroRegimeDetector] = None,
        risk_aggregator: Optional[RiskAggregator] = None,
        capital_allocator: Optional[CapitalAllocator] = None,
        rule_validator: Optional[RuleValidator] = None,
        drift_detector: Optional[DriftDetector] = None,
        breaker_registry: Optional[CircuitBreakerRegistry] = None,
        max_retries: int = 2,
    ):
        self.sub_orchestrators = sub_orchestrators or {}
        self.regime_detector = regime_detector or MacroRegimeDetector()
        self.risk_aggregator = risk_aggregator or RiskAggregator()
        self.capital_allocator = capital_allocator or CapitalAllocator()
        self.rule_validator = rule_validator or RuleValidator()
        self.drift_detector = drift_detector or DriftDetector()
        self._breakers = breaker_registry or CircuitBreakerRegistry()
        self.max_retries = max_retries
        self._run_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Node: detect_regime
    # ------------------------------------------------------------------
    async def node_detect_regime(
        self, state: MarketAgentState
    ) -> MarketAgentState:
        """Classify macro regime and set recommended allocations."""
        logger.info("Node: detect_regime")
        try:
            macro_data = state.get("macro_data", {})
            self.regime_detector.update_indicators_bulk(macro_data)
            classification = self.regime_detector.classify()

            state["regime"] = classification.regime.value
            state["regime_confidence"] = classification.confidence
            state["risk_metrics"] = state.get("risk_metrics", {})
            state["risk_metrics"]["regime_allocations"] = classification.recommended_allocations
        except Exception as e:
            logger.error(f"Regime detection failed: {e}")
            state["regime"] = MarketRegime.UNKNOWN.value
            state["regime_confidence"] = 0.0
            state.setdefault("errors", []).append(f"regime_detection: {e}")

        return state

    # ------------------------------------------------------------------
    # Node: dispatch_sub_orchestrators
    # ------------------------------------------------------------------
    async def node_dispatch_sub_orchestrators(
        self, state: MarketAgentState
    ) -> MarketAgentState:
        """
        Fan out to all registered sub-orchestrators in parallel.
        Each sub-orchestrator runs independently with its own barrier.
        """
        logger.info("Node: dispatch_sub_orchestrators")
        state["status"] = EvaluationStatus.AGENTS_RUNNING.value

        tasks = {}
        for ac_name, sub_orch in self.sub_orchestrators.items():
            breaker = self._breakers.get_or_create(
                f"sub_orch_{ac_name}", fail_max=3, reset_timeout=120, call_timeout=300
            )
            tasks[ac_name] = self._run_sub_orchestrator(
                ac_name, sub_orch, state, breaker
            )

        results = {}
        errors = []
        degraded = []

        if tasks:
            done = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for ac_name, result in zip(tasks.keys(), done):
                if isinstance(result, Exception):
                    logger.error(f"Sub-orchestrator {ac_name} failed: {result}")
                    errors.append(f"{ac_name}: {result}")
                    degraded.append(ac_name)
                else:
                    results[ac_name] = result
        else:
            logger.warning("No sub-orchestrators registered")

        state["position_recommendations"] = []
        for ac_name, bundle in results.items():
            if isinstance(bundle, dict):
                recs = bundle.get("position_recommendations", [])
                state["position_recommendations"].extend(recs)

        state["deal_analysis"] = results.get("distressed", {}).get("deal_analysis", {})
        state.setdefault("errors", []).extend(errors)
        state["degraded_agents"] = degraded
        state["status"] = EvaluationStatus.BARRIER_WAIT.value

        return state

    async def _run_sub_orchestrator(
        self, name: str, sub_orch: Any, state: MarketAgentState, breaker: Any
    ) -> Dict[str, Any]:
        """Run a single sub-orchestrator through its circuit breaker."""
        async def _execute():
            if hasattr(sub_orch, "run"):
                return await sub_orch.run(state)
            elif callable(sub_orch):
                result = sub_orch(state)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            else:
                raise ValueError(f"Sub-orchestrator {name} is not callable")

        return await with_retry(
            breaker.call, _execute, max_retries=2, base_delay=2.0
        )

    # ------------------------------------------------------------------
    # Node: aggregate_risk
    # ------------------------------------------------------------------
    async def node_aggregate_risk(
        self, state: MarketAgentState
    ) -> MarketAgentState:
        """Aggregate risk metrics from all sub-orchestrators."""
        logger.info("Node: aggregate_risk")
        try:
            regime_allocs = state.get("risk_metrics", {}).get("regime_allocations", {})
            self.risk_aggregator.update_allocations(regime_allocs)

            summary = self.risk_aggregator.aggregate()
            state["risk_metrics"] = state.get("risk_metrics", {})
            state["risk_metrics"]["portfolio_summary"] = summary.to_dict()
            state["risk_metrics"]["breached_limits"] = summary.breached_limits
        except Exception as e:
            logger.error(f"Risk aggregation failed: {e}")
            state.setdefault("errors", []).append(f"risk_aggregation: {e}")

        return state

    # ------------------------------------------------------------------
    # Node: allocate_capital
    # ------------------------------------------------------------------
    async def node_allocate_capital(
        self, state: MarketAgentState
    ) -> MarketAgentState:
        """Compute target capital allocations."""
        logger.info("Node: allocate_capital")
        try:
            regime_allocs = state.get("risk_metrics", {}).get("regime_allocations", {})
            risk_breaches = state.get("risk_metrics", {}).get("breached_limits", [])
            regime = state.get("regime", "unknown")

            plan = self.capital_allocator.allocate(
                regime_allocations=regime_allocs,
                risk_breaches=risk_breaches,
                regime=regime,
            )

            state["risk_metrics"] = state.get("risk_metrics", {})
            state["risk_metrics"]["allocation_plan"] = plan.to_dict()
        except Exception as e:
            logger.error(f"Capital allocation failed: {e}")
            state.setdefault("errors", []).append(f"capital_allocation: {e}")

        return state

    # ------------------------------------------------------------------
    # Node: code_guardian_check
    # ------------------------------------------------------------------
    async def node_code_guardian_check(
        self, state: MarketAgentState
    ) -> MarketAgentState:
        """Run code guardian validation on all outputs."""
        logger.info("Node: code_guardian_check")
        violations = []
        warnings = []

        # Validate position recommendations
        for rec in state.get("position_recommendations", []):
            result = self.rule_validator.validate(rec)
            if not result.passed:
                violations.extend(result.errors)
            warnings.extend(result.warnings)

        # Track outputs for drift detection
        for rec in state.get("position_recommendations", []):
            agent_name = rec.get("agent", "unknown")
            self.drift_detector.record_output(agent_name, rec)

        # Check for drift alerts
        drift_alerts = self.drift_detector.check_drift()
        for alert in drift_alerts:
            warnings.append(f"Drift[{alert.agent_name}]: {alert.description}")

        guardian_report = {
            "passed": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "drift_alerts": len(drift_alerts),
            "timestamp": datetime.utcnow().isoformat(),
        }

        state["code_guardian_report"] = guardian_report
        state["guardian_approved"] = guardian_report["passed"]

        if not guardian_report["passed"]:
            logger.warning(f"Code guardian rejected: {violations}")
            state["status"] = EvaluationStatus.DEGRADED.value
        else:
            state["status"] = EvaluationStatus.ACTION_NEEDED.value

        return state

    # ------------------------------------------------------------------
    # Node: synthesize
    # ------------------------------------------------------------------
    async def node_synthesize(
        self, state: MarketAgentState
    ) -> MarketAgentState:
        """Produce the final recommendation."""
        logger.info("Node: synthesize")

        state["final_recommendation"] = {
            "run_id": state.get("run_id", ""),
            "regime": state.get("regime", "unknown"),
            "regime_confidence": state.get("regime_confidence", 0),
            "allocation_plan": state.get("risk_metrics", {}).get("allocation_plan", {}),
            "position_recommendations": state.get("position_recommendations", []),
            "deal_analysis": state.get("deal_analysis", {}),
            "risk_summary": state.get("risk_metrics", {}).get("portfolio_summary", {}),
            "guardian_approved": state.get("guardian_approved", False),
            "degraded_agents": state.get("degraded_agents", []),
            "errors": state.get("errors", []),
            "timestamp": datetime.utcnow().isoformat(),
        }

        state["status"] = EvaluationStatus.COMPLETED.value
        return state

    # ------------------------------------------------------------------
    # Conditional edge: guardian approved?
    # ------------------------------------------------------------------
    def should_retry(self, state: MarketAgentState) -> str:
        """Conditional routing after code guardian check."""
        retry_count = state.get("retry_count", 0)
        if state.get("guardian_approved", False):
            return "synthesize"
        elif retry_count < self.max_retries:
            return "retry"
        else:
            return "synthesize"  # proceed in degraded mode

    # ------------------------------------------------------------------
    # Main execution: run the DAG
    # ------------------------------------------------------------------
    async def run(
        self,
        ticker: str = "",
        asset_class: str = "",
        market_data: Optional[Dict[str, Any]] = None,
        macro_data: Optional[Dict[str, Any]] = None,
    ) -> MarketAgentState:
        """
        Execute the full portfolio orchestration DAG.

        Graph: detect_regime -> dispatch_sub_orchestrators -> aggregate_risk
               -> allocate_capital -> code_guardian_check -> (retry | synthesize)
        """
        state: MarketAgentState = {
            "run_id": str(uuid.uuid4()),
            "ticker": ticker,
            "asset_class": asset_class,
            "timestamp": datetime.utcnow().isoformat(),
            "market_data": market_data or {},
            "macro_data": macro_data or {},
            "status": EvaluationStatus.PENDING.value,
            "errors": [],
            "degraded_agents": [],
            "retry_count": 0,
            "position_recommendations": [],
        }

        logger.info(f"Portfolio orchestrator run {state['run_id']} starting")

        # Execute DAG nodes sequentially
        # Node 1: Regime detection
        state = await self.node_detect_regime(state)

        # Node 2: Fan out to sub-orchestrators (parallel internally)
        state = await self.node_dispatch_sub_orchestrators(state)

        # Node 3: Aggregate risk
        state = await self.node_aggregate_risk(state)

        # Node 4: Capital allocation
        state = await self.node_allocate_capital(state)

        # Node 5: Code guardian check with retry loop
        for attempt in range(self.max_retries + 1):
            state = await self.node_code_guardian_check(state)
            route = self.should_retry(state)
            if route == "synthesize":
                break
            state["retry_count"] = attempt + 1
            logger.info(f"Code guardian retry {attempt + 1}/{self.max_retries}")

        # Node 6: Synthesize
        state = await self.node_synthesize(state)

        self._run_history.append({
            "run_id": state["run_id"],
            "regime": state.get("regime"),
            "status": state.get("status"),
            "errors": len(state.get("errors", [])),
            "timestamp": state.get("timestamp"),
        })

        logger.info(
            f"Portfolio orchestrator run {state['run_id']} completed: "
            f"status={state.get('status')}, regime={state.get('regime')}"
        )

        return state

    def get_run_history(self, n: int = 20) -> List[Dict[str, Any]]:
        return self._run_history[-n:]

    def get_breaker_states(self) -> Dict[str, str]:
        return self._breakers.get_all_states()
