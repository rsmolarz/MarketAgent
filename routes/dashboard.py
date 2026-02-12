from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import current_user
from models import Finding, AgentStatus, MarketData, db
from datetime import datetime, timedelta
import logging
from services.llm_council import analyze_with_council_sync
from replit_auth import require_login, is_user_whitelisted

# Import and register raw data blueprint
from routes.raw import raw_bp

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/health')
def health_check():
    """Fast health check endpoint for deployment systems - NO blocking operations"""
    # Return immediately without any database or external calls
    return 'OK', 200

@dashboard_bp.route('/')
def index():
    """Main dashboard / landing page"""
    try:
        if current_user.is_authenticated and is_user_whitelisted(current_user.email):
            return render_template('dashboard.html', user=current_user)
        else:
            return render_template('landing.html')
    except Exception as e:
        logger.error(f"Dashboard rendering failed: {e}")
        return render_template('landing.html')

@dashboard_bp.route('/agents')
@require_login
def agents():
    """Agent management page"""
    return render_template('agents.html')

@dashboard_bp.route('/system-status')
@require_login
def system_status():
    """System status page showing heartbeat and system health"""
    return render_template('system_status.html')

@dashboard_bp.route('/meta')
@require_login
def meta_dashboard():
    """Meta supervisor dashboard showing agent performance and allocation"""
    import json
    from pathlib import Path
    p = Path("meta_supervisor/reports/meta_report.json")
    report = json.loads(p.read_text()) if p.exists() else {}
    return render_template('meta_dashboard.html', report=report)


@dashboard_bp.route('/heatmap')
@require_login
def heatmap():
    """Forward return heatmap visualization"""
    return render_template('heatmap.html')

@dashboard_bp.route('/findings')
@require_login
def findings():
    """Findings page with server-side filtering"""
    try:
        # Get filter parameters from request
        agent_name = request.args.get('agent_name', '')
        symbol = request.args.get('symbol', '')
        severity = request.args.get('severity', '')
        market_type = request.args.get('market_type', '')
        hours = request.args.get('hours', '24')
        limit = min(int(request.args.get('limit', 50)), 500)  # Cap at 500
        
        # Build query with filters
        query = Finding.query
        
        if agent_name:
            query = query.filter(Finding.agent_name.ilike(f'%{agent_name}%'))
        if symbol:
            query = query.filter(Finding.symbol.ilike(f'%{symbol}%'))
        if severity:
            query = query.filter(Finding.severity == severity)
        if market_type:
            query = query.filter(Finding.market_type == market_type)
        
        # Time filter
        if hours:
            time_threshold = datetime.utcnow() - timedelta(hours=int(hours))
            query = query.filter(Finding.timestamp >= time_threshold)
        
        # Execute query
        findings = query.order_by(Finding.timestamp.desc()).limit(limit).all()
        
        findings_data = []
        for finding in findings:
            findings_data.append({
                'id': finding.id,
                'title': finding.title,
                'description': finding.description,
                'agent_name': finding.agent_name,
                'symbol': finding.symbol,
                'severity': finding.severity,
                'confidence': finding.confidence,
                'market_type': finding.market_type,
                'timestamp': finding.timestamp.isoformat() + 'Z',
                'metadata': finding.metadata or {}
            })
        
        logger.info(f"Returning {len(findings_data)} findings to template")
        return render_template('findings.html', embedded_findings=findings_data)
    except Exception as e:
        logger.error(f"Error loading findings: {e}")
        return render_template('findings.html', embedded_findings=[], error=str(e))

