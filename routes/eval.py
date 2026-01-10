"""
Evaluation Routes

Provides endpoints for backtesting, signal compression, and evaluation.
"""
from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

bp = Blueprint("eval", __name__)


@bp.route("/api/eval/agent_vs_spy", methods=["GET"])
def api_agent_vs_spy():
    """
    Backtest an agent's signals against SPY by regime.
    
    Query params:
        agent: Agent name (required)
        lookahead: Forward return days (default: 1)
    
    Returns:
        Hit rates, returns, and alpha by regime
    """
    from backtests.agent_vs_spy_by_regime import backtest_agent_vs_spy_by_regime
    
    agent = request.args.get("agent")
    lookahead = int(request.args.get("lookahead", "1"))
    
    if not agent:
        return jsonify({"error": "agent is required"}), 400
    
    try:
        res = backtest_agent_vs_spy_by_regime(
            agent_name=agent,
            lookahead_days=lookahead
        )
        return jsonify(res)
    except Exception as e:
        logger.error(f"Agent vs SPY backtest failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/eval/compression", methods=["GET"])
def api_signal_compression():
    """
    Get compressed signal theses preview.
    
    Query params:
        hours: Lookback period (default: 24)
    
    Returns:
        Compressed theses and memo preview
    """
    from services.ic_memo_email import get_compressed_memo_preview
    
    hours = int(request.args.get("hours", "24"))
    
    try:
        res = get_compressed_memo_preview(hours=hours)
        return jsonify(res)
    except Exception as e:
        logger.error(f"Signal compression failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/eval/send_ic_memo", methods=["POST"])
def api_send_ic_memo():
    """
    Send compressed IC memo to whitelist.
    
    Request body:
        hours: Lookback period (default: 24)
    
    Returns:
        Send status and details
    """
    from services.ic_memo_email import send_ic_memo_compressed
    
    data = request.get_json() or {}
    hours = int(data.get("hours", 24))
    
    try:
        res = send_ic_memo_compressed(hours=hours)
        return jsonify(res)
    except Exception as e:
        logger.error(f"IC memo send failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/eval/agents", methods=["GET"])
def api_list_agents():
    """
    List available agents for backtesting.
    
    Returns:
        List of agent names with signal counts
    """
    from models import AgentStatus
    
    try:
        agents = AgentStatus.query.all()
        return jsonify({
            "ok": True,
            "agents": [
                {
                    "name": a.agent_name,
                    "enabled": a.enabled,
                    "run_count": a.run_count,
                    "last_run": a.last_run.isoformat() if a.last_run else None
                }
                for a in agents
            ]
        })
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
