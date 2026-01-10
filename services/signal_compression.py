"""
Signal Compression Service

Compresses multiple findings into IC memo theses.
Groups by (symbol, market_type) and time proximity.
"""
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def compress_findings(findings: list, window_minutes: int = 90) -> List[Dict[str, Any]]:
    """
    Merge many findings into a small set of theses.
    
    Simple deterministic clustering: (symbol, market_type) + time bucket.
    
    Args:
        findings: List of Finding model instances
        window_minutes: Time window for clustering
    
    Returns:
        List of thesis dicts
    """
    buckets = defaultdict(list)
    for f in findings:
        sym = (getattr(f, 'symbol', None) or "UNKNOWN").upper()
        mkt = getattr(f, 'market_type', None) or "unknown"
        t = getattr(f, 'timestamp', None) or datetime.utcnow()
        bucket = int(t.timestamp() // (window_minutes * 60))
        buckets[(sym, mkt, bucket)].append(f)
    
    theses = []
    severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    
    for (sym, mkt, bucket), fs in buckets.items():
        fs = sorted(fs, key=lambda x: getattr(x, 'timestamp', datetime.min), reverse=True)
        top = fs[0]
        max_sev = max(fs, key=lambda x: severity_rank.get(getattr(x, 'severity', 'low'), 0))
        max_severity = getattr(max_sev, 'severity', 'medium')
        
        acts = sum(1 for x in fs if (getattr(x, 'consensus_action', '') or "").upper() == "ACT")
        watches = sum(1 for x in fs if (getattr(x, 'consensus_action', '') or "").upper() == "WATCH")
        ignores = sum(1 for x in fs if (getattr(x, 'consensus_action', '') or "").upper() == "IGNORE")
        
        if acts >= max(watches, ignores):
            consensus = "ACT"
        elif watches >= ignores:
            consensus = "WATCH"
        else:
            consensus = "IGNORE"
        
        conf_sum = sum(
            getattr(x, 'consensus_confidence', None) or getattr(x, 'confidence', None) or 0.5
            for x in fs
        )
        avg_conf = conf_sum / max(len(fs), 1)
        
        start_ts = getattr(fs[-1], 'timestamp', datetime.min)
        end_ts = getattr(fs[0], 'timestamp', datetime.min)
        
        theses.append({
            "symbol": sym,
            "market_type": mkt,
            "start_ts": start_ts.isoformat() if start_ts else None,
            "end_ts": end_ts.isoformat() if end_ts else None,
            "finding_count": len(fs),
            "max_severity": max_severity,
            "consensus": consensus,
            "confidence": round(float(avg_conf), 3),
            "headline": getattr(top, 'title', 'Unknown'),
            "supporting": [
                {
                    "id": getattr(x, 'id', None),
                    "agent": getattr(x, 'agent_name', 'unknown'),
                    "severity": getattr(x, 'severity', 'medium'),
                    "confidence": getattr(x, 'consensus_confidence', None) or getattr(x, 'confidence', 0.5),
                    "title": getattr(x, 'title', ''),
                } for x in fs[:6]
            ],
        })
    
    theses.sort(
        key=lambda x: (
            severity_rank.get(x["max_severity"], 0),
            x["confidence"]
        ),
        reverse=True
    )
    return theses


def build_ic_memo_text(theses: List[Dict[str, Any]], max_theses: int = 10) -> str:
    """
    Build IC memo text from compressed theses.
    
    Args:
        theses: List of thesis dicts
        max_theses: Maximum number of theses to include
    
    Returns:
        Formatted memo text
    """
    lines = []
    lines.append("=" * 60)
    lines.append("IC MEMO — Signal Compression")
    lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    lines.append("=" * 60)
    lines.append("")
    
    if not theses:
        lines.append("No significant signals to report.")
        return "\n".join(lines)
    
    for i, th in enumerate(theses[:max_theses], 1):
        sev = th['max_severity'].upper()
        lines.append(f"{i}. [{sev}] {th['symbol']} ({th['market_type']}) — {th['consensus']} @ {th['confidence']:.2f}")
        lines.append(f"   Thesis: {th['headline']}")
        lines.append(f"   Window: {th['start_ts']} → {th['end_ts']} | n={th['finding_count']}")
        
        for s in th["supporting"]:
            conf = s.get('confidence') or 0.5
            lines.append(f"     • {s['agent']} [{s['severity']}] ({conf:.2f}) {s['title']}")
        lines.append("")
    
    lines.append("=" * 60)
    lines.append(f"Total theses: {len(theses)} | Showing top {min(len(theses), max_theses)}")
    
    return "\n".join(lines)


def build_ic_memo_html(theses: List[Dict[str, Any]], max_theses: int = 10) -> str:
    """
    Build IC memo HTML from compressed theses.
    
    Args:
        theses: List of thesis dicts
        max_theses: Maximum number of theses to include
    
    Returns:
        Formatted HTML memo
    """
    severity_colors = {
        "critical": "#dc3545",
        "high": "#fd7e14",
        "medium": "#ffc107",
        "low": "#28a745"
    }
    
    html = []
    html.append("<html><body>")
    html.append("<h1>IC MEMO — Signal Compression</h1>")
    html.append(f"<p><strong>Generated:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</p>")
    html.append("<hr>")
    
    if not theses:
        html.append("<p>No significant signals to report.</p>")
        html.append("</body></html>")
        return "\n".join(html)
    
    for i, th in enumerate(theses[:max_theses], 1):
        sev = th['max_severity'].lower()
        color = severity_colors.get(sev, "#6c757d")
        
        html.append(f"<h3 style='color:{color}'>{i}. [{th['max_severity'].upper()}] {th['symbol']} ({th['market_type']})</h3>")
        html.append(f"<p><strong>Consensus:</strong> {th['consensus']} @ {th['confidence']:.2f}</p>")
        html.append(f"<p><strong>Thesis:</strong> {th['headline']}</p>")
        html.append(f"<p><strong>Window:</strong> {th['start_ts']} → {th['end_ts']} | Findings: {th['finding_count']}</p>")
        
        html.append("<ul>")
        for s in th["supporting"]:
            conf = s.get('confidence') or 0.5
            html.append(f"<li><strong>{s['agent']}</strong> [{s['severity']}] ({conf:.2f}) — {s['title']}</li>")
        html.append("</ul>")
        html.append("<hr>")
    
    html.append(f"<p><em>Total theses: {len(theses)} | Showing top {min(len(theses), max_theses)}</em></p>")
    html.append("</body></html>")
    
    return "\n".join(html)