@dashboard_bp.route('/archive')
@require_login
def archive():
    """Archive page showing all historical findings"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)
        
        agent_name = request.args.get('agent_name', '')
        symbol = request.args.get('symbol', '')
        severity = request.args.get('severity', '')
        market_type = request.args.get('market_type', '')
        
        query = Finding.query.filter(Finding.agent_name != 'HeartbeatAgent')
        
        if agent_name:
            query = query.filter(Finding.agent_name.ilike(f'%{agent_name}%'))
        if symbol:
            query = query.filter(Finding.symbol.ilike(f'%{symbol}%'))
        if severity:
            query = query.filter(Finding.severity == severity)
        if market_type:
            query = query.filter(Finding.market_type == market_type)
        
        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page
        
        findings = query.order_by(Finding.timestamp.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page).all()
        
        findings_data = []
        for finding in findings:
            findings_data.append({
                'id': finding.id,
                'title': finding.title,
                'description': finding.description,
                'agent_name': finding.agent_name,
                'symbol': finding.symbol,
                'severity': finding.severity,
                'confidence': finding.confidence,
                'market_type': finding.market_type,
                'timestamp': finding.timestamp.isoformat() + 'Z',
                'metadata': finding.finding_metadata or {}
            })
        
        return render_template('archive.html', 
                             findings=findings_data,
                             page=page,
                             per_page=per_page,
                             total_count=total_count,
                             total_pages=total_pages)
    except Exception as e:
        logger.error(f"Error loading archive: {e}")
        return render_template('archive.html', findings=[], error=str(e), 
                             page=1, per_page=50, total_count=0, total_pages=0)

@dashboard_bp.route('/simple')
def simple_findings():
    """Simple findings page with direct server-side rendering"""
    try:
        findings = Finding.query.order_by(Finding.timestamp.desc()).limit(50).all()
        return render_template('simple_findings.html', findings=findings)
    except Exception as e:
        logger.error(f"Error loading findings: {e}")
        return f"Error loading findings: {e}", 500

@dashboard_bp.route('/raw')
def raw_data():
    """Raw market data in plain text - no templates, no JavaScript"""
    from flask import Response
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

@dashboard_bp.route('/api/dashboard/stats')
def dashboard_stats():
    """Get dashboard statistics"""
    try:
        # Get time window from query parameter (default 24 hours)
        hours = request.args.get('hours', 24, type=int)
        hours = max(1, min(hours, 168))  # Clamp between 1 hour and 7 days
        
        # Get recent findings count (excluding heartbeats)
        recent_findings = Finding.query.filter(
            Finding.timestamp >= datetime.utcnow() - timedelta(hours=hours),
            Finding.agent_name != 'HeartbeatAgent'
        ).count()
        
        # Get active agents count
        active_agents = AgentStatus.query.filter_by(is_active=True).count()
        
        # Get total agents count
        total_agents = AgentStatus.query.count()
        
        # Get high severity findings in last hour (excluding heartbeats)
        critical_findings = Finding.query.filter(
            Finding.timestamp >= datetime.utcnow() - timedelta(hours=1),
            Finding.severity.in_(['high', 'critical']),
            Finding.agent_name != 'HeartbeatAgent'
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
    """Get recent findings for dashboard (excluding internal agents)"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        # Exclude internal agents from main dashboard (show only market findings)
        # HeartbeatAgent, CodeQualityGuardianAgent, SystemUpgradeAdvisorAgent are admin-only
        internal_agents = ['HeartbeatAgent', 'CodeQualityGuardianAgent', 'SystemUpgradeAdvisorAgent']
        findings = Finding.query.filter(
            ~Finding.agent_name.in_(internal_agents)
        ).order_by(
            Finding.timestamp.desc()
        ).limit(limit).all()
        
        return jsonify([finding.to_dict() for finding in findings])
        
    except Exception as e:
        logger.error(f"Error getting recent findings: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/heartbeats')
def heartbeats():
    """Get system heartbeat logs"""
    try:
        limit = request.args.get('limit', 100, type=int)
        hours = request.args.get('hours', 24, type=int)
        
        # Get only HeartbeatAgent findings
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        heartbeats = Finding.query.filter(
            Finding.agent_name == 'HeartbeatAgent',
            Finding.timestamp >= time_threshold
        ).order_by(
            Finding.timestamp.desc()
        ).limit(limit).all()
        
        return jsonify([hb.to_dict() for hb in heartbeats])
        
    except Exception as e:
        logger.error(f"Error getting heartbeats: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/findings/chart_data')
def findings_chart_data():
    """Get findings data for charts"""
    try:
        days = request.args.get('days', 7, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get findings by hour for the chart (excluding internal agents)
        internal_agents = ['HeartbeatAgent', 'CodeQualityGuardianAgent', 'SystemUpgradeAdvisorAgent']
        findings = Finding.query.filter(
            Finding.timestamp >= start_date,
            ~Finding.agent_name.in_(internal_agents)
        ).order_by(Finding.timestamp.asc()).all()
        
        # Group by hour
        hourly_data = {}
        for finding in findings:
            hour_key = finding.timestamp.strftime('%Y-%m-%d %H:00')
            if hour_key not in hourly_data:
                hourly_data[hour_key] = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
            severity = finding.severity if finding.severity in ['critical', 'high', 'medium', 'low', 'info'] else 'low'
            hourly_data[hour_key][severity] += 1
        
        # Convert to chart format
        labels = list(hourly_data.keys())
        critical_data = [hourly_data[label]['critical'] for label in labels]
        high_data = [hourly_data[label]['high'] for label in labels]
        medium_data = [hourly_data[label]['medium'] for label in labels]
        low_data = [hourly_data[label]['low'] + hourly_data[label]['info'] for label in labels]
        
        return jsonify({
            'labels': labels,
            'datasets': [
                {
                    'label': 'Critical',
                    'data': critical_data,
                    'backgroundColor': 'rgba(139, 0, 0, 0.5)',
                    'borderColor': 'rgba(139, 0, 0, 1)'
                },
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
    """Get current market data for key symbols from recent findings"""
    try:
        # Get time window from query parameter (default 24 hours)
        hours = request.args.get('hours', 24, type=int)
        hours = max(1, min(hours, 168))  # Clamp between 1 hour and 7 days
        
        # Get recent findings for major market symbols
        symbols = ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA', 'MSFT', 'BTC-USD', 'ETH-USD']
        market_data = []
        
        for symbol in symbols:
            # Get most recent finding for this symbol
            recent_finding = Finding.query.filter_by(symbol=symbol)\
                .filter(Finding.timestamp >= datetime.utcnow() - timedelta(hours=hours))\
                .order_by(Finding.timestamp.desc()).first()
            
            if recent_finding:
                # Extract price-related metadata safely
                try:
                    # Use the correct attribute name from the model
                    metadata = recent_finding.finding_metadata or {}
                    if isinstance(metadata, dict):
                        price_change = metadata.get('price_change', 0)
                    else:
                        price_change = 0
                except Exception:
                    price_change = 0
                
                market_data.append({
                    'symbol': symbol,
                    'name': _get_symbol_name(symbol),
                    'price_change': round(price_change * 100, 2) if isinstance(price_change, (int, float)) else 0,
                    'last_updated': recent_finding.timestamp.isoformat(),
                    'status': _get_market_status(recent_finding),
                    'findings_count': Finding.query.filter_by(symbol=symbol)
                        .filter(Finding.timestamp >= datetime.utcnow() - timedelta(hours=hours)).count()
                })
        
        return jsonify(market_data)
        
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return jsonify({'error': str(e)}), 500

def _get_symbol_name(symbol):
    """Get friendly name for symbol"""
    names = {
        'SPY': 'S&P 500',
        'QQQ': 'NASDAQ',
        'AAPL': 'Apple',
        'TSLA': 'Tesla', 
        'NVDA': 'NVIDIA',
        'MSFT': 'Microsoft',
        'BTC-USD': 'Bitcoin',
        'ETH-USD': 'Ethereum'
    }
    return names.get(symbol, symbol)

def _get_market_status(finding):
    """Get market status based on finding severity and type"""
    if finding.severity == 'high':
        return 'alert'
    elif finding.severity == 'medium':
        return 'warning'
    else:
        return 'normal'


@dashboard_bp.route('/dashboard/api/agents')
def api_agents():
    """Get all agent statuses for the agents dashboard page"""
    try:
        statuses = AgentStatus.query.all()
        return jsonify([{
            'agent_name': s.agent_name,
            'is_active': s.is_active,
            'last_run': s.last_run.isoformat() if s.last_run else None,
            'last_error': s.last_error,
            'run_count': s.run_count,
            'error_count': s.error_count,
            'schedule_interval': s.schedule_interval
        } for s in statuses])
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/analyze_alert', methods=['POST'])
def analyze_alert():
    """Analyze an alert using LLM Council (GPT + Claude + Gemini) for consensus"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        finding_id = data.get('finding_id')
        
        if finding_id:
            finding = Finding.query.get(finding_id)
            if not finding:
                return jsonify({'success': False, 'error': 'Finding not found'}), 404
            
            finding_data = {
                'id': finding.id,
                'title': finding.title,
                'description': finding.description,
                'agent_name': finding.agent_name,
                'symbol': finding.symbol,
                'severity': finding.severity,
                'confidence': finding.confidence,
                'market_type': finding.market_type,
                'timestamp': finding.timestamp.isoformat() if finding.timestamp else None,
                'metadata': finding.finding_metadata or {}
            }
        else:
            finding_data = data.get('finding_data', {})
            if not finding_data:
                return jsonify({'success': False, 'error': 'No finding data provided'}), 400
        
        result = analyze_with_council_sync(finding_data)
        
        if result.get('error') == 'budget_exceeded':
            return jsonify(result), 402
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in analyze_alert endpoint: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/dashboard/api/decay_chart')
def api_decay_chart():
    """Generate SPY price vs agent decay chart with uncertainty bands"""
    try:
        import yfinance as yf
        from meta.decay import _decay, generate_decay_chart
        
        period = request.args.get('period', '1y')
        
        spy = yf.download("SPY", period=period, progress=False)
        if spy.empty:
            return jsonify({'error': 'Failed to fetch SPY data'}), 500
        
        statuses = AgentStatus.query.filter_by(is_active=True).all()
        agents = [s.agent_name for s in statuses[:6]]
        
        if not agents:
            agents = ['MacroWatcherAgent', 'WhaleWalletWatcherAgent', 'ArbitrageFinderAgent']
        
        period_days = {
            '6mo': 126,
            '1y': 252,
            '2y': 504,
            '5y': 1260,
            'max': len(spy)
        }.get(period, 252)
        
        chart_base64 = generate_decay_chart(spy, agents, _decay, period_days)
        
        return jsonify({
            'chart': chart_base64,
            'agents': agents,
            'period': period,
            'data_points': len(spy)
        })
        
    except Exception as e:
        logger.error(f"Error generating decay chart: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/dashboard/api/decay_data')
def api_decay_data():
    """Get agent decay data with uncertainty bands as JSON"""
    try:
        from meta.decay import _decay
        
        statuses = AgentStatus.query.filter_by(is_active=True).all()
        agents = [s.agent_name for s in statuses]
        
        last_n = int(request.args.get('last_n', 100))
        
        result = {}
        for agent in agents:
            decay_vals, upper, lower = _decay.compute_uncertainty_band(agent, last_n=last_n)
            result[agent] = {
                'decay': decay_vals.tolist(),
                'upper_band': upper.tolist(),
                'lower_band': lower.tolist(),
                'current': float(_decay.get(agent)),
                'uncertainty': float(_decay.get_uncertainty(agent))
            }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting decay data: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/dashboard/api/findings')
def api_findings():
    """Get findings for the dashboard (public endpoint)"""
    try:
        agent_name = request.args.get('agent_name')
        symbol = request.args.get('symbol')
        severity = request.args.get('severity')
        market_type = request.args.get('market_type')
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)
        
        query = Finding.query
        
        if agent_name:
            query = query.filter_by(agent_name=agent_name)
        
        if symbol:
            query = query.filter_by(symbol=symbol)
        
        if severity:
            query = query.filter_by(severity=severity)
        
        if market_type:
            query = query.filter_by(market_type=market_type)
        
        if hours:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            query = query.filter(Finding.timestamp >= start_time)
        
        findings = query.order_by(
            Finding.timestamp.desc()
        ).limit(limit).all()
        
        return jsonify([{
            'id': f.id,
            'agent_name': f.agent_name,
            'title': f.title,
            'description': f.description,
            'symbol': f.symbol,
            'severity': f.severity,
            'confidence': f.confidence,
            'market_type': f.market_type,
            'timestamp': f.timestamp.isoformat() if f.timestamp else None,
            'finding_metadata': f.finding_metadata
        } for f in findings])
        
    except Exception as e:
        logger.error(f"Error getting findings: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/dashboard/api/stats')
def api_dashboard_stats():
    """Get dashboard statistics (public endpoint)"""
    try:
        hours = request.args.get('hours', 24, type=int)
        hours = max(1, min(hours, 168))
        
        recent_findings = Finding.query.filter(
            Finding.timestamp >= datetime.utcnow() - timedelta(hours=hours),
            Finding.agent_name != 'HeartbeatAgent'
        ).count()
        
        active_agents = AgentStatus.query.filter_by(is_active=True).count()
        total_agents = AgentStatus.query.count()
        
        critical_findings = Finding.query.filter(
            Finding.timestamp >= datetime.utcnow() - timedelta(hours=1),
            Finding.severity.in_(['high', 'critical']),
            Finding.agent_name != 'HeartbeatAgent'
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


@dashboard_bp.route('/dashboard/api/findings/recent')
def api_recent_findings():
    """Get recent findings for dashboard (public endpoint)"""
    try:
        limit = request.args.get('limit', 10, type=int)
        
        findings = Finding.query.filter(
            Finding.agent_name != 'HeartbeatAgent'
        ).order_by(
            Finding.timestamp.desc()
        ).limit(limit).all()
        
        return jsonify([finding.to_dict() for finding in findings])
        
    except Exception as e:
        logger.error(f"Error getting recent findings: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/dashboard/api/chart_data')
def api_chart_data():
    """Get findings data for charts (public endpoint)"""
    try:
        days = request.args.get('days', 7, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Exclude internal agents from chart data
        internal_agents = ['HeartbeatAgent', 'CodeQualityGuardianAgent', 'SystemUpgradeAdvisorAgent']
        findings = Finding.query.filter(
            Finding.timestamp >= start_date,
            ~Finding.agent_name.in_(internal_agents)
        ).order_by(Finding.timestamp.asc()).all()
        
        hourly_data = {}
        for finding in findings:
            hour_key = finding.timestamp.strftime('%Y-%m-%d %H:00')
            if hour_key not in hourly_data:
                hourly_data[hour_key] = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
            severity = finding.severity if finding.severity in ['critical', 'high', 'medium', 'low', 'info'] else 'low'
            hourly_data[hour_key][severity] += 1
        
        labels = list(hourly_data.keys())
        critical_data = [hourly_data[label]['critical'] for label in labels]
        high_data = [hourly_data[label]['high'] for label in labels]
        medium_data = [hourly_data[label]['medium'] for label in labels]
        low_data = [hourly_data[label]['low'] + hourly_data[label]['info'] for label in labels]
        
        return jsonify({
            'labels': labels,
            'datasets': [
                {'label': 'Critical', 'data': critical_data, 'backgroundColor': 'rgba(139, 0, 0, 0.5)', 'borderColor': 'rgba(139, 0, 0, 1)'},
                {'label': 'High Severity', 'data': high_data, 'backgroundColor': 'rgba(220, 53, 69, 0.5)', 'borderColor': 'rgba(220, 53, 69, 1)'},
                {'label': 'Medium Severity', 'data': medium_data, 'backgroundColor': 'rgba(255, 193, 7, 0.5)', 'borderColor': 'rgba(255, 193, 7, 1)'},
                {'label': 'Low Severity', 'data': low_data, 'backgroundColor': 'rgba(40, 167, 69, 0.5)', 'borderColor': 'rgba(40, 167, 69, 1)'}
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/dashboard/api/market_data')
def api_market_data():
    """Get current market data (public endpoint)"""
    try:
        hours = request.args.get('hours', 24, type=int)
        hours = max(1, min(hours, 168))
        
        symbols = ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA', 'MSFT', 'BTC-USD', 'ETH-USD']
        market_data = []
        
        for symbol in symbols:
            recent_finding = Finding.query.filter_by(symbol=symbol)\
                .filter(Finding.timestamp >= datetime.utcnow() - timedelta(hours=hours))\
                .order_by(Finding.timestamp.desc()).first()
            
            if recent_finding:
                try:
                    metadata = recent_finding.finding_metadata or {}
                    if isinstance(metadata, dict):
                        price_change = metadata.get('price_change', 0)
                    else:
                        price_change = 0
                except Exception:
                    price_change = 0
                
                market_data.append({
                    'symbol': symbol,
                    'name': _get_symbol_name(symbol),
                    'price_change': round(price_change * 100, 2) if isinstance(price_change, (int, float)) else 0,
                    'last_updated': recent_finding.timestamp.isoformat(),
                    'status': _get_market_status(recent_finding),
                    'findings_count': Finding.query.filter_by(symbol=symbol)
                        .filter(Finding.timestamp >= datetime.utcnow() - timedelta(hours=hours)).count()
                })
        
        return jsonify(market_data)
        
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/dashboard/api/decay_heatmap')
def api_decay_heatmap():
    """Get agent decay heatmap data by regime (public endpoint)"""
    try:
        from meta.decay_heatmap import decay_heatmap
        
        heatmap_data = decay_heatmap.get_heatmap_data()
        
        return jsonify(heatmap_data)
        
    except Exception as e:
        logger.error(f"Error getting decay heatmap: {e}")
        return jsonify({
            'regimes': [],
            'agents': [],
            'matrix': [],
            'classifications': {},
            'error': str(e)
        })


@dashboard_bp.route('/dashboard/api/decay_heatmap/chart')
def api_decay_heatmap_chart():
    """Generate a matplotlib heatmap chart as PNG"""
    try:
        from meta.decay_heatmap import decay_heatmap
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        import io
        from flask import Response
        
        heatmap_data = decay_heatmap.get_heatmap_data()
        
        if not heatmap_data['regimes'] or not heatmap_data['agents']:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.text(0.5, 0.5, 'Insufficient data for heatmap\n(collecting samples...)',
                   ha='center', va='center', fontsize=14, color='gray')
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
        else:
            raw_matrix = heatmap_data['matrix']
            matrix = np.array([[0.5 if v is None else float(v) for v in row] for row in raw_matrix], dtype=float)
            matrix = np.nan_to_num(matrix, nan=0.5)
            
            fig, ax = plt.subplots(figsize=(max(12, len(heatmap_data['agents']) * 0.8), 
                                            max(4, len(heatmap_data['regimes']) * 0.6)))
            
            cmap = plt.cm.RdYlGn
            im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=1, aspect='auto')
            
            ax.set_xticks(np.arange(len(heatmap_data['agents'])))
            ax.set_yticks(np.arange(len(heatmap_data['regimes'])))
            ax.set_xticklabels(heatmap_data['agents'], rotation=45, ha='right', fontsize=9)
            ax.set_yticklabels(heatmap_data['regimes'], fontsize=10)
            
            for i in range(len(heatmap_data['regimes'])):
                for j in range(len(heatmap_data['agents'])):
                    val = matrix[i, j]
                    text_color = 'white' if val < 0.4 or val > 0.7 else 'black'
                    ax.text(j, i, f'{val:.2f}', ha='center', va='center', 
                           color=text_color, fontsize=8, fontweight='bold')
            
            ax.set_title('Agent Decay by Market Regime', fontsize=14, fontweight='bold', pad=10)
            ax.set_xlabel('Agent', fontsize=11)
            ax.set_ylabel('Regime', fontsize=11)
            
            cbar = fig.colorbar(im, ax=ax, shrink=0.8)
            cbar.set_label('Decay Multiplier (0=dead, 1=strong)', fontsize=9)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        
        return Response(buf.getvalue(), mimetype='image/png')
        
    except Exception as e:
        logger.error(f"Error generating decay heatmap chart: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/dashboard/api/substitutions')
def api_substitutions():
    """Get agent substitution map (public endpoint)"""
    try:
        from meta.substitution_map import substitution_map
        
        report = substitution_map.get_substitution_report()
        
        return jsonify(report)
        
    except Exception as e:
        logger.error(f"Error getting substitutions: {e}")
        return jsonify({
            'last_built': None,
            'total_substitutions': 0,
            'by_regime': {},
            'error': str(e)
        })


@dashboard_bp.route('/dashboard/api/substitutions/<regime>')
def api_substitutions_for_regime(regime: str):
    """Get substitutions for a specific regime (public endpoint)"""
    try:
        from meta.substitution_map import substitution_map
        
        subs = substitution_map.get_substitutions_for_regime(regime)
        
        return jsonify({
            'regime': regime,
            'substitutions': subs
        })
        
    except Exception as e:
        logger.error(f"Error getting substitutions for regime {regime}: {e}")
        return jsonify({
            'regime': regime,
            'substitutions': [],
            'error': str(e)
        })


@dashboard_bp.route('/api/ta_overlay')
@require_login
def api_ta_overlay():
    """TA overlay data for candlestick + RSI + signal markers chart"""
    try:
        symbol = request.args.get("symbol", "SPY")
        period = request.args.get("period", "6mo")

        rows = (
            Finding.query
            .order_by(Finding.timestamp.desc())
            .limit(500)
            .all()
        )
        findings = []
        for r in rows:
            findings.append({
                "id": getattr(r, "id", None),
                "title": r.title,
                "severity": r.severity,
                "confidence": r.confidence,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "symbol": r.symbol,
                "agent_name": r.agent_name,
            })

        from services.ta_overlay_service import build_ta_overlay
        payload = build_ta_overlay(symbol=symbol, period=period, findings=findings)
        return jsonify(payload)
    except Exception as e:
        logger.error(f"TA overlay error: {e}")
        return jsonify({"ok": False, "reason": str(e)}), 500


@dashboard_bp.route('/api/schwab_status')
@require_login
def api_schwab_status():
    """Schwab/Thinkorswim API connection status"""
    try:
        from data_sources.schwab_client import get_schwab_client
        client = get_schwab_client()
        return jsonify(client.status())
    except Exception as e:
        logger.error(f"Schwab status error: {e}")
        return jsonify({"configured": False, "error": str(e)})


@dashboard_bp.route('/api/ta_regime')
@require_login
def api_ta_regime():
    """Current TA regime classification (trend vs mean-reversion)"""
    try:
        symbol = request.args.get("symbol", "SPY")
        period = request.args.get("period", "1y")
        
        from data_sources.yahoo_finance_client import YahooFinanceClient
        from ta.regime import classify_ta_regime
        
        yahoo = YahooFinanceClient()
        df = yahoo.get_price_data(symbol, period=period)
        
        if df is None or df.empty:
            return jsonify({"ok": False, "reason": "no_data"})
        
        regime = classify_ta_regime(df)
        regime["symbol"] = symbol
        regime["ok"] = True
        
        return jsonify(regime)
    except Exception as e:
        logger.error(f"TA regime error: {e}")
        return jsonify({"ok": False, "reason": str(e)}), 500