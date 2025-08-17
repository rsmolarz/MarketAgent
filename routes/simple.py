from flask import Blueprint, render_template_string
from models import Finding

simple_bp = Blueprint('simple', __name__)

@simple_bp.route('/simple')
def simple_findings():
    """Ultra-simple findings display - no CSS, no JS, pure HTML"""
    findings = Finding.query.order_by(Finding.timestamp.desc()).limit(10).all()
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SIMPLE MARKET FINDINGS</title>
        <style>
            body { font-family: Arial; margin: 20px; background: white; }
            .finding { border: 2px solid #333; margin: 15px 0; padding: 15px; }
            .success { background: #90EE90; border-color: #32CD32; color: black; }
            .warning { background: #FFD700; border-color: #FFA500; color: black; }
            h1 { color: #000080; font-size: 24px; }
            h3 { color: #8B0000; }
        </style>
    </head>
    <body>
        <h1>📊 SIMPLE MARKET FINDINGS PAGE</h1>
        <p><strong>DATABASE STATUS:</strong> {{ findings|length }} findings loaded successfully</p>
        
        {% if findings %}
            <div class="success">
                <strong>SUCCESS:</strong> Market data is working! {{ findings|length }} findings found.
            </div>
            
            {% for finding in findings %}
            <div class="finding">
                <h3>{{ finding.title }}</h3>
                <p><strong>Agent:</strong> {{ finding.agent_name }}</p>
                <p><strong>Symbol:</strong> {{ finding.symbol or 'N/A' }}</p>
                <p><strong>Severity:</strong> {{ finding.severity }}</p>
                <p><strong>Time:</strong> {{ finding.timestamp }}</p>
                <p><strong>Description:</strong> {{ finding.description }}</p>
                <p><strong>Confidence:</strong> {{ (finding.confidence * 100)|round if finding.confidence else 'N/A' }}%</p>
            </div>
            {% endfor %}
            
        {% else %}
            <div class="warning">
                <strong>NO DATA:</strong> No findings in database.
            </div>
        {% endif %}
        
        <p><a href="/dashboard">Back to Dashboard</a> | <a href="/raw">Raw Data</a></p>
    </body>
    </html>
    """
    
    return render_template_string(html, findings=findings)