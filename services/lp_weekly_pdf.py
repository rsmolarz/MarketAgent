import json
import os
import base64
import logging
from pathlib import Path
from datetime import datetime, timezone
from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition

from services.weekly_charts import cvar_heatmap_by_regime_png, live_vs_sim_attribution_png
from meta_supervisor.capital_movement import capital_movement_table

logger = logging.getLogger(__name__)

OUT = Path("reports/lp_weekly.pdf")
OUT_DIR = Path("meta_supervisor/reports")
REPORT_PATH = Path("meta_supervisor/reports/meta_report.json")
SUMMARY_JSON = Path("meta_supervisor/reports/weekly_change_summary.json")

def load_report() -> dict:
    if not REPORT_PATH.exists():
        return {}
    return json.loads(REPORT_PATH.read_text())

def _draw_wrapped(c: canvas.Canvas, x: int, y: int, text: str, max_width: int, line_h: int = 12):
    words = (text or "").split()
    line = ""
    for w in words:
        trial = (line + " " + w).strip()
        if c.stringWidth(trial, "Helvetica", 10) <= max_width:
            line = trial
        else:
            c.drawString(x, y, line)
            y -= line_h
            line = w
    if line:
        c.drawString(x, y, line)
        y -= line_h
    return y

def build_weekly_pdf(report: dict) -> Path:
    """Build LP weekly PDF summary with charts, LLM summary, and capital movement"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    out = OUT_DIR / "lp_weekly_summary.pdf"
    c = canvas.Canvas(str(out), pagesize=LETTER)
    w, h = LETTER

    meta = report.get("meta", {})
    fleet = report.get("fleet", {})
    agents = report.get("agents", {})
    alloc = (report.get("allocation") or {}).get("weights", {}) or {}

    y = h - 40
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "LP Weekly Summary")
    y -= 20

    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Generated: {meta.get('generated_at', '')}")
    y -= 14
    c.drawString(40, y, f"Portfolio PnL (bps): {fleet.get('portfolio_pnl_bps', '')} | Max DD (bps): {fleet.get('portfolio_max_drawdown_bps', '')}")
    y -= 14
    c.drawString(40, y, f"Allocation method: {(report.get('allocation') or {}).get('method', '')}")
    y -= 20

    promos = [k for k, v in agents.items() if v.get("decision") == "PROMOTE"]
    kills = [k for k, v in agents.items() if v.get("decision") in ("KILL", "RETIRE")]

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Decisions")
    y -= 14
    c.setFont("Helvetica", 10)
    y = _draw_wrapped(c, 50, y, f"PROMOTE: {', '.join(promos) if promos else 'None'}", 520)
    y = _draw_wrapped(c, 50, y, f"KILL/RETIRE: {', '.join(kills) if kills else 'None'}", 520)
    y -= 10

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Top Allocation (weights)")
    y -= 14
    c.setFont("Helvetica", 10)
    for name, wt in sorted(alloc.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        c.drawString(50, y, f"- {name}: {wt}")
        y -= 12

    c.showPage()

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, h - 40, "Regime Tail Risk Heatmap (|CVaR95|)")
    try:
        img = cvar_heatmap_by_regime_png(horizon_hours=24)
        if img and Path(img).exists():
            c.drawImage(str(img), 40, 220, width=520, height=260, preserveAspectRatio=True, mask='auto')
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(40, 400, f"Chart unavailable: {e}")
    c.setFont("Helvetica", 10)
    c.drawString(40, 190, "Interpretation: darker/higher values indicate worse left-tail outcomes in that regime over the last window.")
    c.showPage()

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, h - 40, "What Changed This Week (LLM Summary)")
    c.setFont("Helvetica", 10)

    summary_block = {}
    if SUMMARY_JSON.exists():
        try:
            summary_block = json.loads(SUMMARY_JSON.read_text()).get("summary", {})
        except Exception:
            summary_block = {}

    y = h - 70
    headline = summary_block.get("headline") or "N/A"
    c.setFont("Helvetica-Bold", 12)
    y = _draw_wrapped(c, 40, y, headline, 520, line_h=14)
    y -= 6

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Bullets")
    y -= 14
    c.setFont("Helvetica", 10)
    for b in (summary_block.get("bullets") or [])[:8]:
        y = _draw_wrapped(c, 50, y, f"- {b}", 510)

    y -= 6
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Risks")
    y -= 14
    c.setFont("Helvetica", 10)
    for r in (summary_block.get("risks") or [])[:6]:
        y = _draw_wrapped(c, 50, y, f"- {r}", 510)

    y -= 6
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Actions")
    y -= 14
    c.setFont("Helvetica", 10)
    for a in (summary_block.get("actions") or [])[:6]:
        y = _draw_wrapped(c, 50, y, f"- {a}", 510)

    c.setFont("Helvetica", 9)
    c.drawString(40, 40, "Audit note: This page is generated from stored context + LLM output archived in weekly_change_summary.json.")
    c.showPage()

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, h - 40, "Capital Movement Reconciliation (Allocation Deltas)")
    mv = capital_movement_table(n_snapshots=14, top_n=12)

    c.setFont("Helvetica", 10)
    y = h - 70
    if not mv.get("ok"):
        c.drawString(40, y, f"Insufficient allocation history: {mv.get('reason')}")
    else:
        c.drawString(40, y, f"From: {mv.get('from_ts')}   To: {mv.get('to_ts')}")
        y -= 18
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, "Agent")
        c.drawString(220, y, "W_from")
        c.drawString(300, y, "W_to")
        c.drawString(380, y, "Delta")
        y -= 12
        c.setFont("Helvetica", 10)
        for row in mv.get("top_moves", []):
            c.drawString(40, y, str(row["agent"]))
            c.drawString(220, y, str(row["w_from"]))
            c.drawString(300, y, str(row["w_to"]))
            c.drawString(380, y, str(row["delta"]))
            y -= 12

    c.showPage()

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, h - 40, "Live vs Sim Attribution (Cumulative)")
    try:
        img2 = live_vs_sim_attribution_png(horizon_hours=24)
        if img2 and Path(img2).exists():
            c.drawImage(str(img2), 40, 220, width=520, height=260, preserveAspectRatio=True, mask='auto')
    except Exception as e:
        c.setFont("Helvetica", 10)
        c.drawString(40, 400, f"Chart unavailable: {e}")
    c.setFont("Helvetica", 10)
    c.drawString(40, 190, "Note: Sim line uses a proxy mapping from score_final to expected bps. Replace with your simulator output when available.")
    c.showPage()

    c.save()
    return out

def send_weekly_pdf_email():
    """Send weekly PDF via SendGrid with attachment"""
    report = load_report()
    if not report:
        logger.warning("No meta report found for weekly PDF")
        return False

    pdf_path = build_weekly_pdf(report)

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

    meta = report.get("meta", {})
    fleet = report.get("fleet", {})
    severity = meta.get("severity", "low").upper()

    subject = f"[LP Weekly | {severity}] Portfolio {fleet.get('portfolio_pnl_bps', 0)} bps | Week of {meta.get('generated_at', '')[:10]}"

    text = f"""LP Weekly Performance Summary

