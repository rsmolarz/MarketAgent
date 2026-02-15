"""
Abstract base sub-orchestrator implementing the pluggable pattern.

All asset-class sub-orchestrators inherit from this base, which provides:
- Agent registration and lifecycle management
- Bitmask barrier synchronization
- Circuit breaker wrapping per agent
- Confidence-weighted consensus aggregation
- Code guardian Layer 1 validation
- Standard signal output formatting
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

from shared.state_schema import (
    AssetClass,
    ConvictionScore,
    Direction,
    EvaluationStatus,
    LLMOpinion,
    RiskMetrics,
    SubOrchestratorState,
    TAScore,
)
from shared.signal_schema import Signal, SignalBundle
from shared.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    with_retry,
)
from agents.consensus.aggregator import (
    AgentFlags,
    AGENT_FLAG_MAP,
    BitmaskBarrier,
    HybridVotingAggregator,
)
from agents.code_guardian.rule_validator import RuleValidator

logger = logging.getLogger(__name__)


class BaseSubOrchestrator(ABC):
    """
    Abstract base for asset-class sub-orchestrators.

    Subclasses must implement:
    - asset_class property
    - register_agents(): register specialized agents for this asset class
    - fetch_data(): fetch asset-class-specific data
    - compute_risk_metrics(): compute asset-class-specific risk metrics
    """

    def __init__(
        self,
        ta_weight: float = 0.6,
        llm_weight: float = 0.4,
        barrier_timeout: float = 120.0,
        agent_call_timeout: float = 30.0,
    ):
        self._agents: Dict[str, Callable] = {}
        self._agent_flags: Dict[str, AgentFlags] = {}
        self._ta_agents: List[str] = []
        self._llm_agents: List[str] = []
        self._breakers = CircuitBreakerRegistry()
        self._rule_validator = RuleValidator()
        self._ta_weight = ta_weight
        self._llm_weight = llm_weight
        self._barrier_timeout = barrier_timeout
        self._agent_call_timeout = agent_call_timeout
        self._run_history: List[Dict[str, Any]] = []

        # Let subclass register its agents
        self.register_agents()

    @property
    @abstractmethod
    def asset_class(self) -> AssetClass:
        """Return the asset class this sub-orchestrator handles."""
        ...

    @abstractmethod
    def register_agents(self) -> None:
        """Register all specialized agents for this asset class."""
        ...

    @abstractmethod
    async def fetch_data(self, tickers: List[str], state: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch asset-class-specific market data."""
        ...

    @abstractmethod
    async def compute_risk_metrics(self, state: Dict[str, Any]) -> RiskMetrics:
        """Compute asset-class-specific risk metrics."""
        ...

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_ta_agent(
        self,
        name: str,
        agent_fn: Callable,
        flag: Optional[AgentFlags] = None,
    ) -> None:
        """Register a technical analysis agent."""
        self._agents[name] = agent_fn
        self._ta_agents.append(name)
        if flag:
            self._agent_flags[name] = flag

    def register_llm_agent(
        self,
        name: str,
        agent_fn: Callable,
        flag: Optional[AgentFlags] = None,
    ) -> None:
        """Register an LLM council agent."""
        self._agents[name] = agent_fn
        self._llm_agents.append(name)
        if flag:
            self._agent_flags[name] = flag

    # ------------------------------------------------------------------
    # Agent execution
    # ------------------------------------------------------------------

    async def _run_agent(
        self,
        name: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run a single agent through its circuit breaker with retry."""
        agent_fn = self._agents[name]
        breaker = self._breakers.get_or_create(
            name, fail_max=3, reset_timeout=60, call_timeout=self._agent_call_timeout
        )

        start = time.monotonic()

        async def _execute():
            if asyncio.iscoroutinefunction(agent_fn):
                return await agent_fn(data)
            result = agent_fn(data)
            if asyncio.iscoroutine(result):
                return await result
            return result

        try:
            result = await with_retry(breaker.call, _execute, max_retries=2, base_delay=2.0)
            elapsed = time.monotonic() - start
            if isinstance(result, dict):
                result["response_time_ms"] = elapsed * 1000
            return result
        except CircuitBreakerOpenError:
            logger.warning(f"Agent {name} circuit breaker is OPEN, skipping")
            return {"error": "circuit_breaker_open", "agent": name}
        except Exception as e:
            logger.error(f"Agent {name} failed after retries: {e}")
            return {"error": str(e), "agent": name}

    async def _run_all_agents(
        self, data: Dict[str, Any]
    ) -> Tuple[List[TAScore], List[LLMOpinion], List[str], List[str]]:
        """
        Run all TA and LLM agents in parallel with barrier tracking.
        Returns (ta_scores, llm_opinions, completed, failed).
        """
        barrier = BitmaskBarrier(timeout_seconds=self._barrier_timeout)
        barrier.start()

        # Fan out all agents
        ta_tasks = {name: self._run_agent(name, data) for name in self._ta_agents}
        llm_tasks = {name: self._run_agent(name, data) for name in self._llm_agents}

        all_tasks = {**ta_tasks, **llm_tasks}
        results = {}

        if all_tasks:
            done = await asyncio.gather(*all_tasks.values(), return_exceptions=True)
            for name, result in zip(all_tasks.keys(), done):
                if isinstance(result, Exception):
                    results[name] = {"error": str(result), "agent": name}
                else:
                    results[name] = result

        # Process TA results
        ta_scores = []
        for name in self._ta_agents:
            result = results.get(name, {})
            if "error" not in result:
                score = result.get("score", 50)
                confidence = result.get("confidence", 0.5)
                ta_scores.append(TAScore(
                    agent_name=name,
                    indicator=result.get("indicator", name),
                    score=max(0, min(100, float(score))),
                    confidence=max(0, min(1, float(confidence))),
                    signals=result.get("signals", {}),
                ))
                if name in self._agent_flags:
                    AGENT_FLAG_MAP[name] = self._agent_flags[name]
                barrier.mark_complete(name)
            else:
                barrier.mark_failed(name)

        # Process LLM results
        llm_opinions = []
        for name in self._llm_agents:
            result = results.get(name, {})
            if "error" not in result:
                direction_str = result.get("direction", "neutral").lower()
                try:
                    direction = Direction(direction_str)
                except ValueError:
                    direction = Direction.NEUTRAL
                llm_opinions.append(LLMOpinion(
                    agent_name=name,
                    model=result.get("model", ""),
                    direction=direction,
                    reasoning=result.get("reasoning", ""),
                    confidence=max(0, min(1, float(result.get("confidence", 0.5)))),
                ))
                if name in self._agent_flags:
                    AGENT_FLAG_MAP[name] = self._agent_flags[name]
                barrier.mark_complete(name)
            else:
                barrier.mark_failed(name)

        status = barrier.status()
        completed = barrier.get_completed_agents()
        failed = barrier.get_missing_agents()

        logger.info(
            f"[{self.asset_class.value}] Barrier: {status.completion_pct:.0%} complete, "
            f"viable={status.is_viable}, failed={failed}"
        )

        return ta_scores, llm_opinions, completed, failed

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    async def run(self, parent_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the sub-orchestrator workflow:
        1. Fetch data
        2. Run all agents (parallel with barrier)
        3. Aggregate consensus
        4. Validate outputs
        5. Compute risk metrics
        6. Return signal bundle
        """
        run_id = str(uuid.uuid4())
        ac = self.asset_class.value
        logger.info(f"[{ac}] Sub-orchestrator run {run_id} starting")

        tickers = parent_state.get("tickers", [parent_state.get("ticker", "")])
        tickers = [t for t in tickers if t]

        # Step 1: Fetch data
        try:
            data = await self.fetch_data(tickers, parent_state)
        except Exception as e:
            logger.error(f"[{ac}] Data fetch failed: {e}")
            return {"error": f"data_fetch: {e}", "asset_class": ac}

        # Step 2: Run all agents
        ta_scores, llm_opinions, completed, failed = await self._run_all_agents(data)

        # Step 3: Aggregate consensus
        aggregator = HybridVotingAggregator(
            ta_weight=self._ta_weight, llm_weight=self._llm_weight
        )
        for score in ta_scores:
            aggregator.add_ta_score(score)
        for opinion in llm_opinions:
            aggregator.add_llm_opinion(opinion)

        conviction_scores = {}
        for ticker in tickers or [""]:
            conviction = aggregator.aggregate(ticker=ticker)
            conviction.missing_agents = failed
            conviction.is_degraded = len(failed) > 0
            conviction_scores[ticker] = conviction

        # Step 4: Validate outputs
        validation_errors = []
        for score in ta_scores:
            result = self._rule_validator.validate(score.model_dump())
            if not result.passed:
                validation_errors.extend(result.errors)

        # Step 5: Risk metrics
        try:
            risk = await self.compute_risk_metrics(data)
        except Exception as e:
            logger.error(f"[{ac}] Risk computation failed: {e}")
            risk = RiskMetrics(asset_class=self.asset_class)

        # Step 6: Build signal bundle
        signals = []
        for ticker, conviction in conviction_scores.items():
            signals.append(Signal(
                source_agent=f"{ac}_sub_orchestrator",
                source_tier=2,
                asset_class=self.asset_class,
                ticker=ticker,
                direction=conviction.llm_consensus,
                conviction=conviction.combined_score,
                position_size_pct=self._conviction_to_position_size(conviction.combined_score),
                risk_metrics=risk.model_dump(exclude_none=True),
                data_freshness_seconds=0,
            ))

        bundle = SignalBundle(
            asset_class=self.asset_class,
            signals=signals,
            regime=parent_state.get("regime", "unknown"),
            regime_confidence=parent_state.get("regime_confidence", 0),
            is_degraded=len(failed) > 0,
            degraded_agents=failed,
        )

        result = {
            "run_id": run_id,
            "asset_class": ac,
            "signal_bundle": bundle.model_dump(mode="json"),
            "conviction_scores": {
                t: c.model_dump(mode="json") for t, c in conviction_scores.items()
            },
            "ta_scores": [s.model_dump(mode="json") for s in ta_scores],
            "llm_opinions": [o.model_dump(mode="json") for o in llm_opinions],
            "risk_metrics": risk.model_dump(mode="json"),
            "completed_agents": completed,
            "failed_agents": failed,
            "validation_errors": validation_errors,
            "position_recommendations": [s.to_dict() for s in signals],
        }

        self._run_history.append({
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "tickers": tickers,
            "completed": len(completed),
            "failed": len(failed),
        })

        logger.info(
            f"[{ac}] Run {run_id} complete: "
            f"{len(completed)} agents OK, {len(failed)} failed"
        )
        return result

    def _conviction_to_position_size(self, conviction: float) -> float:
        """Map conviction [-1, 1] to position size [0, 1]."""
        abs_conv = abs(conviction)
        if abs_conv < 0.2:
            return 0.0
        elif abs_conv < 0.5:
            return 0.02
        elif abs_conv < 0.7:
            return 0.05
        elif abs_conv < 0.9:
            return 0.08
        else:
            return 0.10

    def get_run_history(self, n: int = 20) -> List[Dict[str, Any]]:
        return self._run_history[-n:]

    def get_breaker_states(self) -> Dict[str, str]:
        return self._breakers.get_all_states()
