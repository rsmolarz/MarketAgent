import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "rsmolarz@medmoneyshow.com")
EMAIL_TO = os.environ.get("META_EMAIL_TO")

def send_meta_email(subject: str, text_body: str, html_body: str | None = None):
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY not configured")
    
    if not EMAIL_TO:
        raise RuntimeError("META_EMAIL_TO not configured")

    message = Mail(
        from_email=Email(EMAIL_FROM),
        to_emails=[To(email.strip()) for email in EMAIL_TO.split(",")],
        subject=subject
    )
    
    if html_body:
        message.content = [
            Content("text/plain", text_body),
            Content("text/html", html_body)
        ]
    else:
        message.content = Content("text/plain", text_body)

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    response = sg.send(message)
    
    if response.status_code not in (200, 201, 202):
        raise RuntimeError(f"SendGrid error: {response.status_code}")
    
    return response


def send_critical_finding_alert(finding, consensus: dict):
    """
    Send an email alert for a critical finding that received ACT consensus.
    
    Args:
        finding: Finding model instance
        consensus: Dict with action, confidence, votes, disagreement
    """
    subject = f"🚨 CRITICAL SIGNAL — {finding.title}"
    
    text_body = f"""
CRITICAL FINDING ALERT
======================

Agent: {finding.agent_name}
Symbol: {finding.symbol or 'N/A'}
Market: {finding.market_type or 'N/A'}
Severity: {finding.severity}
Confidence: {finding.confidence:.2f}

LLM Council Decision
--------------------
Consensus Action: {consensus.get('action', 'N/A')}
Council Confidence: {consensus.get('confidence', 0):.2f}
Votes: {consensus.get('votes', {})}
Disagreement: {consensus.get('disagreement', False)}

Description
-----------
{finding.description}

Metadata
--------
{finding.finding_metadata}

---
This is an automated alert from the Market Inefficiency Detection Platform.
"""

    html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<div style="background: #dc3545; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
<h1 style="margin: 0;">🚨 CRITICAL SIGNAL</h1>
<h2 style="margin: 10px 0 0 0;">{finding.title}</h2>
</div>
<div style="padding: 20px; background: #f8f9fa; border: 1px solid #dee2e6;">
<table style="width: 100%; border-collapse: collapse;">
<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;"><strong>Agent</strong></td><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{finding.agent_name}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;"><strong>Symbol</strong></td><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{finding.symbol or 'N/A'}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;"><strong>Market</strong></td><td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{finding.market_type or 'N/A'}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #dee2e6;"><strong>Severity</strong></td><td style="padding: 8px; border-bottom: 1px solid #dee2e6;"><span style="color: #dc3545; font-weight: bold;">{finding.severity}</span></td></tr>
</table>
</div>
<div style="padding: 20px; background: #fff; border: 1px solid #dee2e6; border-top: none;">
<h3 style="color: #007bff;">LLM Council Decision</h3>
<p><strong>Consensus:</strong> <span style="background: #28a745; color: white; padding: 4px 8px; border-radius: 4px;">{consensus.get('action', 'N/A')}</span></p>
<p><strong>Confidence:</strong> {consensus.get('confidence', 0):.2%}</p>
<p><strong>Votes:</strong> {consensus.get('votes', {})}</p>
<p><strong>Disagreement:</strong> {'Yes ⚠️' if consensus.get('disagreement') else 'No ✓'}</p>
</div>
<div style="padding: 20px; background: #fff; border: 1px solid #dee2e6; border-top: none;">
<h3>Description</h3>
<p>{finding.description}</p>
</div>
<div style="padding: 15px; background: #6c757d; color: white; border-radius: 0 0 8px 8px; text-align: center; font-size: 12px;">
Automated alert from Market Inefficiency Detection Platform
</div>
</body>
</html>
"""

    try:
        send_meta_email(subject, text_body, html_body)
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to send critical finding alert: {e}")
        return False
