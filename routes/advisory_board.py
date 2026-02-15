"""
Advisory Board Routes — Flask Blueprint

Provides endpoints for the AI Advisory Board multi-agent debate system.
"""

import json
import logging
from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context

from advisory_board.engine import AdvisoryBoardEngine
from advisory_board.personas import ADVISORS
from advisory_board.frameworks import (
    BarbellAnalyzer,
    BlackSwanScanner,
    AlphaExtractor,
    ConvexityMapper,
)

logger = logging.getLogger(__name__)

advisory_board_bp = Blueprint(
    "advisory_board",
    __name__,
    template_folder="../templates",
)

# Singleton engine instance
_engine = AdvisoryBoardEngine()


# --------------------------------------------------------------------------
# Page Routes
# --------------------------------------------------------------------------
@advisory_board_bp.route("/advisory-board")
def advisory_board_page():
    """Render the Advisory Board chat interface."""
    return render_template("advisory_board.html", advisors=ADVISORS)


# --------------------------------------------------------------------------
# API: Session Management
# --------------------------------------------------------------------------
@advisory_board_bp.route("/api/advisory-board/session", methods=["POST"])
def create_session():
    """Create a new advisory board session."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", "anonymous")
    session_id = _engine.create_session(user_id)
    return jsonify({"session_id": session_id})


# --------------------------------------------------------------------------
# API: Single Advisor Query
# --------------------------------------------------------------------------
@advisory_board_bp.route("/api/advisory-board/ask", methods=["POST"])
def ask_advisor():
    """Query a single advisor."""
    data = request.get_json(silent=True) or {}
    advisor_id = data.get("advisor_id")
    proposal = data.get("proposal", "").strip()
    session_id = data.get("session_id")

    if not advisor_id or not proposal:
        return jsonify({"error": "advisor_id and proposal are required"}), 400

    if advisor_id not in ADVISORS:
        return jsonify({"error": f"Unknown advisor: {advisor_id}",
                         "available": list(ADVISORS.keys())}), 400

    result = _engine.ask_advisor(advisor_id, proposal, session_id)
    return jsonify(result)


# --------------------------------------------------------------------------
# API: Full Panel (All Advisors)
# --------------------------------------------------------------------------
@advisory_board_bp.route("/api/advisory-board/panel", methods=["POST"])
def convene_panel():
    """Convene the full advisory panel — all advisors respond independently."""
    data = request.get_json(silent=True) or {}
    proposal = data.get("proposal", "").strip()
    session_id = data.get("session_id")
    selected_advisors = data.get("advisors")  # optional subset

    if not proposal:
        return jsonify({"error": "proposal is required"}), 400

    result = _engine.convene_panel(proposal, session_id, selected_advisors)
    return jsonify(result)


# --------------------------------------------------------------------------
# API: Full Debate (Multi-Round with Synthesis)
# --------------------------------------------------------------------------
@advisory_board_bp.route("/api/advisory-board/debate", methods=["POST"])
def run_debate():
    """Run a full advisory board debate with cross-examination and synthesis."""
    data = request.get_json(silent=True) or {}
    proposal = data.get("proposal", "").strip()
    session_id = data.get("session_id")
    include_frameworks = data.get("include_frameworks", True)

    if not proposal:
        return jsonify({"error": "proposal is required"}), 400

    result = _engine.run_debate(proposal, session_id, include_frameworks)
    return jsonify(result)


# --------------------------------------------------------------------------
# API: Streaming Debate (Server-Sent Events)
# --------------------------------------------------------------------------
@advisory_board_bp.route("/api/advisory-board/debate/stream", methods=["POST"])
def stream_debate():
    """Stream a debate using Server-Sent Events for real-time UI updates."""
    data = request.get_json(silent=True) or {}
    proposal = data.get("proposal", "").strip()
    session_id = data.get("session_id")

    if not proposal:
        return jsonify({"error": "proposal is required"}), 400

    def generate():
        for event in _engine.stream_debate(proposal, session_id):
            yield f"data: {json.dumps(event)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# --------------------------------------------------------------------------
# API: Framework Analysis (Standalone)
# --------------------------------------------------------------------------
@advisory_board_bp.route("/api/advisory-board/frameworks", methods=["POST"])
def run_frameworks():
    """Run analytical frameworks independently."""
    data = request.get_json(silent=True) or {}
    proposal = data.get("proposal", "").strip()
    frameworks_requested = data.get("frameworks", ["barbell", "black_swan", "alpha", "convexity"])

    if not proposal:
        return jsonify({"error": "proposal is required"}), 400

    results = {}
    framework_map = {
        "barbell": lambda p: BarbellAnalyzer.analyze(p),
        "black_swan": lambda p: BlackSwanScanner.scan(p),
        "alpha": lambda p: AlphaExtractor.extract(p),
        "convexity": lambda p: ConvexityMapper.map_payoff(p),
    }

    for fw_name in frameworks_requested:
        if fw_name in framework_map:
            results[fw_name] = framework_map[fw_name](proposal)

    return jsonify({"frameworks": results})


# --------------------------------------------------------------------------
# API: List Advisors
# --------------------------------------------------------------------------
@advisory_board_bp.route("/api/advisory-board/advisors", methods=["GET"])
def list_advisors():
    """List available advisors with their metadata."""
    advisor_list = []
    for aid, data in ADVISORS.items():
        advisor_list.append({
            "id": aid,
            "name": data["name"],
            "role": data["role"],
            "color": data["color"],
            "expertise": data["expertise"],
            "bias": data["bias"],
        })
    return jsonify({"advisors": advisor_list})
