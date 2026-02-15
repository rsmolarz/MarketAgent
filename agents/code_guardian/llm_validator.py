"""
Layer 2: LLM-based semantic validation.

Asynchronous, non-blocking — uses a separate validator LLM to check text
outputs for hallucinations, logical inconsistencies, and factual errors.
Cross-references claimed prices against actual market data, verifies
ticker symbols, and checks reasoning consistency.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


VALIDATION_PROMPT = """You are a financial data validator. Your job is to check the following analysis output for:

1. HALLUCINATIONS: Does the analysis claim specific prices, dates, or statistics that seem fabricated?
2. LOGICAL INCONSISTENCIES: Does the reasoning contradict itself?
3. FACTUAL ERRORS: Are there obviously wrong financial facts?
4. TICKER VALIDITY: Are the mentioned ticker symbols real?
5. INTERNAL CONSISTENCY: Do the numbers add up? Does the conclusion match the evidence?

Analysis to validate:
{analysis_text}

Known market data for reference:
{reference_data}

Respond in JSON format:
{{
    "is_valid": true/false,
    "confidence": 0.0 to 1.0,
    "issues": [
        {{
            "type": "hallucination" | "logical_inconsistency" | "factual_error" | "invalid_ticker" | "inconsistency",
            "severity": "low" | "medium" | "high" | "critical",
            "description": "Description of the issue",
            "field": "field name if applicable"
        }}
    ],
    "summary": "Brief summary of validation result"
}}"""


class LLMValidator:
    """
    Layer 2 validator: uses an LLM to semantically validate agent outputs.

    Runs asynchronously and non-blocking. Critical failures trigger alerts
    and output quarantine.
    """

    def __init__(
        self,
        llm_client: Optional[Callable[..., Coroutine]] = None,
        market_data_lookup: Optional[Callable[[str], Dict[str, Any]]] = None,
        critical_severity_threshold: str = "high",
    ):
        """
        Args:
            llm_client: Async callable that takes a prompt string and returns response text.
            market_data_lookup: Async callable that takes a ticker and returns current market data.
            critical_severity_threshold: Minimum severity that triggers quarantine ("low"/"medium"/"high"/"critical").
        """
        self.llm_client = llm_client
        self.market_data_lookup = market_data_lookup
        self.severity_levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        self.critical_threshold = self.severity_levels.get(critical_severity_threshold, 2)
        self._quarantined: List[Dict[str, Any]] = []

    async def validate(
        self,
        agent_name: str,
        output: Dict[str, Any],
        reference_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Validate an agent's text output using LLM semantic checking.

        Returns a validation result dict with is_valid, issues, and quarantine status.
        """
        if self.llm_client is None:
            logger.warning("No LLM client configured for Layer 2 validation")
            return {
                "is_valid": True,
                "confidence": 0.0,
                "issues": [],
                "summary": "Layer 2 validation skipped (no LLM client)",
                "quarantined": False,
            }

        # Build reference data
        ref_data = reference_data or {}
        ticker = output.get("symbol") or output.get("ticker")
        if ticker and self.market_data_lookup:
            try:
                if asyncio.iscoroutinefunction(self.market_data_lookup):
                    market = await self.market_data_lookup(ticker)
                else:
                    market = self.market_data_lookup(ticker)
                ref_data.update(market)
            except Exception as e:
                logger.warning(f"Could not fetch reference data for {ticker}: {e}")

        # Build analysis text from output
        analysis_text = self._format_output_for_validation(agent_name, output)

        prompt = VALIDATION_PROMPT.format(
            analysis_text=analysis_text,
            reference_data=json.dumps(ref_data, indent=2, default=str),
        )

        try:
            response = await self.llm_client(prompt)
            result = self._parse_response(response)
        except Exception as e:
            logger.error(f"Layer 2 LLM validation failed for {agent_name}: {e}")
            return {
                "is_valid": True,  # Don't block on validation failure
                "confidence": 0.0,
                "issues": [],
                "summary": f"Validation error: {e}",
                "quarantined": False,
            }

        # Check if any issues exceed critical threshold
        should_quarantine = any(
            self.severity_levels.get(issue.get("severity", "low"), 0) >= self.critical_threshold
            for issue in result.get("issues", [])
        )

        result["quarantined"] = should_quarantine
        result["agent_name"] = agent_name

        if should_quarantine:
            self._quarantined.append({
                "agent_name": agent_name,
                "output": output,
                "validation_result": result,
            })
            logger.warning(f"QUARANTINED output from {agent_name}: {result.get('summary', '')}")

        return result

    def _format_output_for_validation(self, agent_name: str, output: Dict[str, Any]) -> str:
        """Format agent output as text for LLM validation."""
        parts = [f"Agent: {agent_name}"]

        # Extract key text fields
        for key in ["title", "description", "reasoning", "summary", "analysis"]:
            if key in output and output[key]:
                parts.append(f"{key}: {output[key]}")

        # Include numerical claims
        for key, value in output.items():
            if isinstance(value, (int, float)) and key not in ("confidence", "timestamp"):
                parts.append(f"{key}: {value}")

        return "\n".join(parts)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM validation response."""
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            return {
                "is_valid": True,
                "confidence": 0.0,
                "issues": [],
                "summary": "Could not parse validation response",
            }

    def get_quarantined(self) -> List[Dict[str, Any]]:
        return list(self._quarantined)

    def clear_quarantine(self) -> int:
        count = len(self._quarantined)
        self._quarantined.clear()
        return count

    async def validate_batch(
        self,
        outputs: List[Dict[str, Any]],
        reference_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Validate multiple outputs concurrently."""
        tasks = [
            self.validate(
                agent_name=o.get("agent", "unknown"),
                output=o,
                reference_data=reference_data,
            )
            for o in outputs
        ]
        return await asyncio.gather(*tasks)
