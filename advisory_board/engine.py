"""
Advisory Board Engine — Multi-Agent Debate Orchestrator

Manages the flow of a board session:
1. User submits a corporate strategy or investment proposal
2. Each advisor independently analyzes the proposal (parallel)
3. Advisors respond to each other's critiques (cross-examination)
4. Board moderator synthesizes into a unified recommendation
5. Structured output: Barbell allocation, Black Swan checklist, Alpha signals
"""

import os
import json
import logging
import hashlib
from typing import Dict, List, Any, Optional, Generator
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from advisory_board.personas import ADVISORS, MODERATOR_PROMPT, get_advisor
from advisory_board.frameworks import (
    BarbellAnalyzer,
    BlackSwanScanner,
    AlphaExtractor,
    ConvexityMapper,
)

logger = logging.getLogger(__name__)

# LLM client initialization
try:
    import anthropic
    _anthropic_client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", "")
    )
except Exception:
    _anthropic_client = None
    logger.warning("Anthropic client not available for advisory board")

# Model configuration
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEBATE_MODEL = "claude-sonnet-4-20250514"
SYNTHESIS_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS_PER_ADVISOR = 2000
MAX_TOKENS_SYNTHESIS = 3000


def _call_llm(system_prompt: str, user_message: str,
              model: str = DEFAULT_MODEL,
              max_tokens: int = MAX_TOKENS_PER_ADVISOR) -> str:
    """Call Claude API with the given system prompt and user message."""
    from services.api_toggle import api_guard
    if not api_guard("anthropic", "Advisory Board LLM call"):
        return "[Advisory Board: Anthropic API is currently disabled via admin controls.]"

    if not _anthropic_client:
        return "[Error: Anthropic client not configured. Set ANTHROPIC_API_KEY.]"

    try:
        response = _anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text if response.content else ""
    except Exception as e:
        logger.error(f"Advisory Board LLM call failed: {e}")
        return f"[LLM Error: {str(e)[:200]}]"


