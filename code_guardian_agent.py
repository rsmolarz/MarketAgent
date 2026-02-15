"""
Code Guardian Agent — top-level facade.

Integrates all three validation layers into a single agent interface
compatible with the existing BaseAgent framework. Positioned as an
Observer/Interceptor between agent output and downstream consumers.

Layer 1: Rule-based numerical validation (synchronous, blocking)
Layer 2: LLM semantic validation (asynchronous, non-blocking)
Layer 3: Statistical drift detection (batch, periodic)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

from agents.code_guardian.rule_validator import RuleValidator, ValidationResult
from agents.code_guardian.llm_validator import LLMValidator
from agents.code_guardian.drift_detector import DriftDetector, DriftAlert

logger = logging.getLogger(__name__)


class CodeGuardianAgent:
    """
    Three-layer hybrid validation interceptor.

    Positioned between agent output and the downstream consumer queue.
    Validates and either passes, corrects, or rejects each output.

    Usage:
        guardian = CodeGuardianAgent()
        result = await guardian.validate(agent_name="ta_rsi", output={...})
        if result["passed"]:
            # proceed with output
        elif result["manual_review_required"]:
            # flag for human review
        else:
            # quarantine output
    """

    def __init__(
        self,
        llm_client: Optional[Callable[..., Coroutine]] = None,
        market_data_lookup: Optional[Callable] = None,
        staleness_threshold_seconds: float = 300.0,
        drift_z_threshold: float = 2.5,
        drift_min_samples: int = 30,
    ):
        # Layer 1: Deterministic rule-based checks
        self.rule_validator = RuleValidator(
            staleness_threshold_seconds=staleness_threshold_seconds
        )

        # Layer 2: LLM semantic validation
        self.llm_validator = LLMValidator(
            llm_client=llm_client,
            market_data_lookup=market_data_lookup,
        )

        # Layer 3: Statistical drift detection
        self.drift_detector = DriftDetector(
            z_threshold=drift_z_threshold,
            min_samples=drift_min_samples,
        )

        self._validation_history: List[Dict[str, Any]] = []
        self._dead_letter_queue: List[Dict[str, Any]] = []
        self._max_dead_letter = 1000

    async def validate(
        self,
        agent_name: str,
        output: Dict[str, Any],
        reference_data: Optional[Dict[str, Any]] = None,
        run_layer2: bool = True,
    ) -> Dict[str, Any]:
        """
        Run all applicable validation layers on an agent output.

        Args:
            agent_name: Name of the agent that produced the output.
            output: The agent output dictionary to validate.
            reference_data: Optional reference data for Layer 2 validation.
            run_layer2: Whether to run LLM validation (can be skipped for speed).

        Returns:
            Validation result dict with keys:
            - passed: bool
            - layer1: ValidationResult dict
            - layer2: LLM validation dict (if run)
            - layer3_recorded: bool
            - violations: List[str]
            - warnings: List[str]
            - manual_review_required: bool
            - quarantined: bool
        """
        result: Dict[str, Any] = {
            "agent_name": agent_name,
            "passed": True,
            "violations": [],
            "warnings": [],
            "manual_review_required": False,
            "quarantined": False,
        }

        # Layer 1: Rule-based validation (blocking)
        layer1_result = self.rule_validator.validate(output)
        result["layer1"] = {
            "passed": layer1_result.passed,
            "errors": layer1_result.errors,
            "warnings": layer1_result.warnings,
            "checked_fields": layer1_result.checked_fields,
            "failed_fields": layer1_result.failed_fields,
        }

        if not layer1_result.passed:
            result["passed"] = False
            result["violations"].extend(layer1_result.errors)
        result["warnings"].extend(layer1_result.warnings)

        # Layer 2: LLM semantic validation (non-blocking)
        if run_layer2:
            try:
                layer2_result = await self.llm_validator.validate(
                    agent_name=agent_name,
                    output=output,
                    reference_data=reference_data,
                )
                result["layer2"] = layer2_result

                if not layer2_result.get("is_valid", True):
                    issues = layer2_result.get("issues", [])
                    critical_issues = [
                        i for i in issues
                        if i.get("severity") in ("high", "critical")
                    ]
                    if critical_issues:
                        result["passed"] = False
                        result["quarantined"] = True
                        result["violations"].extend(
                            f"LLM[{i['type']}]: {i['description']}"
                            for i in critical_issues
                        )
            except Exception as e:
                logger.warning(f"Layer 2 validation error (non-blocking): {e}")
                result["layer2"] = {"skipped": True, "reason": str(e)}
        else:
            result["layer2"] = {"skipped": True, "reason": "run_layer2=False"}

        # Layer 3: Record for drift detection (always runs)
        self.drift_detector.record_output(agent_name, output)
        self.drift_detector.record_error(agent_name, not result["passed"])
        result["layer3_recorded"] = True

        # Check for drift alerts
        drift_alerts = self.drift_detector.check_drift(agent_name)
        if drift_alerts:
            for alert in drift_alerts:
                result["warnings"].append(f"Drift[{alert.metric_name}]: {alert.description}")
                if alert.severity in ("high", "critical"):
                    result["manual_review_required"] = True

        # Dead letter queue for failed validations
        if not result["passed"]:
            self._add_to_dead_letter(agent_name, output, result)

        # Record history
        self._validation_history.append({
            "agent_name": agent_name,
            "passed": result["passed"],
            "violations": len(result["violations"]),
            "warnings": len(result["warnings"]),
        })

        return result

    async def validate_batch(
        self,
        outputs: List[Dict[str, Any]],
        reference_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Validate a batch of agent outputs."""
        tasks = [
            self.validate(
                agent_name=o.get("agent", "unknown"),
                output=o,
                reference_data=reference_data,
            )
            for o in outputs
        ]
        return await asyncio.gather(*tasks)

    def _add_to_dead_letter(
        self,
        agent_name: str,
        output: Dict[str, Any],
        validation_result: Dict[str, Any],
    ) -> None:
        """Add a failed validation to the dead letter queue."""
        self._dead_letter_queue.append({
            "agent_name": agent_name,
            "output": output,
            "validation_result": {
                "passed": validation_result["passed"],
                "violations": validation_result["violations"],
            },
        })
        # Cap at max size
        if len(self._dead_letter_queue) > self._max_dead_letter:
            self._dead_letter_queue = self._dead_letter_queue[-self._max_dead_letter:]

    def run_drift_check(self) -> List[DriftAlert]:
        """Run drift detection across all tracked agents."""
        return self.drift_detector.check_drift()

    def get_quarantined(self) -> List[Dict[str, Any]]:
        """Get all quarantined outputs from Layer 2."""
        return self.llm_validator.get_quarantined()

    def get_dead_letter_queue(self) -> List[Dict[str, Any]]:
        """Get the dead letter queue."""
        return list(self._dead_letter_queue)

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        total = len(self._validation_history)
        passed = sum(1 for v in self._validation_history if v["passed"])
        return {
            "total_validations": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0,
            "dead_letter_queue_size": len(self._dead_letter_queue),
            "quarantined_count": len(self.llm_validator.get_quarantined()),
            "drift_alerts": len(self.drift_detector.get_alerts()),
        }

    def get_agent_drift_summary(self, agent_name: str) -> Dict[str, Any]:
        """Get drift detector summary for a specific agent."""
        return self.drift_detector.get_agent_summary(agent_name)
