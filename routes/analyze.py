"""
Analyze Route - LLM Council Entry Point

Provides combined TA + LLM scoring for findings analysis.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db, Finding, LLMCouncilResult
from services.llm_council import llm_council_analyze_finding
import logging

logger = logging.getLogger(__name__)

bp = Blueprint("analyze", __name__)


def ta_confirmation_score(symbol: str) -> dict:
    """Get TA confirmation score for a symbol."""
    from data_sources.price_loader import load_symbol_frame
    from ta.regime import classify_ta_regime
    
    if not symbol:
        return {"score": 0.5, "regime": "unknown", "direction": "neutral"}
    
    try:
        df = load_symbol_frame(symbol)
        if df is None or len(df) < 60:
            return {"score": 0.5, "regime": "unknown", "direction": "neutral"}
        
        ta = classify_ta_regime(df)
        
        if ta["ta_regime"] == "trend" and ta["trend_direction"] in ("up", "down"):
            return {
                "score": 0.85,
                "regime": ta["ta_regime"],
                "direction": ta["trend_direction"]
            }
        
        if ta["ta_regime"] == "mean_reversion":
            return {
                "score": 0.65,
                "regime": ta["ta_regime"],
                "direction": ta["trend_direction"]
            }
        
        return {
            "score": 0.4,
            "regime": ta["ta_regime"],
            "direction": ta["trend_direction"]
        }
        
    except Exception as e:
        logger.warning(f"TA confirmation error for {symbol}: {e}")
        return {"score": 0.5, "regime": "error", "direction": "neutral"}


@bp.route("/api/analyze", methods=["POST"])
def analyze_finding():
    """
    Analyze a finding with combined TA + LLM council scoring.
    
    Request:
        {"finding_id": int, "force": bool}
    
    Response:
        {"ok": bool, "confidence": float, "council": {...}, "ta": {...}}
    """
    data = request.get_json() or {}
    finding_id = data.get("finding_id")
    force = data.get("force", False)
    
    if not finding_id:
        return jsonify({"error": "finding_id required"}), 400

    finding = db.session.get(Finding, finding_id)
    if not finding:
        return jsonify({"error": "Finding not found"}), 404

    if finding.auto_analyzed and not force:
        return jsonify({
            "ok": True,
            "reason": "already_analyzed",
            "confidence": finding.consensus_confidence,
            "council": {
                "consensus": finding.consensus_action,
                "votes": finding.llm_votes,
                "disagreement": finding.llm_disagreement
            },
            "ta": {
                "regime": finding.ta_regime
            }
        })

    try:
        council = llm_council_analyze_finding(finding)
    except Exception as e:
        logger.error(f"LLM council error for finding {finding_id}: {e}")
        council = {
            "action": "WATCH",
            "confidence": 0.0,
            "votes": {},
            "disagreement": True,
            "agreement": 0.0,
            "uncertainty": 1.0,
            "analyses": {}
        }
    
    ta = ta_confirmation_score(finding.symbol)

    combined_confidence = round(
        0.65 * council.get("confidence", 0.5) +
        0.35 * ta["score"],
        4
    )

    finding.consensus_action = council.get("action", "WATCH")
    finding.consensus_confidence = combined_confidence
    finding.llm_votes = council.get("votes", {})
    finding.llm_disagreement = council.get("disagreement", False)
    finding.auto_analyzed = True
    finding.ta_regime = ta["regime"]
    finding.analyzed_at = datetime.utcnow()

    try:
        council_result = LLMCouncilResult(
            finding_id=finding.id,
            agent_name=finding.agent_name,
            consensus=council.get("action", "WATCH"),
            agreement=council.get("agreement", 0.5),
            uncertainty=council.get("uncertainty", 0.0),
            raw_votes=council.get("votes", {}),
            analyses=council.get("analyses", {}),
            confidence=combined_confidence,
            severity=finding.severity,
        )
        db.session.add(council_result)
    except Exception as e:
        logger.warning(f"Failed to persist council result: {e}")

    try:
        from routes.uncertainty import _record_uncertainty_event
        _record_uncertainty_event(
            label="llm_disagreement",
            score=council.get("uncertainty", 0.0),
            spike=council.get("disagreement", False),
            metadata={"votes": council.get("votes", {})}
        )
    except Exception as e:
        logger.debug(f"Uncertainty event tracking unavailable: {e}")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to commit analysis: {e}")
        return jsonify({"error": "Database commit failed"}), 500

    return jsonify({
        "ok": True,
        "confidence": combined_confidence,
        "council": {
            "consensus": council.get("action", "WATCH"),
            "votes": council.get("votes", {}),
            "disagreement": council.get("disagreement", False),
            "agreement": council.get("agreement", 0.5)
        },
        "ta": {
            "score": ta["score"],
            "regime": ta["regime"],
            "direction": ta["direction"]
        },
        "triple_confirmed": (
            (finding.severity or "").lower() == "critical" and
            council.get("action") == "ACT" and
            ta["score"] >= 0.7
        )
    })


@bp.route("/api/analyze/batch", methods=["POST"])
def analyze_batch():
    """
    Analyze multiple findings in batch.
    
    Request:
        {"finding_ids": [int], "force": bool}
    
    Response:
        {"ok": bool, "results": [...]}
    """
    data = request.get_json() or {}
    finding_ids = data.get("finding_ids", [])
    force = data.get("force", False)
    
    if not finding_ids:
        return jsonify({"error": "finding_ids required"}), 400
    
    if len(finding_ids) > 50:
        return jsonify({"error": "Maximum 50 findings per batch"}), 400
    
    results = []
    for fid in finding_ids:
        try:
            finding = db.session.get(Finding, fid)
            if not finding:
                results.append({"finding_id": fid, "ok": False, "reason": "not_found"})
                continue
            
            if finding.auto_analyzed and not force:
                results.append({
                    "finding_id": fid,
                    "ok": True,
                    "reason": "already_analyzed",
                    "confidence": finding.consensus_confidence
                })
                continue
            
            council = llm_council_analyze_finding(finding)
            ta = ta_confirmation_score(finding.symbol)
            
            combined = round(0.65 * council.get("confidence", 0.5) + 0.35 * ta["score"], 4)
            
            finding.consensus_action = council.get("action", "WATCH")
            finding.consensus_confidence = combined
            finding.llm_votes = council.get("votes", {})
            finding.llm_disagreement = council.get("disagreement", False)
            finding.auto_analyzed = True
            finding.ta_regime = ta["regime"]
            finding.analyzed_at = datetime.utcnow()
            
            results.append({
                "finding_id": fid,
                "ok": True,
                "confidence": combined,
                "consensus": council.get("action", "WATCH")
            })
            
        except Exception as e:
            logger.error(f"Batch analysis error for {fid}: {e}")
            results.append({"finding_id": fid, "ok": False, "reason": str(e)})
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Batch commit failed: {e}"}), 500
    
    return jsonify({"ok": True, "results": results})
