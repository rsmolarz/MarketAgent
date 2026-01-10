"""
IC Memo Service

Builds compressed thesis from recent findings.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def build_ic_memo(hours: int = 24, limit: int = 25) -> Dict[str, Any]:
    """
    Build IC memo from recent findings.
    
    Args:
        hours: Lookback window
        limit: Max findings to process
    
    Returns:
        Memo dict with headline, thesis, bullets
    """
    from models import Finding
    
    since = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        qs = (
            Finding.query
            .filter(Finding.timestamp >= since)
            .order_by(Finding.timestamp.desc())
            .limit(limit)
            .all()
        )
    except Exception as e:
        logger.error(f"IC memo query error: {e}")
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "hours": hours,
            "headline": "Error loading findings",
            "thesis": str(e),
            "bullets": []
        }
    
    if not qs:
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "hours": hours,
            "headline": "No material signals",
            "thesis": "No significant findings in the selected window.",
            "bullets": []
        }
    
    items = []
    for f in qs:
        items.append({
            "ts": f.timestamp.isoformat() if f.timestamp else None,
            "agent": getattr(f, 'agent_name', 'Unknown'),
            "symbol": getattr(f, 'symbol', None) or "NA",
            "severity": getattr(f, 'severity', 'medium'),
            "confidence": float(getattr(f, 'confidence', 0) or 0),
            "title": getattr(f, 'title', 'Untitled')
        })
    
    sev_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    items_sorted = sorted(
        items,
        key=lambda x: (sev_rank.get(x["severity"], 0), x["confidence"]),
        reverse=True
    )
    top = items_sorted[:3]
    
    if top:
        headline = f"{top[0]['severity'].upper()} focus: {top[0]['symbol']} — {top[0]['title']}"
    else:
        headline = "No material signals"
    
    bullets = [
        f"[{t['severity'].upper()}] {t['symbol']} — {t['title']} ({t['agent']}, conf {int(t['confidence']*100)}%)"
        for t in top
    ]
    
    thesis = (
        "Compressed thesis:\n"
        + "\n".join(f"- {b}" for b in bullets)
        + "\n\nAction: review top items; if council confirms ACT, promote to trade candidate."
    )
    
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "hours": hours,
        "headline": headline,
        "thesis": thesis,
        "bullets": bullets
    }
