"""
IC Memo Email Service

Sends compressed IC memos to the whitelist.
"""
from datetime import datetime, timedelta
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


def send_ic_memo_compressed(hours: int = 24, to_emails: Optional[List[str]] = None) -> dict:
    """
    Compress recent findings and send IC memo email.
    
    Args:
        hours: Lookback period for findings
        to_emails: Override email list (uses whitelist if None)
    
    Returns:
        Dict with status and details
    """
    from models import db, Finding, Whitelist
    from services.signal_compression import compress_findings, build_ic_memo_text, build_ic_memo_html
    
    try:
        from services.email_meta import send_meta_email
    except ImportError:
        logger.warning("send_meta_email not available")
        send_meta_email = None
    
    since = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        findings = (
            Finding.query
            .filter(Finding.timestamp >= since)
            .order_by(Finding.timestamp.desc())
            .limit(500)
            .all()
        )
    except Exception as e:
        logger.error(f"Failed to query findings: {e}")
        return {"ok": False, "error": str(e)}
    
    if not findings:
        logger.info(f"No findings in last {hours}h, skipping IC memo")
        return {"ok": True, "skipped": True, "reason": "no_findings"}
    
    theses = compress_findings(findings, window_minutes=90)
    
    if not theses:
        logger.info("No theses after compression, skipping IC memo")
        return {"ok": True, "skipped": True, "reason": "no_theses"}
    
    text_body = build_ic_memo_text(theses)
    html_body = build_ic_memo_html(theses)
    
    subject = f"IC Memo (Compressed) — last {hours}h — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
    
    if to_emails is None:
        try:
            to_emails = [w.email for w in Whitelist.query.all()]
        except Exception as e:
            logger.warning(f"Failed to get whitelist: {e}")
            to_emails = []
    
    if not to_emails:
        logger.warning("No recipients for IC memo")
        return {"ok": True, "skipped": True, "reason": "no_recipients"}
    
    if send_meta_email:
        try:
            send_meta_email(subject, text_body, html_body, to_override=to_emails)
            logger.info(f"Sent IC memo to {len(to_emails)} recipients with {len(theses)} theses")
            return {
                "ok": True,
                "sent": True,
                "recipients": len(to_emails),
                "theses": len(theses),
                "findings": len(findings)
            }
        except Exception as e:
            logger.error(f"Failed to send IC memo: {e}")
            return {"ok": False, "error": str(e)}
    else:
        logger.warning("Email service not available, returning memo text only")
        return {
            "ok": True,
            "sent": False,
            "reason": "email_service_unavailable",
            "theses": len(theses),
            "text": text_body
        }


def get_compressed_memo_preview(hours: int = 24) -> dict:
    """
    Get preview of compressed IC memo without sending.
    
    Args:
        hours: Lookback period for findings
    
    Returns:
        Dict with theses and memo preview
    """
    from models import Finding
    from services.signal_compression import compress_findings, build_ic_memo_text
    
    since = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        findings = (
            Finding.query
            .filter(Finding.timestamp >= since)
            .order_by(Finding.timestamp.desc())
            .limit(500)
            .all()
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}
    
    theses = compress_findings(findings, window_minutes=90)
    text = build_ic_memo_text(theses)
    
    return {
        "ok": True,
        "findings_count": len(findings),
        "theses_count": len(theses),
        "theses": theses[:10],
        "preview": text
    }
