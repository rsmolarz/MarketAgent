import json
import os
import base64
import logging
from pathlib import Path
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition

from services.lp_weekly_pdf import build_weekly_pdf
from services.tear_sheet_batch import build_all as build_tearsheets
from meta_supervisor.weekly_summary_llm import main as build_weekly_llm_summary

logger = logging.getLogger(__name__)

REPORT = Path("meta_supervisor/reports/meta_report.json")

def _load():
    if not REPORT.exists():
        return {}
    return json.loads(REPORT.read_text())

def format_lp_email(report: dict) -> tuple[str, str, str]:
    meta = report.get("meta", {})
    fleet = report.get("fleet", {})
    agents = report.get("agents", {})
    alloc = report.get("allocation", {}).get("weights", {})

    severity = meta.get("severity", "low").upper()
    subject = f"[LP Daily | {severity}] Portfolio {fleet.get('portfolio_pnl_bps',0)} bps | DD {fleet.get('portfolio_max_drawdown_bps',0)} bps | {meta.get('generated_at','')}"

    lines = []
    lines.append(subject)
    lines.append("")
    lines.append("PORTFOLIO")
    lines.append(f"- PnL (bps): {fleet.get('portfolio_pnl_bps')}")
    lines.append(f"- Hit rate: {fleet.get('portfolio_hit_rate')}")
    lines.append(f"- Max DD (bps): {fleet.get('portfolio_max_drawdown_bps')}")
    lines.append("")

    promos = [k for k,v in agents.items() if v.get("decision") == "PROMOTE"]
    kills = [k for k,v in agents.items() if v.get("decision") in ("KILL", "RETIRE")]
    lines.append("DECISIONS")
    lines.append(f"- PROMOTE: {', '.join(promos) if promos else 'None'}")
    lines.append(f"- KILL / RETIRE: {', '.join(kills) if kills else 'None'}")
    lines.append("")

    lines.append("ALLOCATION (top)")
    for name, w in sorted(alloc.items(), key=lambda kv: kv[1], reverse=True)[:8]:
        lines.append(f"- {name}: {w}")
    text = "\n".join(lines)

    def td(x): return f"<td style='border:1px solid #ddd;padding:8px'>{x}</td>"
    def th(x): return f"<th style='border:1px solid #ddd;padding:8px;background:#f6f6f6;text-align:left'>{x}</th>"

    rows = []
    for name, a in sorted(agents.items(), key=lambda kv: kv[1].get("pnl_sum_bps",0), reverse=True)[:12]:
        rows.append(
            "<tr>" +
            td(name) +
            td(a.get("decision","")) +
            td(a.get("pnl_sum_bps","")) +
            td(a.get("hit_rate","")) +
            td(a.get("error_rate","")) +
            td(a.get("avg_latency_ms","")) +
            td(a.get("cost_usd","")) +
            "</tr>"
        )

    html = f"""
    <html><body style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.35">
      <h2>LP Daily Performance</h2>
      <div><b>Generated:</b> {meta.get("generated_at","")}</div>
      <h3>Portfolio</h3>
      <ul>
        <li><b>PnL (bps):</b> {fleet.get("portfolio_pnl_bps")}</li>
        <li><b>Hit rate:</b> {fleet.get("portfolio_hit_rate")}</li>
        <li><b>Max drawdown (bps):</b> {fleet.get("portfolio_max_drawdown_bps")}</li>
      </ul>

      <h3>Decisions</h3>
      <ul>
        <li><b>PROMOTE:</b> {", ".join(promos) if promos else "None"}</li>
        <li><b>KILL / RETIRE:</b> {", ".join(kills) if kills else "None"}</li>
      </ul>

      <h3>Allocation (top)</h3>
      <ul>
        {''.join([f"<li><b>{k}:</b> {v}</li>" for k,v in sorted(alloc.items(), key=lambda kv: kv[1], reverse=True)[:8]])}
      </ul>

      <h3>Top Agents</h3>
      <table style="border-collapse:collapse;width:100%">
        <tr>{th("Agent")}{th("Decision")}{th("PnL bps")}{th("Hit")}{th("Err")}{th("Latency ms")}{th("Cost $")}</tr>
        {''.join(rows)}
      </table>

      <p style="color:#666;margin-top:12px">
        Informational performance summary. Not investment advice.
      </p>
    </body></html>
    """

    return subject, text, html

def _attach_files(message: Mail, paths: list):
    """Attach PDF files to SendGrid message"""
    for p in paths:
        if not isinstance(p, Path):
            p = Path(p)
        if not p.exists():
            continue
        encoded = base64.b64encode(p.read_bytes()).decode("utf-8")
        attachment = Attachment()
        attachment.file_content = FileContent(encoded)
        attachment.file_name = FileName(p.name)
        attachment.file_type = FileType("application/pdf")
        attachment.disposition = Disposition("attachment")
        message.add_attachment(attachment)

def send_lp_email():
    report = _load()
    if not report:
        logger.warning("No meta report found for LP email")
        return False

    subject, text, html = format_lp_email(report)

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
            logger.info(f"LP email sent to {recipient}: {response.status_code}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to send LP email: {e}")
        return False

def send_lp_weekly_email():
    """Send weekly LP email with PDF attachments"""
    report = _load()
    if not report:
        logger.warning("No meta report found for LP weekly email")
        return False

    try:
        build_weekly_llm_summary()
        logger.info("Weekly LLM summary generated")
    except Exception as e:
        logger.warning(f"Weekly LLM summary failed: {e}")

    subject, text, html = format_lp_email(report)
    subject = subject.replace("[LP Daily", "[LP Weekly")

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

    attachments = []

    try:
        portfolio_pdf = build_weekly_pdf(report)
        if portfolio_pdf:
            attachments.append(Path(portfolio_pdf))
    except Exception as e:
        logger.warning(f"Weekly portfolio PDF failed: {e}")

    try:
        tear_sheets = build_tearsheets(top_n=10)
        for ts in tear_sheets:
            agent_name = ts.get("agent", "unknown")
            ts_path = Path(f"reports/tear_sheets/{agent_name}.json")
            if ts_path.exists():
                pass
    except Exception as e:
        logger.warning(f"Tear sheet build failed: {e}")

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

            _attach_files(message, attachments)

            response = sg.send(message)
            logger.info(
                f"LP WEEKLY email sent to {recipient}: "
                f"{response.status_code} | attachments={len(attachments)}"
            )

        return True

    except Exception as e:
        logger.error(f"Failed to send LP weekly email: {e}")
        return False

if __name__ == "__main__":
    mode = os.environ.get("LP_EMAIL_MODE", "daily").lower()
    if mode == "weekly":
        send_lp_weekly_email()
    else:
        send_lp_email()
