import logging
from flask import Blueprint, jsonify, request
from services.cluster_ensemble import (
    ensemble_cluster_votes,
    load_cluster_map,
    save_cluster_map,
    build_clusters_from_correlation
)
from services.thesis_compressor import (
    build_thesis_for_findings,
    fetch_recent_findings,
    compress_signals_for_symbol,
    compress_cluster_signals
)
from models import db

logger = logging.getLogger(__name__)

bp = Blueprint("ensemble", __name__)


@bp.route("/api/clusters", methods=["GET"])
def get_clusters():
    """Get current agent cluster assignments."""
    clusters = load_cluster_map()
    return jsonify({"ok": True, "clusters": clusters})


@bp.route("/api/clusters", methods=["POST"])
def update_clusters():
    """
    Update agent cluster assignments.
    
    Request:
        {"clusters": {"agent1": "cluster_a", "agent2": "cluster_a", ...}}
    """
    data = request.get_json() or {}
    clusters = data.get("clusters", {})
    
    if not isinstance(clusters, dict):
        return jsonify({"error": "clusters must be a dict"}), 400
    
    save_cluster_map(clusters)
    return jsonify({"ok": True, "clusters": clusters})


@bp.route("/api/clusters/vote", methods=["POST"])
def cluster_vote():
    """
    Run ensemble voting across agent clusters.
    
    Request:
        {
            "per_agent": {"agent1": {"vote": "ACT", "confidence": 0.8}, ...},
            "agent_weights": {"agent1": 1.2, ...}  # optional
        }
    
    Response:
        {"ok": true, "cluster_votes": {...}}
    """
    data = request.get_json() or {}
    per_agent = data.get("per_agent", {})
    agent_weights = data.get("agent_weights")
    
    if not per_agent:
        return jsonify({"error": "per_agent required"}), 400
    
    clusters = load_cluster_map()
    result = ensemble_cluster_votes(per_agent, clusters, agent_weights)
    
    return jsonify({
        "ok": True,
        "cluster_votes": result,
        "cluster_count": len(result)
    })


@bp.route("/api/thesis", methods=["GET"])
def get_thesis():
    """
    Get compressed thesis for recent findings.
    
    Query params:
        hours: lookback window (default 1)
        symbol: optional symbol filter
    """
    hours = request.args.get("hours", 1, type=int)
    symbol = request.args.get("symbol")
    
    try:
        findings = fetch_recent_findings(db.session, hours=hours, symbol=symbol)
        
        if not findings:
            return jsonify({
                "ok": True,
                "thesis": "No recent alerts to analyze.",
                "finding_count": 0
            })
        
        thesis = build_thesis_for_findings(findings)
        
        return jsonify({
            "ok": True,
            "thesis": thesis,
            "finding_count": len(findings),
            "symbol": symbol,
            "hours": hours
        })
    except Exception as e:
        logger.error(f"Error generating thesis: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/thesis/symbol/<symbol>", methods=["GET"])
def get_thesis_for_symbol(symbol: str):
    """Get compressed thesis for a specific symbol."""
    hours = request.args.get("hours", 1, type=int)
    
    try:
        result = compress_signals_for_symbol(db.session, symbol, hours=hours)
        return jsonify({"ok": True, **result})
    except Exception as e:
        logger.error(f"Error generating thesis for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/thesis/cluster", methods=["POST"])
def get_cluster_thesis():
    """
    Get compressed thesis for cluster-level votes.
    
    Request:
        {"cluster_votes": {...}}  # output from /api/clusters/vote
    """
    data = request.get_json() or {}
    cluster_votes = data.get("cluster_votes", {})
    
    if not cluster_votes:
        return jsonify({"error": "cluster_votes required"}), 400
    
    try:
        thesis = compress_cluster_signals(cluster_votes)
        return jsonify({
            "ok": True,
            "thesis": thesis,
            "cluster_count": len(cluster_votes)
        })
    except Exception as e:
        logger.error(f"Error generating cluster thesis: {e}")
        return jsonify({"error": str(e)}), 500
