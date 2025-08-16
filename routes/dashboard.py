from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from models import Finding, AgentStatus, MarketData
from app import db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/health')
def health_check():
    """Dedicated health check endpoint for deployment systems"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        return 'OK', 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return 'UNHEALTHY', 500

@dashboard_bp.route('/')
def index():
    """Main dashboard page - handles both web UI and deployment health checks"""
    # Check if this is a health check request from deployment systems
    user_agent = request.headers.get('User-Agent', '').lower()
    accept_header = request.headers.get('Accept', '').lower()
    
    # Enhanced health check detection for all major deployment platforms
    is_health_check = (
        # CLI tools without browser headers
        ('curl' in user_agent and 'text/html' not in accept_header) or
        'wget' in user_agent or
        # Health monitoring systems
        'health' in user_agent or
        'monitor' in user_agent or
        'probe' in user_agent or
        'check' in user_agent or
        'uptime' in user_agent or
        # Kubernetes health checks
        'kube-probe' in user_agent or
        # Cloud provider health checks
        'googlehc' in user_agent or  # Google Cloud health check
        'alb-healthchecker' in user_agent or  # AWS ALB health check
        'cloud-run' in user_agent or  # Google Cloud Run health check
        'azure-health' in user_agent or  # Azure health check
        'netlify' in user_agent or  # Netlify health check
        'render' in user_agent or  # Render health check
        'heroku' in user_agent or  # Heroku health check
        # Generic patterns for deployment systems
        (accept_header == '*/*' and 'mozilla' not in user_agent and 'chrome' not in user_agent and 'safari' not in user_agent) or
        # Direct health check parameter
        request.args.get('health') is not None or
        # No user agent (some load balancers)
        user_agent == ''
    )
    
    if is_health_check:
        # Return immediate 200 OK for health checks - no database operations
        return 'OK', 200
    
    # Normal web browser request - return the dashboard
    try:
        return render_template('dashboard.html')
    except Exception as e:
        logger.error(f"Dashboard rendering failed: {e}")
        return f"Application is running but dashboard unavailable: {str(e)}", 200

@dashboard_bp.route('/agents')
def agents():
    """Agent management page"""
    return render_template('agents.html')

@dashboard_bp.route('/findings')
def findings():
    """Findings page"""
    return render_template('findings.html')

@dashboard_bp.route('/api/dashboard/stats')
def dashboard_stats():
    """Get dashboard statistics"""
    try:
        # Get recent findings count
        recent_findings = Finding.query.filter(
            Finding.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        # Get active agents count
        active_agents = AgentStatus.query.filter_by(is_active=True).count()
        
        # Get total agents count
        total_agents = AgentStatus.query.count()
        
        # Get high severity findings in last hour
        critical_findings = Finding.query.filter(
            Finding.timestamp >= datetime.utcnow() - timedelta(hours=1),
            Finding.severity.in_(['high', 'critical'])
        ).count()
        
        return jsonify({
            'recent_findings': recent_findings,
            'active_agents': active_agents,
            'total_agents': total_agents,
            'critical_findings': critical_findings
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/findings/recent')
def recent_findings():
    """Get recent findings for dashboard"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        findings = Finding.query.order_by(
            Finding.timestamp.desc()
        ).limit(limit).all()
        
        return jsonify([finding.to_dict() for finding in findings])
        
    except Exception as e:
        logger.error(f"Error getting recent findings: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/findings/chart_data')
def findings_chart_data():
    """Get findings data for charts"""
    try:
        days = request.args.get('days', 7, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get findings by hour for the chart
        findings = Finding.query.filter(
            Finding.timestamp >= start_date
        ).order_by(Finding.timestamp.asc()).all()
        
        # Group by hour
        hourly_data = {}
        for finding in findings:
            hour_key = finding.timestamp.strftime('%Y-%m-%d %H:00')
            if hour_key not in hourly_data:
                hourly_data[hour_key] = {'high': 0, 'medium': 0, 'low': 0}
            hourly_data[hour_key][finding.severity] += 1
        
        # Convert to chart format
        labels = list(hourly_data.keys())
        high_data = [hourly_data[label]['high'] for label in labels]
        medium_data = [hourly_data[label]['medium'] for label in labels]
        low_data = [hourly_data[label]['low'] for label in labels]
        
        return jsonify({
            'labels': labels,
            'datasets': [
                {
                    'label': 'High Severity',
                    'data': high_data,
                    'backgroundColor': 'rgba(220, 53, 69, 0.5)',
                    'borderColor': 'rgba(220, 53, 69, 1)'
                },
                {
                    'label': 'Medium Severity',
                    'data': medium_data,
                    'backgroundColor': 'rgba(255, 193, 7, 0.5)',
                    'borderColor': 'rgba(255, 193, 7, 1)'
                },
                {
                    'label': 'Low Severity',
                    'data': low_data,
                    'backgroundColor': 'rgba(40, 167, 69, 0.5)',
                    'borderColor': 'rgba(40, 167, 69, 1)'
                }
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/market_data')
def market_data():
    """Get recent market data"""
    try:
        symbols = request.args.getlist('symbols')
        if not symbols:
            symbols = ['BTC', 'ETH', 'SPY', 'VIX']
        
        data = {}
        for symbol in symbols:
            recent_data = MarketData.query.filter_by(
                symbol=symbol
            ).order_by(MarketData.timestamp.desc()).first()
            
            if recent_data:
                data[symbol] = recent_data.to_dict()
        
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return jsonify({'error': str(e)}), 500
