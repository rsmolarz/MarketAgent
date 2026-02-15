"""
Flask Routes for the Antifragile Board of Advisors

Provides both API endpoints and HTML dashboard for the boardroom.
"""

import logging
import json
from flask import Blueprint, jsonify, request, render_template

from antifragile.council import CouncilProtocol, quick_deliberate, ADVISORS
from antifragile.tools import (
    FragilityScorer,
    GeometricSimulator,
    PatternDetector,
    FactorAnalyzer,
    AmbiguityScorer,
)
from antifragile.agents import (
    TalebFragilityAgent,
    SpitznagelSafeHavenAgent,
    SimonsPatternAgent,
    AssnessFactorAgent,
    AntifragileBoardAgent,
)

logger = logging.getLogger(__name__)

antifragile_bp = Blueprint("antifragile", __name__)


# ---------------------------------------------------------------------------
# Dashboard UI
# ---------------------------------------------------------------------------

@antifragile_bp.route("/antifragile")
def antifragile_dashboard():
    """Render the Antifragile Board dashboard."""
    return render_template("antifragile_board.html")


# ---------------------------------------------------------------------------
# Council Protocol API
# ---------------------------------------------------------------------------

@antifragile_bp.route("/api/antifragile/deliberate", methods=["POST"])
def deliberate():
    """
    Run a full Council Protocol deliberation.

    Request:
        {
            "query": "Should we invest in AI infrastructure?",
            "advisors": ["taleb", "spitznagel", "simons", "asness"],  // optional
            "peer_review": false,  // optional, default false
            "context": {}  // optional market data context
        }

    Response:
        Full deliberation results with all phases
    """
    data = request.get_json() or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "query is required"}), 400

    advisors = data.get("advisors")
    peer_review = data.get("peer_review", False)
    context = data.get("context")

    # Validate advisor names
    if advisors:
        valid = [a for a in advisors if a in ADVISORS]
        if not valid:
            return jsonify({
                "error": f"No valid advisors. Choose from: {list(ADVISORS.keys())}"
            }), 400
        advisors = valid

    try:
        result = quick_deliberate(
            query=query,
            context=context,
            advisors=advisors,
            peer_review=peer_review,
        )
        return jsonify({"ok": True, **result})
    except Exception as e:
        logger.error(f"Deliberation failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@antifragile_bp.route("/api/antifragile/advisors", methods=["GET"])
def list_advisors():
    """List available board advisors and their focus areas."""
    return jsonify({
        "ok": True,
        "advisors": {
            k: {"name": v["name"], "title": v["title"], "focus": v["focus"]}
            for k, v in ADVISORS.items()
        },
    })


# ---------------------------------------------------------------------------
# Specialist Agent APIs
# ---------------------------------------------------------------------------

@antifragile_bp.route("/api/antifragile/scan", methods=["POST"])
def run_scan():
    """
    Run specialist agent scans (non-LLM, data-driven analysis).

    Request:
        {"agents": ["taleb", "spitznagel", "simons", "asness"]}  // optional, default all

    Response:
        Findings from selected specialist agents
    """
    data = request.get_json() or {}
    selected = data.get("agents", ["taleb", "spitznagel", "simons", "asness"])

    agent_map = {
        "taleb": TalebFragilityAgent,
        "spitznagel": SpitznagelSafeHavenAgent,
        "simons": SimonsPatternAgent,
        "asness": AssnessFactorAgent,
    }

    all_findings = {}
    for agent_id in selected:
        if agent_id not in agent_map:
            continue
        try:
            agent = agent_map[agent_id]()
            findings = agent.analyze()
            all_findings[agent_id] = findings
        except Exception as e:
            logger.error(f"Agent {agent_id} scan failed: {e}")
            all_findings[agent_id] = [{"error": str(e)}]

    total = sum(len(f) for f in all_findings.values())
    return jsonify({
        "ok": True,
        "total_findings": total,
        "findings": all_findings,
    })


# ---------------------------------------------------------------------------
# Tool APIs
# ---------------------------------------------------------------------------

@antifragile_bp.route("/api/antifragile/tools/fragility", methods=["POST"])
def fragility_score():
    """
    Compute a fragility score for a business/strategy.

    Request:
        {
            "leverage_ratio": 1.5,
            "concentration_pct": 0.4,
            "years_of_operation": 3,
            "has_skin_in_game": true,
            "relies_on_forecasting": false,
            "revenue_sources": 2,
            "debt_to_equity": 0.8,
            "tail_exposure": "neutral"
        }
    """
    data = request.get_json() or {}
    try:
        result = FragilityScorer.score_fragility(**data)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@antifragile_bp.route("/api/antifragile/tools/bernoulli", methods=["POST"])
def bernoulli_falls():
    """
    Calculate Bernoulli Falls (drawdown recovery math).

    Request:
        {"drawdown_pct": 0.50}
    """
    data = request.get_json() or {}
    drawdown = data.get("drawdown_pct", 0)
    try:
        result = GeometricSimulator.bernoulli_falls(drawdown)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@antifragile_bp.route("/api/antifragile/tools/safe-haven", methods=["POST"])
def safe_haven_sim():
    """
    Run Safe Haven Frontier Monte Carlo simulation.

    Request:
        {
            "portfolio_return": 0.08,
            "portfolio_vol": 0.16,
            "haven_allocation": 0.03,
            "crash_probability": 0.05,
            "crash_severity": -0.40
        }
    """
    data = request.get_json() or {}
    try:
        result = GeometricSimulator.safe_haven_frontier(**data)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@antifragile_bp.route("/api/antifragile/tools/ambiguity", methods=["POST"])
def ambiguity_score():
    """
    Score text for strategic ambiguity.

    Request:
        {"text": "We expect to potentially see growth going forward..."}
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        result = AmbiguityScorer.score_text(text)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@antifragile_bp.route("/api/antifragile/tools/lindy", methods=["POST"])
def lindy_check():
    """
    Apply the Lindy Effect to a concept/strategy.

    Request:
        {"concept": "Value Investing", "years_existed": 90}
    """
    data = request.get_json() or {}
    concept = data.get("concept", "")
    years = data.get("years_existed", 0)

    if not concept:
        return jsonify({"error": "concept is required"}), 400

    try:
        result = FragilityScorer.lindy_check(concept, years)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
