import logging
from flask import Blueprint, jsonify, request
from services.drawdown_governor import (
    drawdown_governor,
    load_portfolio_equity,
    max_drawdown,
    log_governance_event
)
from services.uncertainty_state import (
    current_uncertainty_multiplier,
    get_uncertainty_status
)
from meta.capital_optimizer import capital_allocate, get_regime_allocation_summary
from services.council_weights import get_all_model_stats

logger = logging.getLogger(__name__)

bp = Blueprint("governor", __name__)


@bp.route("/api/governor/status", methods=["GET"])
def governor_status():
    """Get current portfolio governor status."""
    try:
        gov = drawdown_governor(dd_limit=-3.0)
        unc = get_uncertainty_status()
        
        return jsonify({
            "ok": True,
            "drawdown": {
                "current_dd": gov["dd"],
                "risk_multiplier": gov["risk_multiplier"],
                "halt": gov["halt"],
                "within_limits": gov["ok"]
            },
            "uncertainty": unc
        })
    except Exception as e:
        logger.error(f"Error getting governor status: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/governor/equity", methods=["GET"])
def equity_curve():
    """Get portfolio equity curve."""
    limit = request.args.get("limit", 500, type=int)
    
    try:
        curve = load_portfolio_equity(window_n=limit)
        dd = max_drawdown(curve) if curve else 0.0
        
        return jsonify({
            "ok": True,
            "curve": curve[-100:] if len(curve) > 100 else curve,
            "max_drawdown": dd,
            "points": len(curve)
        })
    except Exception as e:
        logger.error(f"Error loading equity curve: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/governor/allocate", methods=["POST"])
def compute_allocation():
    """
    Compute capital allocation given current state.
    
    Request:
        {
            "base_weights": {"agent1": 1.0, ...},
            "regime_weights": {"agent1": 0.8, ...},
            "total_notional": 100000
        }
    """
    data = request.get_json() or {}
    base_weights = data.get("base_weights", {})
    regime_weights = data.get("regime_weights", {})
    total_notional = data.get("total_notional", 100000.0)
    
    if not base_weights:
        return jsonify({"error": "base_weights required"}), 400
    
    try:
        gov = drawdown_governor(dd_limit=-3.0)
        unc_mult = current_uncertainty_multiplier()
        
        notional = capital_allocate(
            base_weights=base_weights,
            regime_weights=regime_weights,
            uncertainty_mult=unc_mult,
            drawdown_mult=gov["risk_multiplier"],
            total_notional=total_notional
        )
        
        summary = get_regime_allocation_summary(notional)
        
        return jsonify({
            "ok": True,
            "allocation": notional,
            "summary": summary,
            "multipliers": {
                "uncertainty": unc_mult,
                "drawdown": gov["risk_multiplier"]
            }
        })
    except Exception as e:
        logger.error(f"Error computing allocation: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/council/weights", methods=["GET"])
def council_model_weights():
    """Get LLM council model weights by regime."""
    try:
        stats = get_all_model_stats()
        return jsonify({
            "ok": True,
            "model_stats": stats
        })
    except Exception as e:
        logger.error(f"Error getting model weights: {e}")
        return jsonify({"error": str(e)}), 500
