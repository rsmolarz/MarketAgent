from flask import Blueprint, Response
from models import Finding
from datetime import datetime
import json

raw_bp = Blueprint('raw', __name__)

@raw_bp.route('/raw')
def raw_data():
    """Raw market data in plain text - no templates, no JavaScript"""
    try:
        findings = Finding.query.order_by(Finding.timestamp.desc()).limit(20).all()
        
        output = []
        output.append("=== MARKET DATA VERIFICATION ===")
        output.append(f"Total findings: {len(findings)}")
        output.append(f"Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        output.append("")
        
        if not findings:
            output.append("❌ NO FINDINGS FOUND")
            output.append("Database appears empty or inaccessible")
        else:
            output.append("✅ LATEST MARKET FINDINGS:")
            output.append("")
            
            for i, finding in enumerate(findings[:10], 1):
                minutes_ago = int((datetime.utcnow() - finding.timestamp).total_seconds() / 60)
                output.append(f"{i}. {finding.title}")
                output.append(f"   Agent: {finding.agent_name}")
                output.append(f"   Symbol: {finding.symbol or 'N/A'}")
                output.append(f"   Severity: {finding.severity}")
                output.append(f"   Time: {finding.timestamp.strftime('%H:%M:%S')} ({minutes_ago}min ago)")
                output.append(f"   Description: {finding.description[:100]}...")
                output.append("")
        
        return Response('\n'.join(output), mimetype='text/plain')
        
    except Exception as e:
        error_output = []
        error_output.append("=== ERROR ACCESSING MARKET DATA ===")
        error_output.append(f"Error: {str(e)}")
        error_output.append(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        return Response('\n'.join(error_output), mimetype='text/plain')