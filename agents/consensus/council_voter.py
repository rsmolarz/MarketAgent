"""
LLM Council Voter implementing Karpathy's three-stage pattern:

  Stage 1: All agents answer independently (fan-out).
  Stage 2: Each agent reviews anonymized peer responses.
  Stage 3: A chairman agent synthesizes the final decision.

This produces higher-quality consensus than simple majority voting by
incorporating cross-examination and synthesis steps.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from shared.state_schema import Direction, LLMOpinion

logger = logging.getLogger(__name__)


class LLMCouncilVoter:
    """
    Multi-LLM council that follows the three-stage Karpathy pattern.

    Each council member is an LLM client (OpenAI, Anthropic, Google)
    that independently analyzes a financial situation, then reviews peers,
    and finally a chairman synthesizes the result.
    """

    # Prompt templates for each stage
    STAGE1_PROMPT = """You are a financial analyst on an investment council. Analyze the following market data and provide your independent assessment.

Ticker: {ticker}
Asset Class: {asset_class}

Market Data:
{market_data}

Technical Analysis Summary:
{ta_summary}

Provide your assessment in the following JSON format:
{{
    "direction": "bullish" | "bearish" | "neutral",
    "confidence": 0.0 to 1.0,
    "reasoning": "Your detailed reasoning",
    "key_factors": ["factor1", "factor2", ...]
}}"""

    STAGE2_PROMPT = """You are a financial analyst reviewing peer assessments. Your own initial assessment was:

{own_assessment}

Here are anonymized peer assessments from other council members:

{peer_assessments}

After reviewing these perspectives, provide your revised assessment. You may change your opinion or strengthen it.

Provide your revised assessment in JSON format:
{{
    "direction": "bullish" | "bearish" | "neutral",
    "confidence": 0.0 to 1.0,
    "reasoning": "Your revised reasoning incorporating peer feedback",
    "changed_from_initial": true | false,
    "key_disagreements": ["any notable disagreements with peers"]
}}"""

    STAGE3_PROMPT = """You are the chairman of an investment council. You must synthesize all council members' final assessments into a single decision.

All council member assessments (after peer review):

{all_assessments}

Market Context:
{market_context}

As chairman, synthesize these views into a final council decision. Weight each member's input by their confidence and the quality of their reasoning.

