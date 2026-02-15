"""
Council Protocol: Ensemble Reasoning Pipeline for the Antifragile Board

Implements the three-stage deliberation process:
1. DIVERGENCE: Parallel independent analysis from all advisors
2. CONVERGENCE: Anonymous peer review and adversarial critique
3. SYNTHESIS: Chairman aggregation into a definitive recommendation

This is a deterministic linear DAG (not a cyclical autonomous agent),
designed for cognitive vetting rather than task execution.
"""

import os
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from antifragile.prompts import (
    TALEB_SYSTEM_PROMPT,
    SPITZNAGEL_SYSTEM_PROMPT,
    SIMONS_SYSTEM_PROMPT,
    ASNESS_SYSTEM_PROMPT,
    CHAIRMAN_SYSTEM_PROMPT,
    PEER_REVIEW_PROMPT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM Adapter
# ---------------------------------------------------------------------------

def _get_llm_client():
    """Get the best available LLM client."""
    # Try Anthropic first (Claude is better for nuanced reasoning)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return "anthropic", api_key

    # Fall back to OpenAI
    api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    if api_key:
        return "openai", (api_key, base_url)

    # Fall back to Gemini
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return "gemini", api_key

    return None, None


def _call_llm(system_prompt: str, user_message: str, temperature: float = 0.3) -> str:
    """Call the available LLM with system and user prompts."""
    provider, credentials = _get_llm_client()

    if provider == "anthropic":
        return _call_anthropic(system_prompt, user_message, credentials, temperature)
    elif provider == "openai":
        api_key, base_url = credentials
        return _call_openai(system_prompt, user_message, api_key, base_url, temperature)
    elif provider == "gemini":
        return _call_gemini(system_prompt, user_message, credentials, temperature)
    else:
        return "[LLM unavailable - no API keys configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY.]"


def _call_anthropic(system: str, user: str, api_key: str, temperature: float) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=os.environ.get("ANTIFRAGILE_CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=2000,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text if response.content else ""
    except Exception as e:
        logger.error(f"Anthropic call failed: {e}")
        return f"[Anthropic error: {e}]"


def _call_openai(system: str, user: str, api_key: str, base_url: Optional[str], temperature: float) -> str:
    try:
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        response = client.chat.completions.create(
            model=os.environ.get("ANTIFRAGILE_OPENAI_MODEL", "gpt-4o"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2000,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"OpenAI call failed: {e}")
        return f"[OpenAI error: {e}]"


def _call_gemini(system: str, user: str, api_key: str, temperature: float) -> str:
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        combined = f"SYSTEM:\n{system}\n\nUSER:\n{user}"
        response = client.models.generate_content(
            model=os.environ.get("ANTIFRAGILE_GEMINI_MODEL", "gemini-2.5-flash"),
            contents=combined,
        )
        return response.text or ""
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        return f"[Gemini error: {e}]"


# ---------------------------------------------------------------------------
# Advisor Definitions
# ---------------------------------------------------------------------------

ADVISORS = {
    "taleb": {
        "name": "Nassim Taleb",
        "title": "Epistemologist of Risk",
        "system_prompt": TALEB_SYSTEM_PROMPT,
        "focus": "fragility, Black Swans, survival, skin in the game",
    },
    "spitznagel": {
        "name": "Mark Spitznagel",
        "title": "Safe Haven Practitioner",
        "system_prompt": SPITZNAGEL_SYSTEM_PROMPT,
        "focus": "convexity, geometric returns, drawdown protection",
    },
    "simons": {
        "name": "Jim Simons",
        "title": "High-Frequency Quant",
        "system_prompt": SIMONS_SYSTEM_PROMPT,
        "focus": "statistical patterns, data-driven signals, market neutrality",
    },
    "asness": {
        "name": "Cliff Asness",
        "title": "Disciplined Contrarian",
        "system_prompt": ASNESS_SYSTEM_PROMPT,
        "focus": "Value/Momentum factors, behavioral biases, systematic discipline",
    },
}


# ---------------------------------------------------------------------------
# Council Protocol Implementation
# ---------------------------------------------------------------------------

class CouncilProtocol:
    """
    The three-stage ensemble reasoning pipeline:
    Divergence -> Convergence -> Synthesis
    """

    def __init__(self, parallel: bool = True, enable_peer_review: bool = True):
        """
        Args:
            parallel: Run divergence phase in parallel (True) or sequential (False)
            enable_peer_review: Enable the convergence (peer review) phase
        """
        self.parallel = parallel
        self.enable_peer_review = enable_peer_review

    def deliberate(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        selected_advisors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full Council Protocol deliberation.

        Args:
            query: The investment thesis, business model, or strategic question
            context: Optional market data, financial metrics, etc.
            selected_advisors: Which advisors to include (default: all)

        Returns:
            Complete deliberation results with all phases
        """
        start_time = datetime.utcnow()
        advisors = selected_advisors or list(ADVISORS.keys())

        # Build context string for advisors
        context_str = self._format_context(context) if context else ""
        full_query = f"{query}\n\n{context_str}" if context_str else query

        # Phase 1: Divergence
        logger.info(f"Council Protocol: Starting divergence phase with {len(advisors)} advisors")
        opinions = self._divergence_phase(full_query, advisors)

        # Phase 2: Convergence (Peer Review)
        critiques = {}
        if self.enable_peer_review and len(opinions) > 1:
            logger.info("Council Protocol: Starting convergence phase (peer review)")
            critiques = self._convergence_phase(full_query, opinions, advisors)

        # Phase 3: Synthesis
        logger.info("Council Protocol: Starting synthesis phase (Chairman)")
        synthesis = self._synthesis_phase(full_query, opinions, critiques)

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        return {
            "query": query,
            "timestamp": start_time.isoformat(),
            "elapsed_seconds": round(elapsed, 1),
            "advisors_consulted": advisors,
            "phases": {
                "divergence": opinions,
                "convergence": critiques,
                "synthesis": synthesis,
            },
            "final_recommendation": synthesis,
        }

    def _divergence_phase(
        self, query: str, advisors: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Phase 1: Fan-Out - Each advisor generates an independent opinion.
        """
        opinions = {}

        if self.parallel:
            with ThreadPoolExecutor(max_workers=len(advisors)) as executor:
                futures = {}
                for advisor_id in advisors:
                    if advisor_id not in ADVISORS:
                        continue
                    advisor = ADVISORS[advisor_id]
                    future = executor.submit(
                        _call_llm, advisor["system_prompt"], query
                    )
                    futures[future] = advisor_id

                for future in as_completed(futures):
                    advisor_id = futures[future]
                    try:
                        response = future.result()
                        opinions[advisor_id] = {
                            "advisor": ADVISORS[advisor_id]["name"],
                            "title": ADVISORS[advisor_id]["title"],
                            "focus": ADVISORS[advisor_id]["focus"],
                            "analysis": response,
                        }
                    except Exception as e:
                        logger.error(f"Advisor {advisor_id} failed: {e}")
                        opinions[advisor_id] = {
                            "advisor": ADVISORS[advisor_id]["name"],
                            "title": ADVISORS[advisor_id]["title"],
                            "focus": ADVISORS[advisor_id]["focus"],
                            "analysis": f"[Analysis failed: {e}]",
                        }
        else:
            for advisor_id in advisors:
                if advisor_id not in ADVISORS:
                    continue
                advisor = ADVISORS[advisor_id]
                try:
                    response = _call_llm(advisor["system_prompt"], query)
                    opinions[advisor_id] = {
                        "advisor": advisor["name"],
                        "title": advisor["title"],
                        "focus": advisor["focus"],
                        "analysis": response,
                    }
                except Exception as e:
                    logger.error(f"Advisor {advisor_id} failed: {e}")
                    opinions[advisor_id] = {
                        "advisor": advisor["name"],
                        "title": advisor["title"],
                        "focus": advisor["focus"],
                        "analysis": f"[Analysis failed: {e}]",
                    }

        return opinions

    def _convergence_phase(
        self, query: str, opinions: Dict[str, Dict[str, Any]], advisors: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Phase 2: Anonymous Peer Review - Each advisor critiques the others.
        Responses are anonymized to prevent bias.
        """
        critiques = {}

        # Build anonymized opinion summaries
        anonymized = {}
        for i, (advisor_id, opinion) in enumerate(opinions.items()):
            # Use anonymous labels
            anon_label = f"Advisor_{chr(65 + i)}"  # A, B, C, D
            anonymized[anon_label] = {
                "real_id": advisor_id,
                "analysis": opinion["analysis"],
            }

        # Each advisor reviews the others
        for reviewer_id in advisors:
            if reviewer_id not in opinions:
                continue

            other_analyses = []
            for anon_label, anon_data in anonymized.items():
                if anon_data["real_id"] != reviewer_id:
                    other_analyses.append(
                        f"--- {anon_label} ---\n{anon_data['analysis']}\n"
                    )

            if not other_analyses:
                continue

            review_prompt = (
                f"ORIGINAL QUERY:\n{query}\n\n"
                f"ANALYSES TO REVIEW:\n{''.join(other_analyses)}\n\n"
                f"Provide your peer review of these analyses."
            )

            try:
                review = _call_llm(
                    f"{ADVISORS[reviewer_id]['system_prompt']}\n\n{PEER_REVIEW_PROMPT}",
                    review_prompt,
                )
                critiques[reviewer_id] = {
                    "reviewer": ADVISORS[reviewer_id]["name"],
                    "critique": review,
                }
            except Exception as e:
                logger.error(f"Peer review by {reviewer_id} failed: {e}")
                critiques[reviewer_id] = {
                    "reviewer": ADVISORS[reviewer_id]["name"],
                    "critique": f"[Review failed: {e}]",
                }

        return critiques

    def _synthesis_phase(
        self,
        query: str,
        opinions: Dict[str, Dict[str, Any]],
        critiques: Dict[str, Dict[str, Any]],
    ) -> str:
        """
        Phase 3: Chairman Synthesis - Map-Reduce advisory intelligence
        into a definitive recommendation.
        """
        # Build the full context for the Chairman
        synthesis_input = f"ORIGINAL QUERY:\n{query}\n\n"
        synthesis_input += "=" * 60 + "\nADVISOR OPINIONS:\n" + "=" * 60 + "\n\n"

        for advisor_id, opinion in opinions.items():
            synthesis_input += (
                f"--- {opinion['advisor']} ({opinion['title']}) ---\n"
                f"Focus: {opinion['focus']}\n"
                f"Analysis:\n{opinion['analysis']}\n\n"
            )

        if critiques:
            synthesis_input += "=" * 60 + "\nPEER REVIEW CRITIQUES:\n" + "=" * 60 + "\n\n"
            for reviewer_id, critique in critiques.items():
                synthesis_input += (
                    f"--- Critique by {critique['reviewer']} ---\n"
                    f"{critique['critique']}\n\n"
                )

        synthesis_input += (
            "=" * 60 + "\n"
            "Based on the above advisor opinions and peer review critiques, "
            "provide your Chairman synthesis and final recommendation.\n"
        )

        try:
            return _call_llm(CHAIRMAN_SYSTEM_PROMPT, synthesis_input, temperature=0.2)
        except Exception as e:
            logger.error(f"Chairman synthesis failed: {e}")
            return f"[Synthesis failed: {e}]"

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format market data context for advisor consumption."""
        parts = ["MARKET DATA CONTEXT:"]

        if "market_data" in context:
            parts.append("\nMarket Snapshot:")
            for k, v in context["market_data"].items():
                parts.append(f"  {k}: {v}")

        if "financial_metrics" in context:
            parts.append("\nFinancial Metrics:")
            for k, v in context["financial_metrics"].items():
                parts.append(f"  {k}: {v}")

        if "fragility_score" in context:
            parts.append(f"\nFragility Score: {context['fragility_score']}")

        if "ambiguity_score" in context:
            parts.append(f"\nStrategic Ambiguity Score: {context['ambiguity_score']}")

        if "factor_analysis" in context:
            parts.append("\nFactor Analysis:")
            for k, v in context["factor_analysis"].items():
                parts.append(f"  {k}: {v}")

        if "pattern_signals" in context:
            parts.append("\nPattern Signals:")
            for k, v in context["pattern_signals"].items():
                parts.append(f"  {k}: {v}")

        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Quick deliberation (simplified for API use)
# ---------------------------------------------------------------------------

def quick_deliberate(
    query: str,
    context: Optional[Dict[str, Any]] = None,
    advisors: Optional[List[str]] = None,
    peer_review: bool = False,
) -> Dict[str, Any]:
    """
    Convenience function for running a council deliberation.

    Args:
        query: The question or thesis to evaluate
        context: Optional market/financial context
        advisors: Which advisors to consult (default: all four)
        peer_review: Enable peer review phase (slower but more thorough)

    Returns:
        Full deliberation results
    """
    council = CouncilProtocol(parallel=True, enable_peer_review=peer_review)
    return council.deliberate(query, context, advisors)
