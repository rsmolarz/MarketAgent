import json
import os
import logging
from pathlib import Path
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

logger = logging.getLogger(__name__)

STATE = Path("meta_supervisor/state/divergence.json")

def load_divergence():
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}

def send_divergence_email():
    """Send divergence alert email"""
    from services.api_toggle import api_guard
    if not api_guard("sendgrid", "divergence alert email"):
        return False

    div = load_divergence()
    
    if not div.get("alert"):
        logger.info("No divergence alert, skipping email")
        return False
    
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        logger.error("SENDGRID_API_KEY not set")
        return False
    
    recipients = os.environ.get("META_EMAIL_TO", "").split(",")
    recipients = [r.strip() for r in recipients if r.strip()]
    if not recipients:
        logger.error("META_EMAIL_TO not set")
        return False
    
    from_email = os.environ.get("EMAIL_FROM", "rsmolarz@medmoneyshow.com")
    
    divergence = div.get("divergence_bps", 0)
    live_pnl = div.get("live_pnl_bps", 0)
    sim_pnl = div.get("sim_pnl_bps", 0)
    
    subject = f"[ALERT] Sim vs Live Divergence: {divergence} bps"
    
    text = f"""DIVERGENCE ALERT

A significant divergence between simulated and live performance has been detected.

Divergence: {divergence} bps
Threshold: {div.get('threshold_bps', 100)} bps

Live PnL: {live_pnl} bps
Sim PnL: {sim_pnl} bps

Computed at: {div.get('computed_at', '')}
Horizon: {div.get('horizon_hours', 24)}h
Agents compared: {div.get('agents_compared', 0)}

This may indicate:
- Model drift
- Execution slippage
- Data quality issues
- Market regime change

Please review allocation weights and agent performance.
"""
    
    html = f"""
    <html><body style="font-family:Arial,sans-serif;font-size:14px">
        <h2 style="color:#dc3545">Divergence Alert</h2>
        <p>A significant divergence between simulated and live performance has been detected.</p>
        
        <div style="background:#fff3cd;padding:16px;border-radius:8px;margin:16px 0">
            <h3 style="margin-top:0">Summary</h3>
            <table>
                <tr><td><b>Divergence:</b></td><td style="color:#dc3545"><b>{divergence} bps</b></td></tr>
                <tr><td><b>Threshold:</b></td><td>{div.get('threshold_bps', 100)} bps</td></tr>
                <tr><td><b>Live PnL:</b></td><td>{live_pnl} bps</td></tr>
                <tr><td><b>Sim PnL:</b></td><td>{sim_pnl} bps</td></tr>
            </table>
        </div>
        
        <h3>Possible Causes</h3>
        <ul>
            <li>Model drift</li>
            <li>Execution slippage</li>
            <li>Data quality issues</li>
            <li>Market regime change</li>
        </ul>
        
        <p style="color:#666;font-size:12px">
            Computed at: {div.get('computed_at', '')}<br>
            Horizon: {div.get('horizon_hours', 24)}h | Agents: {div.get('agents_compared', 0)}
        </p>
    </body></html>
    """
    
    try:
        sg = SendGridAPIClient(api_key)
        
        for recipient in recipients:
            message = Mail(
                from_email=Email(from_email),
                to_emails=To(recipient),
                subject=subject,
                plain_text_content=Content("text/plain", text),
                html_content=Content("text/html", html)
            )
            
            response = sg.send(message)
            logger.info(f"Divergence alert sent to {recipient}: {response.status_code}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to send divergence email: {e}")
        return False

if __name__ == "__main__":
    send_divergence_email()
