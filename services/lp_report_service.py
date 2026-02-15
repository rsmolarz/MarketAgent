import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

logger = logging.getLogger(__name__)

def load_meta_report():
    p = Path("meta_supervisor/reports/meta_report.json")
    if not p.exists():
        return {}
    return json.loads(p.read_text())

def format_lp_report(report: dict) -> tuple[str, str, str]:
    """Format LP-grade performance report for email."""
    meta = report.get("meta", {})
    fleet = report.get("fleet", {})
    agents = report.get("agents", {})
    alloc = report.get("allocation", {})
    weights = alloc.get("weights", {})
    confidence = alloc.get("confidence_state", {})
    
    promos = [k for k, v in agents.items() if v.get("decision") == "PROMOTE"]
    kills = [k for k, v in agents.items() if v.get("decision") == "KILL"]
    
    subject = f"[LP Report] Portfolio {fleet.get('portfolio_pnl_bps', 0)} bps | {len(agents)} agents | {meta.get('generated_at', '')[:10]}"
    
    lines = [
        "LP PERFORMANCE REPORT",
        "=" * 40,
        "",
        "PORTFOLIO SUMMARY",
        f"  PnL (bps): {fleet.get('portfolio_pnl_bps', 0)}",
        f"  Hit Rate: {fleet.get('portfolio_hit_rate', 0)}",
        f"  Max Drawdown (bps): {fleet.get('portfolio_max_drawdown_bps', 0)}",
        f"  Total Signals: {fleet.get('total_signals', 0)}",
        f"  Sharpe (approx): {fleet.get('sharpe_approx', 0)}",
        "",
        "AGENT STATUS",
        f"  Active: {len([a for a in agents.values() if a.get('decision') != 'KILL'])}",
        f"  Killed: {len(kills)}",
        f"  Promotable: {len(promos)}",
        "",
        "DECISIONS",
        f"  PROMOTE: {', '.join(promos) if promos else 'None'}",
        f"  KILL: {', '.join(kills) if kills else 'None'}",
        "",
        "ALLOCATION (top 5)",
    ]
    
    for name, w in sorted(weights.items(), key=lambda x: x[1], reverse=True)[:5]:
        lines.append(f"  {name}: {w*100:.1f}%")
    
    lines.extend([
        "",
        "TOP AGENTS BY PNL",
    ])
    
    for name, a in sorted(agents.items(), key=lambda x: x[1].get("pnl_sum_bps", 0), reverse=True)[:5]:
        lines.append(f"  {name}: {a.get('pnl_sum_bps', 0)} bps | Hit: {a.get('hit_rate', 0)*100:.0f}%")
    
    text = "\n".join(lines)
    
    def td(x): return f"<td style='border:1px solid #ddd;padding:8px'>{x}</td>"
    def th(x): return f"<th style='border:1px solid #ddd;padding:8px;background:#f6f6f6;text-align:left'>{x}</th>"
    
    agent_rows = []
    for name, a in sorted(agents.items(), key=lambda x: x[1].get("pnl_sum_bps", 0), reverse=True)[:10]:
        decision = a.get("decision", "HOLD")
        color = "#28a745" if decision == "PROMOTE" else ("#dc3545" if decision == "KILL" else "#6c757d")
        hit_rate_str = f"{a.get('hit_rate', 0)*100:.0f}%"
        error_rate_str = f"{a.get('error_rate', 0)*100:.1f}%"
        agent_rows.append(
            f"<tr>{td(name)}<td style='border:1px solid #ddd;padding:8px;color:{color}'>{decision}</td>"
            f"{td(a.get('pnl_sum_bps', 0))}{td(hit_rate_str)}"
            f"{td(error_rate_str)}{td(a.get('runs', 0))}</tr>"
        )
    
    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;font-size:14px;line-height:1.4;color:#333">
        <h2 style="color:#1a1a2e">LP Performance Report</h2>
        <p style="color:#666">Generated: {meta.get('generated_at', '')}</p>
        
        <div style="background:#f8f9fa;padding:16px;border-radius:8px;margin:16px 0">
            <h3 style="margin-top:0">Portfolio Summary</h3>
            <table style="width:100%">
                <tr><td><b>PnL (bps):</b></td><td>{fleet.get('portfolio_pnl_bps', 0)}</td></tr>
                <tr><td><b>Hit Rate:</b></td><td>{fleet.get('portfolio_hit_rate', 0)}</td></tr>
                <tr><td><b>Max Drawdown:</b></td><td>{fleet.get('portfolio_max_drawdown_bps', 0)} bps</td></tr>
                <tr><td><b>Sharpe (approx):</b></td><td>{fleet.get('sharpe_approx', 0)}</td></tr>
            </table>
        </div>
        
        <div style="margin:16px 0">
            <h3>Decisions</h3>
            <p><span style="color:#28a745"><b>PROMOTE:</b></span> {', '.join(promos) if promos else 'None'}</p>
            <p><span style="color:#dc3545"><b>KILL:</b></span> {', '.join(kills) if kills else 'None'}</p>
        </div>
        
        <h3>Agent Performance</h3>
        <table style="border-collapse:collapse;width:100%">
            <tr>{th('Agent')}{th('Decision')}{th('PnL bps')}{th('Hit Rate')}{th('Error Rate')}{th('Runs')}</tr>
            {''.join(agent_rows)}
        </table>
        
        <h3>Capital Allocation</h3>
        <ul>
            {''.join([f"<li><b>{k}:</b> {v*100:.1f}%</li>" for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True)[:8]])}
        </ul>
        
        <p style="color:#999;font-size:12px;margin-top:24px">
            This is an automated performance summary. Not investment advice.
        </p>
    </body>
    </html>
    """
    
    return subject, text, html

def send_lp_report():
    """Send LP performance report via email."""
    report = load_meta_report()
    if not report:
        logger.warning("No meta report found for LP report")
        return False
    
    subject, text, html = format_lp_report(report)
    
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        logger.error("SENDGRID_API_KEY not set")
        return False
    
    recipients = os.environ.get("META_EMAIL_TO", "").split(",")
    recipients = [r.strip() for r in recipients if r.strip()]
    if not recipients:
        logger.warning("META_EMAIL_TO not set, using default")
        return False
    
    from_email = os.environ.get("EMAIL_FROM", "rsmolarz@medmoneyshow.com")
    
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
            logger.info(f"LP report sent to {recipient}: {response.status_code}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to send LP report: {e}")
        return False

if __name__ == "__main__":
    send_lp_report()
