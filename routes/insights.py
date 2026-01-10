"""
Insights API endpoints for dashboard panels.

Provides:
- Risk Governor state
- IC Memo (compressed thesis)
- Agent vs SPY by regime
- Agent list
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

bp = Blueprint("insights", __name__)


@bp.route("/api/governor_state")
def governor_state():
    """
    Live portfolio drawdown governor state.
    """
    try:
        from services.drawdown_governor import compute_drawdown_state
        g = compute_drawdown_state()
        return jsonify({
            "ok": True,
            "dd": g.get("dd", 0),
            "dd_limit": g.get("dd_limit", -0.06),
            "risk_multiplier": g.get("risk_multiplier", 1.0),
            "cadence_multiplier": g.get("cadence_multiplier", 1.0),
            "block_new_act": g.get("block_new_act", False),
            "reason": g.get("reason", "unknown"),
            "ts": datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Governor state error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "dd": 0,
            "dd_limit": -0.06,
            "risk_multiplier": 1.0,
            "cadence_multiplier": 1.0,
            "block_new_act": False,
            "reason": "error"
        })


@bp.route("/api/ic_memo/latest")
def ic_memo_latest():
    """
    IC memo = compressed thesis built from recent findings.
    """
    try:
        from services.ic_memo import build_ic_memo
        hours = int(request.args.get("hours", "24"))
        memo = build_ic_memo(hours=hours)
        return jsonify({"ok": True, **memo})
    except Exception as e:
        logger.error(f"IC memo error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
            "headline": "Error loading memo",
            "thesis": str(e),
            "bullets": []
        })


@bp.route("/api/agents/list")
def agents_list():
    """List all agents."""
    try:
        from models import AgentStatus
        statuses = AgentStatus.query.order_by(AgentStatus.agent_name.asc()).all()
        names = [s.agent_name for s in statuses] if statuses else []
        return jsonify({"ok": True, "agents": names})
    except Exception as e:
        logger.error(f"Agents list error: {e}")
        return jsonify({"ok": False, "agents": [], "error": str(e)})


@bp.route("/api/eval/agent_vs_spy")
def agent_vs_spy():
    """
    Backtest agent vs SPY by regime.
    """
    agent = request.args.get("agent")
    if not agent:
        return jsonify({"ok": False, "error": "agent required"}), 400
    
    try:
        from backtests.agent_vs_spy_by_regime import backtest_agent_vs_spy_by_regime
        res = backtest_agent_vs_spy_by_regime(agent_name=agent)
        
        if not res.get("ok", False) and res.get("by_regime") is not None:
            res["ok"] = True
        
        if res.get("by_regime"):
            for row in res["by_regime"]:
                row["agent_days"] = row.get("count", 0)
                row["agent_mean"] = row.get("mean_return", 0)
                row["spy_mean"] = row.get("spy_baseline", 0)
                row["agent_alpha_mean"] = row.get("alpha_vs_spy", 0)
        
        return jsonify(res)
    except Exception as e:
        logger.error(f"Agent vs SPY error: {e}")
        return jsonify({"ok": False, "error": str(e), "by_regime": []})