Provide the council's final decision in JSON format:
{{
    "direction": "bullish" | "bearish" | "neutral",
    "confidence": 0.0 to 1.0,
    "reasoning": "Synthesized reasoning",
    "dissenting_views": ["any notable dissents"],
    "risk_factors": ["key risks to this assessment"],
    "vote_tally": {{"bullish": N, "bearish": N, "neutral": N}}
}}"""

    def __init__(self, llm_clients: Optional[Dict[str, Any]] = None):
        """
        Args:
            llm_clients: Dict mapping model name to callable LLM client.
                         Each client should accept (prompt: str) -> str.
                         If None, uses mock clients for testing.
        """
        self.llm_clients = llm_clients or {}
        self._stage1_results: Dict[str, Dict[str, Any]] = {}
        self._stage2_results: Dict[str, Dict[str, Any]] = {}
        self._stage3_result: Optional[Dict[str, Any]] = None

    async def _call_llm(self, model_name: str, prompt: str) -> str:
        """Call an LLM and return the response text."""
        client = self.llm_clients.get(model_name)
        if client is None:
            logger.warning(f"No LLM client for {model_name}, using mock response")
            return json.dumps({
                "direction": "neutral",
                "confidence": 0.5,
                "reasoning": f"Mock response from {model_name} - no client configured",
                "key_factors": [],
            })

        if asyncio.iscoroutinefunction(client):
            return await client(prompt)
        return client(prompt)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (```json and ```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            logger.error(f"Failed to parse LLM response as JSON: {text[:200]}")
            return {
                "direction": "neutral",
                "confidence": 0.3,
                "reasoning": f"Parse error. Raw: {text[:500]}",
            }

    async def stage1_independent_analysis(
        self,
        ticker: str,
        asset_class: str,
        market_data: Dict[str, Any],
        ta_summary: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Stage 1: All council members analyze independently in parallel.
        Returns dict mapping model_name -> assessment.
        """
        prompt = self.STAGE1_PROMPT.format(
            ticker=ticker,
            asset_class=asset_class,
            market_data=json.dumps(market_data, indent=2, default=str),
            ta_summary=json.dumps(ta_summary, indent=2, default=str),
        )

        tasks = {}
        for model_name in self.llm_clients:
            tasks[model_name] = self._call_llm(model_name, prompt)

        results = {}
        for model_name, coro in tasks.items():
            try:
                response = await coro
                results[model_name] = self._parse_llm_response(response)
                results[model_name]["model"] = model_name
            except Exception as e:
                logger.error(f"Stage 1 failed for {model_name}: {e}")
                results[model_name] = {
                    "direction": "neutral",
                    "confidence": 0.0,
                    "reasoning": f"Error: {e}",
                    "model": model_name,
                }

        self._stage1_results = results
        return results

    async def stage2_peer_review(self) -> Dict[str, Dict[str, Any]]:
        """
        Stage 2: Each member reviews anonymized peer responses.
        Returns dict mapping model_name -> revised assessment.
        """
        if not self._stage1_results:
            raise ValueError("Must run stage1 before stage2")

        tasks = {}
        for model_name, own_result in self._stage1_results.items():
            # Create anonymized peer assessments (exclude own)
            peers = []
            for i, (peer_name, peer_result) in enumerate(self._stage1_results.items()):
                if peer_name != model_name:
                    anonymized = {
                        "member": f"Analyst {i + 1}",
                        "direction": peer_result.get("direction", "neutral"),
                        "confidence": peer_result.get("confidence", 0.5),
                        "reasoning": peer_result.get("reasoning", ""),
                    }
                    peers.append(anonymized)

            prompt = self.STAGE2_PROMPT.format(
                own_assessment=json.dumps(own_result, indent=2, default=str),
                peer_assessments=json.dumps(peers, indent=2, default=str),
            )
            tasks[model_name] = self._call_llm(model_name, prompt)

        results = {}
        for model_name, coro in tasks.items():
            try:
                response = await coro
                results[model_name] = self._parse_llm_response(response)
                results[model_name]["model"] = model_name
            except Exception as e:
                logger.error(f"Stage 2 failed for {model_name}: {e}")
                # Fall back to stage 1 result
                results[model_name] = self._stage1_results[model_name]

        self._stage2_results = results
        return results

    async def stage3_chairman_synthesis(
        self,
        market_context: Dict[str, Any],
        chairman_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Stage 3: Chairman synthesizes all revised assessments.
        Returns the final council decision.
        """
        if not self._stage2_results:
            raise ValueError("Must run stage2 before stage3")

        # Pick chairman (first available or specified)
        if chairman_model and chairman_model in self.llm_clients:
            chair = chairman_model
        else:
            chair = next(iter(self.llm_clients), None)
            if chair is None:
                # No clients - return majority vote from stage 2
                return self._fallback_majority_vote()

        prompt = self.STAGE3_PROMPT.format(
            all_assessments=json.dumps(
                [
                    {"analyst": f"Member {i + 1}", **result}
                    for i, result in enumerate(self._stage2_results.values())
                ],
                indent=2,
                default=str,
            ),
            market_context=json.dumps(market_context, indent=2, default=str),
        )

        try:
            response = await self._call_llm(chair, prompt)
            result = self._parse_llm_response(response)
            result["chairman_model"] = chair
        except Exception as e:
            logger.error(f"Stage 3 chairman failed: {e}")
            result = self._fallback_majority_vote()

        self._stage3_result = result
        return result

    def _fallback_majority_vote(self) -> Dict[str, Any]:
        """Simple majority vote fallback when chairman fails."""
        source = self._stage2_results or self._stage1_results
        votes = {"bullish": 0, "bearish": 0, "neutral": 0}
        for result in source.values():
            direction = result.get("direction", "neutral")
            votes[direction] = votes.get(direction, 0) + 1

        winner = max(votes, key=votes.get)  # type: ignore
        total = sum(votes.values())
        return {
            "direction": winner,
            "confidence": votes[winner] / total if total > 0 else 0.0,
            "reasoning": "Fallback majority vote (chairman unavailable)",
            "vote_tally": votes,
        }

    async def run_full_council(
        self,
        ticker: str,
        asset_class: str,
        market_data: Dict[str, Any],
        ta_summary: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None,
        chairman_model: Optional[str] = None,
    ) -> List[LLMOpinion]:
        """
        Run the complete three-stage council process and return LLMOpinions.
        """
        # Stage 1: Independent analysis
        await self.stage1_independent_analysis(ticker, asset_class, market_data, ta_summary)

        # Stage 2: Peer review
        await self.stage2_peer_review()

        # Stage 3: Chairman synthesis
        final = await self.stage3_chairman_synthesis(
            market_context=market_context or {},
            chairman_model=chairman_model,
        )

        # Convert stage 2 results to LLMOpinions (these are the peer-reviewed opinions)
        opinions = []
        for model_name, result in self._stage2_results.items():
            direction_str = result.get("direction", "neutral").lower()
            try:
                direction = Direction(direction_str)
            except ValueError:
                direction = Direction.NEUTRAL

            opinions.append(LLMOpinion(
                agent_name=f"council_{model_name}",
                model=model_name,
                direction=direction,
                reasoning=result.get("reasoning", ""),
                confidence=float(result.get("confidence", 0.5)),
            ))

        # Add chairman's synthesis as a weighted opinion
        chair_direction_str = final.get("direction", "neutral").lower()
        try:
            chair_direction = Direction(chair_direction_str)
        except ValueError:
            chair_direction = Direction.NEUTRAL

        opinions.append(LLMOpinion(
            agent_name="council_chairman",
            model=final.get("chairman_model", "unknown"),
            direction=chair_direction,
            reasoning=final.get("reasoning", ""),
            confidence=float(final.get("confidence", 0.5)),
        ))

        return opinions

    def get_all_results(self) -> Dict[str, Any]:
        """Return all stage results for audit/debugging."""
        return {
            "stage1": self._stage1_results,
            "stage2": self._stage2_results,
            "stage3": self._stage3_result,
        }