Portfolio PnL: {fleet.get('portfolio_pnl_bps', 0)} bps
Hit Rate: {fleet.get('portfolio_hit_rate', 0)}
Max Drawdown: {fleet.get('portfolio_max_drawdown_bps', 0)} bps

See attached PDF for full details.

This is an informational summary. Not investment advice.
"""

    try:
        with open(pdf_path, "rb") as f:
            pdf_data = base64.b64encode(f.read()).decode()

        sg = SendGridAPIClient(api_key)

        for recipient in recipients:
            message = Mail(
                from_email=Email(from_email),
                to_emails=To(recipient),
                subject=subject,
                plain_text_content=Content("text/plain", text)
            )

            attachment = Attachment()
            attachment.file_content = FileContent(pdf_data)
            attachment.file_name = FileName("lp_weekly_report.pdf")
            attachment.file_type = FileType("application/pdf")
            attachment.disposition = Disposition("attachment")
            message.attachment = attachment

            response = sg.send(message)
            logger.info(f"Weekly PDF sent to {recipient}: {response.status_code}")

        return True
    except Exception as e:
        logger.error(f"Failed to send weekly PDF: {e}")
        return False

if __name__ == "__main__":
    report = load_report()
    if report:
        pdf_path = build_weekly_pdf(report)
        print(f"PDF generated: {pdf_path}")
    else:
        print("No report found")
