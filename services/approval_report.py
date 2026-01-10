from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from textwrap import wrap
from datetime import datetime
import os


def _draw_wrapped(c, x, y, text, width_chars=110, leading=14):
    """Draw wrapped text and return new y position."""
    for line in wrap(str(text or ""), width_chars):
        c.drawString(x, y, line)
        y -= leading
    return y


def build_approval_report_pdf(out_path: str, proposal: dict, votes: list):
    """
    Generate a PDF report explaining why a proposal was approved.
    Includes proposal details, votes with confidence scores, and per-file risk.
    """
    c = canvas.Canvas(out_path, pagesize=LETTER)
    w, h = LETTER
    x = 0.8 * inch
    y = h - 0.8 * inch
    
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(HexColor("#1a365d"))
    c.drawString(x, y, "Agent Oversight Approval Report")
    y -= 24
    
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#666666"))
    c.drawString(x, y, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    y -= 8
    c.drawString(x, y, "Educational and internal use only - not legal or financial advice")
    y -= 24
    
    c.setFillColor(HexColor("#000000"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "Proposal Details")
    y -= 4
    c.setStrokeColor(HexColor("#2563eb"))
    c.setLineWidth(2)
    c.line(x, y, x + 150, y)
    y -= 16
    
    c.setFont("Helvetica", 10)
    y = _draw_wrapped(c, x, y, f"ID: {proposal.get('id', 'N/A')}")
    y = _draw_wrapped(c, x, y, f"Title: {proposal.get('title', 'N/A')}")
    y = _draw_wrapped(c, x, y, f"Branch: {proposal.get('branch', 'N/A')}")
    y = _draw_wrapped(c, x, y, f"Status: {proposal.get('status', 'N/A')}")
    
    overall_risk = proposal.get('overall_risk', 'unknown')
    risk_color = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444"}.get(overall_risk.lower(), "#666666")
    c.setFillColor(HexColor(risk_color))
    y = _draw_wrapped(c, x, y, f"Overall Risk: {overall_risk.upper()}")
    c.setFillColor(HexColor("#000000"))
    y -= 12
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "Rationale")
    y -= 4
    c.setStrokeColor(HexColor("#2563eb"))
    c.line(x, y, x + 80, y)
    y -= 16
    
    c.setFont("Helvetica", 10)
    y = _draw_wrapped(c, x, y, f"Summary: {proposal.get('summary', 'No summary provided')}")
    y -= 6
    y = _draw_wrapped(c, x, y, f"Rationale: {proposal.get('rationale', 'No rationale provided')}")
    y -= 16
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "Agent Votes")
    y -= 4
    c.setStrokeColor(HexColor("#2563eb"))
    c.line(x, y, x + 100, y)
    y -= 16
    
    c.setFont("Helvetica", 10)
    if votes:
        for v in votes:
            vote_type = v.get('vote', 'UNKNOWN')
            vote_color = {"APPROVE": "#22c55e", "REJECT": "#ef4444", "ABSTAIN": "#f59e0b"}.get(vote_type, "#666666")
            
            agent_name = v.get('agent_name', 'Unknown Agent')
            confidence = v.get('confidence', 0)
            effective_conf = v.get('effective_confidence', confidence)
            
            c.setFillColor(HexColor(vote_color))
            line = f"{agent_name}: {vote_type}"
            c.drawString(x, y, line)
            y -= 14
            
            c.setFillColor(HexColor("#000000"))
            conf_line = f"  Confidence: {confidence:.2f} | Effective: {effective_conf:.4f}"
            c.drawString(x, y, conf_line)
            y -= 14
            
            notes = v.get('notes', '')
            if notes:
                y = _draw_wrapped(c, x + 10, y, f"Notes: {notes}", width_chars=100)
            y -= 8
            
            if y < 1.5 * inch:
                c.showPage()
                y = h - 0.8 * inch
                c.setFont("Helvetica", 10)
    else:
        c.drawString(x, y, "No votes recorded")
        y -= 14
    
    y -= 8
    
    file_risk = proposal.get('file_risk', {})
    if file_risk:
        if y < 2.5 * inch:
            c.showPage()
            y = h - 0.8 * inch
        
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(HexColor("#000000"))
        c.drawString(x, y, "Per-File Risk Assessment")
        y -= 4
        c.setStrokeColor(HexColor("#2563eb"))
        c.line(x, y, x + 160, y)
        y -= 16
        
        c.setFont("Helvetica", 9)
        for filepath, risk in file_risk.items():
            risk_str = str(risk).lower()
            risk_color = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444"}.get(risk_str, "#666666")
            
            c.setFillColor(HexColor("#000000"))
            c.drawString(x, y, f"{filepath}:")
            c.setFillColor(HexColor(risk_color))
            c.drawString(x + 300, y, risk_str.upper())
            y -= 12
            
            if y < 1.2 * inch:
                c.showPage()
                y = h - 0.8 * inch
                c.setFont("Helvetica", 9)
    
    y -= 20
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(HexColor("#999999"))
    c.drawString(x, y, "This report is generated automatically for oversight and audit purposes.")
    
    c.save()
    return out_path


def build_multi_proposal_report(out_path: str, proposals_with_votes: list):
    """
    Generate a PDF report for multiple proposals.
    """
    c = canvas.Canvas(out_path, pagesize=LETTER)
    w, h = LETTER
    x = 0.8 * inch
    y = h - 0.8 * inch
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Agent Oversight Summary Report")
    y -= 20
    
    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    c.drawString(x, y - 12, f"Total Proposals: {len(proposals_with_votes)}")
    y -= 36
    
    for i, (proposal, votes) in enumerate(proposals_with_votes, 1):
        if y < 3 * inch:
            c.showPage()
            y = h - 0.8 * inch
        
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y, f"{i}. {proposal.get('title', 'Untitled')}")
        y -= 14
        
        c.setFont("Helvetica", 9)
        c.drawString(x + 20, y, f"Status: {proposal.get('status', 'N/A')} | Risk: {proposal.get('overall_risk', 'N/A')}")
        y -= 12
        
        vote_summary = {}
        for v in votes:
            vote_type = v.get('vote', 'UNKNOWN')
            vote_summary[vote_type] = vote_summary.get(vote_type, 0) + 1
        
        vote_str = ", ".join(f"{k}: {v}" for k, v in vote_summary.items())
        c.drawString(x + 20, y, f"Votes: {vote_str if vote_str else 'None'}")
        y -= 20
    
    c.save()
    return out_path
