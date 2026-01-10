"""
Uncertainty Events API

Provides endpoint to visualize system uncertainty bands on dashboard charts.
"""

from flask import Blueprint, jsonify
from replit_auth import require_login
from models import UncertaintyEvent

bp = Blueprint("uncertainty", __name__)


@bp.route("/api/uncertainty")
def uncertainty_feed():
    """
    Get recent uncertainty events for dashboard visualization.
    
    Returns list of events with timestamp, score, spike status, and regime.
    Used to render uncertainty bands on SPY chart overlay.
    """
    events = (
        UncertaintyEvent.query
        .order_by(UncertaintyEvent.timestamp.desc())
        .limit(200)
        .all()
    )
    return jsonify([e.to_dict() for e in events])


@bp.route("/api/uncertainty/summary")
def uncertainty_summary():
    """
    Get summary statistics for uncertainty events.
    """
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)
    cutoff_7d = datetime.utcnow() - timedelta(days=7)
    
    spikes_24h = (
        UncertaintyEvent.query
        .filter(UncertaintyEvent.timestamp >= cutoff_24h)
        .filter(UncertaintyEvent.spike == True)
        .count()
    )
    
    spikes_7d = (
        UncertaintyEvent.query
        .filter(UncertaintyEvent.timestamp >= cutoff_7d)
        .filter(UncertaintyEvent.spike == True)
        .count()
    )
    
    avg_score_24h = (
        UncertaintyEvent.query
        .filter(UncertaintyEvent.timestamp >= cutoff_24h)
        .with_entities(func.avg(UncertaintyEvent.score))
        .scalar()
    ) or 0.0
    
    latest = (
        UncertaintyEvent.query
        .order_by(UncertaintyEvent.timestamp.desc())
        .first()
    )
    
    return jsonify({
        "spikes_24h": spikes_24h,
        "spikes_7d": spikes_7d,
        "avg_score_24h": round(float(avg_score_24h), 3),
        "latest_score": latest.score if latest else None,
        "latest_spike": latest.spike if latest else False,
        "latest_regime": latest.active_regime if latest else None,
        "latest_timestamp": latest.timestamp.isoformat() if latest else None,
    })
