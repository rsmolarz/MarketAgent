import logging
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)

THESIS_SYSTEM = """You are an IC memo writer.
Given multiple alerts, produce ONE actionable thesis with:
- Thesis (1–2 sentences)
- Evidence (bullets: top 3 signals)
- Action (ACT/WATCH/IGNORE + brief why)
- Risk (1–2 bullets)
Keep it tight. No fluff."""


def call_llm(model: str, system: str, user: str, max_tokens: int = 600) -> str:
    """Call LLM for thesis generation."""
    try:
        if model == "gpt":
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                max_tokens=max_tokens
            )
            return response.choices[0].message.content or ""
        elif model == "claude":
            import anthropic
            import os
            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}]
            )
            if response.content and hasattr(response.content[0], "text"):
                return response.content[0].text
            return ""
        else:
            return ""
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return ""


def build_thesis_for_findings(findings: list, model: str = "gpt") -> str:
    """
    Build a single actionable thesis from multiple findings.
    
    Args:
        findings: List of Finding objects
        model: LLM model to use ('gpt' or 'claude')
    
    Returns:
        Thesis text
    """
    if not findings:
        return "No recent alerts to analyze."
    
    lines = []
    for f in findings:
        severity = (f.severity or "INFO").upper()
        confidence = f.confidence if hasattr(f, 'confidence') and f.confidence else 0.5
        agent_name = f.agent_name if hasattr(f, 'agent_name') else "Unknown"
        title = f.title if hasattr(f, 'title') else "No title"
        symbol = f.symbol if hasattr(f, 'symbol') else "N/A"
        lines.append(f"- [{severity}|{confidence:.2f}] {agent_name}: {title} ({symbol})")
    
    prompt = "Recent alerts:\n" + "\n".join(lines)
    
    txt = call_llm(model=model, system=THESIS_SYSTEM, user=prompt, max_tokens=600)
    return txt or "Failed to generate thesis."


def fetch_recent_findings(db_session, hours: int = 1, symbol: Optional[str] = None) -> list:
    """
    Fetch recent findings from database.
    
    Args:
        db_session: SQLAlchemy session
        hours: lookback window in hours
        symbol: optional symbol filter
    
    Returns:
        List of Finding objects
    """
    from models import Finding
    
    q = db_session.query(Finding).filter(
        Finding.timestamp >= datetime.utcnow() - timedelta(hours=hours)
    ).order_by(Finding.timestamp.desc())
    
    if symbol:
        q = q.filter(Finding.symbol == symbol)
    
    return q.limit(50).all()


def compress_signals_for_symbol(db_session, symbol: str, hours: int = 1) -> dict:
    """
    Compress all recent signals for a symbol into a single thesis.
    
    Returns:
        {"symbol": str, "thesis": str, "finding_count": int, "timestamp": str}
    """
    findings = fetch_recent_findings(db_session, hours=hours, symbol=symbol)
    thesis = build_thesis_for_findings(findings)
    
    return {
        "symbol": symbol,
        "thesis": thesis,
        "finding_count": len(findings),
        "timestamp": datetime.utcnow().isoformat()
    }


def compress_cluster_signals(cluster_votes: dict) -> str:
    """
    Compress cluster-level votes into a thesis.
    
    Args:
        cluster_votes: Output from ensemble_cluster_votes
    
    Returns:
        Thesis text
    """
    lines = []
    for cid, data in cluster_votes.items():
        vote = data.get("vote", "IGNORE")
        conf = data.get("confidence", 0.5)
        members = ", ".join(data.get("members", [])[:3])
        lines.append(f"- [{vote}|{conf:.2f}] Cluster {cid}: {members}")
    
    if not lines:
        return "No cluster signals to compress."
    
    prompt = "Cluster-level signals:\n" + "\n".join(lines)
    return call_llm(model="gpt", system=THESIS_SYSTEM, user=prompt, max_tokens=400)