class AdvisoryBoardEngine:
    """
    Orchestrates multi-agent advisory board sessions.

    Supports three modes:
    - INDIVIDUAL: Query a single advisor
    - PANEL: All four advisors respond independently
    - DEBATE: Full board session with cross-examination and synthesis
    """

    def __init__(self):
        self.sessions: Dict[str, Dict] = {}

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------
    def create_session(self, user_id: str = "anonymous") -> str:
        """Create a new advisory board session."""
        session_id = hashlib.sha256(
            f"{user_id}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        self.sessions[session_id] = {
            "id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "turns": [],
            "frameworks_applied": [],
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve a session by ID."""
        return self.sessions.get(session_id)

    # ------------------------------------------------------------------
    # Single Advisor Query
    # ------------------------------------------------------------------
    def ask_advisor(self, advisor_id: str, proposal: str,
                    session_id: str = None) -> Dict[str, Any]:
        """Get a single advisor's analysis of a proposal."""
        advisor = get_advisor(advisor_id)
        if not advisor:
            return {"error": f"Unknown advisor: {advisor_id}"}

        response_text = _call_llm(
            system_prompt=advisor["system_prompt"],
            user_message=f"Analyze this proposal:\n\n{proposal}",
        )

        result = {
            "advisor": advisor["name"],
            "advisor_id": advisor_id,
            "role": advisor["role"],
            "color": advisor["color"],
            "response": response_text,
            "expertise": advisor["expertise"],
            "timestamp": datetime.utcnow().isoformat(),
        }

        if session_id and session_id in self.sessions:
            self.sessions[session_id]["turns"].append({
                "type": "individual",
                "advisor": advisor_id,
                "proposal": proposal[:500],
                "result": result,
            })

        return result

    # ------------------------------------------------------------------
    # Full Panel (Parallel Responses)
    # ------------------------------------------------------------------
    def convene_panel(self, proposal: str, session_id: str = None,
                      advisors: List[str] = None) -> Dict[str, Any]:
        """
        Convene the full advisory panel — each advisor responds independently.
        Runs in parallel for speed.
        """
        advisor_ids = advisors or list(ADVISORS.keys())
        responses = {}
        errors = []

        # Run advisors in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.ask_advisor, aid, proposal, session_id): aid
                for aid in advisor_ids
            }
            for future in as_completed(futures):
                aid = futures[future]
                try:
                    responses[aid] = future.result()
                except Exception as e:
                    logger.error(f"Advisor {aid} failed: {e}")
                    errors.append({"advisor": aid, "error": str(e)})

        panel_result = {
            "type": "panel",
            "proposal": proposal,
            "responses": responses,
            "errors": errors,
            "advisor_count": len(responses),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return panel_result

    # ------------------------------------------------------------------
    # Full Debate (Multi-Round with Synthesis)
    # ------------------------------------------------------------------
    def run_debate(self, proposal: str, session_id: str = None,
                   include_frameworks: bool = True) -> Dict[str, Any]:
        """
        Full advisory board debate:
        1. Framework analysis (Barbell, Black Swan, Alpha, Convexity)
        2. Each advisor provides independent analysis
        3. Cross-examination round (advisors respond to each other)
        4. Board moderator synthesis

        Returns complete debate transcript and structured recommendations.
        """
        timestamp = datetime.utcnow().isoformat()

        # --- Phase 1: Framework Analysis ---
        frameworks = {}
        if include_frameworks:
            frameworks = {
                "barbell": BarbellAnalyzer.analyze(proposal),
                "black_swan": BlackSwanScanner.scan(proposal),
                "alpha": AlphaExtractor.extract(proposal),
                "convexity": ConvexityMapper.map_payoff(proposal),
            }

        # --- Phase 2: Independent Advisor Responses ---
        framework_context = ""
        if frameworks:
            framework_context = self._summarize_frameworks(frameworks)

        enriched_proposal = f"""{proposal}

---
FRAMEWORK ANALYSIS CONTEXT (for your reference):
{framework_context}""" if framework_context else proposal

        panel = self.convene_panel(enriched_proposal, session_id)
        advisor_responses = panel["responses"]

        # --- Phase 3: Cross-Examination ---
        cross_exam = self._cross_examine(proposal, advisor_responses)

        # --- Phase 4: Board Synthesis ---
        synthesis = self._synthesize(proposal, advisor_responses, cross_exam, frameworks)

        debate_result = {
            "type": "debate",
            "proposal": proposal,
            "timestamp": timestamp,
            "frameworks": frameworks,
            "advisor_responses": advisor_responses,
            "cross_examination": cross_exam,
            "synthesis": synthesis,
            "structured_output": self._build_structured_output(synthesis, frameworks),
        }

        if session_id and session_id in self.sessions:
            self.sessions[session_id]["turns"].append(debate_result)
            self.sessions[session_id]["frameworks_applied"] = list(frameworks.keys())

        return debate_result

    # ------------------------------------------------------------------
    # Cross-Examination Round
    # ------------------------------------------------------------------
    def _cross_examine(self, proposal: str,
                       advisor_responses: Dict[str, Dict]) -> Dict[str, str]:
        """Each advisor critiques the others' positions."""
        cross_exam = {}

        for advisor_id, advisor_data in ADVISORS.items():
            # Build the "other advisors said" context
            others_said = []
            for other_id, other_resp in advisor_responses.items():
                if other_id != advisor_id and "response" in other_resp:
                    others_said.append(
                        f"**{other_resp.get('advisor', other_id)}** said:\n"
                        f"{other_resp['response'][:800]}\n"
                    )

            if not others_said:
                continue

            cross_prompt = f"""The proposal under discussion:
{proposal[:500]}

Your fellow board members have weighed in. Here are their positions:

{'---'.join(others_said)}

---
Now respond to their analyses. Where do you AGREE? Where do you STRONGLY
DISAGREE? What critical risks or opportunities did they miss?
Be specific. Be yourself. Challenge weak reasoning."""

            cross_response = _call_llm(
                system_prompt=advisor_data["system_prompt"],
                user_message=cross_prompt,
                max_tokens=1500,
            )
            cross_exam[advisor_id] = cross_response

        return cross_exam

    # ------------------------------------------------------------------
    # Board Synthesis
    # ------------------------------------------------------------------
    def _synthesize(self, proposal: str, advisor_responses: Dict,
                    cross_exam: Dict, frameworks: Dict) -> str:
        """Moderator synthesizes all perspectives into a board recommendation."""
        # Build full context for the moderator
        advisor_summaries = []
        for aid, resp in advisor_responses.items():
            text = resp.get("response", "")[:1000]
            cross = cross_exam.get(aid, "")[:500]
            advisor_summaries.append(
                f"### {resp.get('advisor', aid)}\n"
                f"**Initial Position:**\n{text}\n\n"
                f"**Cross-Examination Response:**\n{cross}\n"
            )

        framework_summary = ""
        if frameworks:
            framework_summary = self._summarize_frameworks(frameworks)

        synthesis_prompt = f"""PROPOSAL UNDER REVIEW:
{proposal[:800]}

FRAMEWORK ANALYSIS:
{framework_summary}

ADVISOR POSITIONS AND CROSS-EXAMINATION:
{'---'.join(advisor_summaries)}

---
Synthesize the board's discussion into a unified recommendation.
Follow your output format exactly."""

        return _call_llm(
            system_prompt=MODERATOR_PROMPT,
            user_message=synthesis_prompt,
            model=SYNTHESIS_MODEL,
            max_tokens=MAX_TOKENS_SYNTHESIS,
        )

    # ------------------------------------------------------------------
    # Framework Summary Builder
    # ------------------------------------------------------------------
    def _summarize_frameworks(self, frameworks: Dict) -> str:
        """Create a concise summary of framework analyses for context injection."""
        parts = []

        if "barbell" in frameworks:
            bb = frameworks["barbell"]
            parts.append(
                "**Barbell Strategy:** Safety side focuses on "
                f"{len(bb.get('safety_side', {}).get('criteria', []))} criteria "
                f"(cash, debt, diversification). Upside side evaluates "
                f"{len(bb.get('upside_side', {}).get('criteria', []))} criteria "
                f"(asymmetric payoff, small bets, optionality)."
            )

        if "black_swan" in frameworks:
            bs = frameworks["black_swan"]
            categories = [c["name"] for c in bs.get("risk_categories", [])]
            parts.append(
                f"**Black Swan Scan:** {len(categories)} risk categories scanned: "
                f"{', '.join(categories[:4])}..."
            )

        if "alpha" in frameworks:
            al = frameworks["alpha"]
            signal_types = [s["name"] for s in al.get("signal_types", [])]
            parts.append(
                f"**Alpha Extraction:** {len(signal_types)} signal types evaluated: "
                f"{', '.join(signal_types)}."
            )

        if "convexity" in frameworks:
            parts.append(
                "**Convexity Map:** Evaluating payoff profiles for convex (antifragile), "
                "concave (fragile), and linear (robust) characteristics."
            )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Structured Output Builder
    # ------------------------------------------------------------------
    def _build_structured_output(self, synthesis: str,
                                 frameworks: Dict) -> Dict[str, Any]:
        """Build the final structured output from the debate."""
        return {
            "board_recommendation": synthesis,
            "frameworks_used": list(frameworks.keys()),
            "framework_details": {
                k: {
                    "framework_type": v.get("framework", k),
                    "timestamp": v.get("timestamp"),
                }
                for k, v in frameworks.items()
            },
            "decision_template": {
                "barbell_allocation": {
                    "safety_percentage": "85-90%",
                    "upside_percentage": "10-15%",
                },
                "risk_register": "See Black Swan scan output",
                "alpha_signals": "See Alpha extraction output",
                "convexity_score": "See Convexity mapping output",
            },
        }

    # ------------------------------------------------------------------
    # Streaming Support (for real-time UI)
    # ------------------------------------------------------------------
    def stream_debate(self, proposal: str,
                      session_id: str = None) -> Generator[Dict, None, None]:
        """
        Generator that yields debate events for real-time streaming to the UI.

        Events:
        - {"event": "phase", "phase": "frameworks", "data": ...}
        - {"event": "advisor_start", "advisor": "taleb"}
        - {"event": "advisor_complete", "advisor": "taleb", "response": ...}
        - {"event": "cross_exam_start"}
        - {"event": "cross_exam_complete", "data": ...}
        - {"event": "synthesis_start"}
        - {"event": "synthesis_complete", "data": ...}
        - {"event": "complete", "result": ...}
        """
        # Phase 1: Frameworks
        yield {"event": "phase", "phase": "frameworks",
               "message": "Running analytical frameworks..."}

        frameworks = {
            "barbell": BarbellAnalyzer.analyze(proposal),
            "black_swan": BlackSwanScanner.scan(proposal),
            "alpha": AlphaExtractor.extract(proposal),
            "convexity": ConvexityMapper.map_payoff(proposal),
        }
        yield {"event": "phase_complete", "phase": "frameworks",
               "data": {"frameworks_applied": list(frameworks.keys())}}

        # Phase 2: Individual Advisors
        framework_context = self._summarize_frameworks(frameworks)
        enriched = f"{proposal}\n\n---\nFRAMEWORK CONTEXT:\n{framework_context}"
        advisor_responses = {}

        for aid in ADVISORS:
            yield {"event": "advisor_start", "advisor": aid,
                   "name": ADVISORS[aid]["name"],
                   "message": f"{ADVISORS[aid]['name']} is analyzing..."}

            result = self.ask_advisor(aid, enriched, session_id)
            advisor_responses[aid] = result

            yield {"event": "advisor_complete", "advisor": aid,
                   "name": ADVISORS[aid]["name"],
                   "response": result}

        # Phase 3: Cross-Examination
        yield {"event": "phase", "phase": "cross_examination",
               "message": "Advisors are debating each other's positions..."}

        cross_exam = self._cross_examine(proposal, advisor_responses)

        yield {"event": "phase_complete", "phase": "cross_examination",
               "data": cross_exam}

        # Phase 4: Synthesis
        yield {"event": "phase", "phase": "synthesis",
               "message": "Board moderator is synthesizing recommendations..."}

        synthesis = self._synthesize(proposal, advisor_responses, cross_exam, frameworks)

        yield {"event": "phase_complete", "phase": "synthesis",
               "data": {"synthesis": synthesis}}

        # Complete
        full_result = {
            "type": "debate",
            "proposal": proposal,
            "timestamp": datetime.utcnow().isoformat(),
            "frameworks": frameworks,
            "advisor_responses": advisor_responses,
            "cross_examination": cross_exam,
            "synthesis": synthesis,
            "structured_output": self._build_structured_output(synthesis, frameworks),
        }

        yield {"event": "complete", "result": full_result}
