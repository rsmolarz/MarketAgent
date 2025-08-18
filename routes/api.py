from flask import Blueprint, request, jsonify
from models import Finding, AgentStatus, MarketData
from app import db
from flask import current_app
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

@api_bp.route('/health')
def api_health():
    """Lightweight JSON health check endpoint for deployment systems"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'Market Inefficiency Detection Platform API'
    }), 200

@api_bp.route('/healthz')  
def api_healthz():
    """Alternative health check endpoint"""
    return jsonify({'status': 'ok'}), 200

@api_bp.route('/findings', methods=['GET', 'POST'])
def findings():
    """Get or create findings"""
    if request.method == 'GET':
        try:
            # Query parameters
            agent_name = request.args.get('agent_name')
            symbol = request.args.get('symbol')
            severity = request.args.get('severity')
            market_type = request.args.get('market_type')
            hours = request.args.get('hours', 24, type=int)
            limit = request.args.get('limit', 100, type=int)
            
            # Build query
            query = Finding.query
            
            if agent_name:
                query = query.filter_by(agent_name=agent_name)
            
            if symbol:
                query = query.filter_by(symbol=symbol)
            
            if severity:
                query = query.filter_by(severity=severity)
            
            if market_type:
                query = query.filter_by(market_type=market_type)
            
            # Filter by time
            if hours:
                start_time = datetime.utcnow() - timedelta(hours=hours)
                query = query.filter(Finding.timestamp >= start_time)
            
            findings = query.order_by(
                Finding.timestamp.desc()
            ).limit(limit).all()
            
            return jsonify([finding.to_dict() for finding in findings])
            
        except Exception as e:
            logger.error(f"Error getting findings: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            finding = Finding()
            finding.agent_name = data.get('agent_name')
            finding.title = data.get('title')
            finding.description = data.get('description')
            finding.severity = data.get('severity', 'medium')
            finding.confidence = data.get('confidence', 0.5)
            finding.finding_metadata = data.get('metadata', {})
            finding.symbol = data.get('symbol')
            finding.market_type = data.get('market_type')
            
            db.session.add(finding)
            db.session.commit()
            
            return jsonify(finding.to_dict()), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating finding: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Default return for unexpected method
    return jsonify({'error': 'Method not allowed'}), 405

@api_bp.route('/agents', methods=['GET'])
def get_agents():
    """Get all agent statuses"""
    try:
        statuses = AgentStatus.query.all()
        return jsonify([status.to_dict() for status in statuses])
        
    except Exception as e:
        logger.error(f"Error getting agents: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/agents/<agent_name>/start', methods=['POST'])
def start_agent(agent_name):
    """Start an agent"""
    try:
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        success = scheduler.start_agent(agent_name)
        if success:
            return jsonify({'message': f'Agent {agent_name} started'})
        else:
            return jsonify({'error': f'Failed to start agent {agent_name}'}), 400
            
    except Exception as e:
        logger.error(f"Error starting agent {agent_name}: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/agents/<agent_name>/stop', methods=['POST'])
def stop_agent(agent_name):
    """Stop an agent"""
    try:
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        success = scheduler.stop_agent(agent_name)
        if success:
            return jsonify({'message': f'Agent {agent_name} stopped'})
        else:
            return jsonify({'error': f'Failed to stop agent {agent_name}'}), 400
            
    except Exception as e:
        logger.error(f"Error stopping agent {agent_name}: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/agents/<agent_name>/interval', methods=['PUT'])
def update_agent_interval(agent_name):
    """Update agent scheduling interval"""
    try:
        data = request.get_json()
        interval = data.get('interval')
        
        if not interval or interval < 1:
            return jsonify({'error': 'Invalid interval'}), 400
        
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        success = scheduler.update_agent_interval(agent_name, interval)
        if success:
            return jsonify({'message': f'Agent {agent_name} interval updated to {interval} minutes'})
        else:
            return jsonify({'error': f'Failed to update agent {agent_name}'}), 400
            
    except Exception as e:
        logger.error(f"Error updating agent interval: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/market_data', methods=['GET'])
def get_market_data():
    """Get current market data for key symbols from recent findings"""
    try:
        # Get recent findings for major market symbols
        symbols = ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA', 'MSFT', 'BTC-USD', 'ETH-USD']
        market_data = []
        
        for symbol in symbols:
            # Get most recent finding for this symbol
            recent_finding = Finding.query.filter_by(symbol=symbol)\
                .filter(Finding.timestamp >= datetime.utcnow() - timedelta(hours=24))\
                .order_by(Finding.timestamp.desc()).first()
            
            if recent_finding:
                # Extract price-related metadata safely
                try:
                    metadata = recent_finding.metadata or {}
                    if hasattr(metadata, 'get'):
                        price_change = metadata.get('price_change', 0)
                    else:
                        # Handle case where metadata is not a dict
                        price_change = 0
                except Exception:
                    price_change = 0
                
                market_data.append({
                    'symbol': symbol,
                    'name': _get_symbol_name(symbol),
                    'price_change': round(price_change * 100, 2) if isinstance(price_change, float) else 0,
                    'last_updated': recent_finding.timestamp.isoformat(),
                    'status': _get_market_status(recent_finding),
                    'findings_count': Finding.query.filter_by(symbol=symbol)
                        .filter(Finding.timestamp >= datetime.utcnow() - timedelta(hours=24)).count()
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

@api_bp.route('/dashboard/stats')
def dashboard_stats():
    """Get dashboard statistics"""
    try:
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get counts
        recent_findings = Finding.query.filter(Finding.timestamp >= now - timedelta(hours=24)).count()
        critical_findings = Finding.query.filter(
            Finding.severity == 'high',
            Finding.timestamp >= now - timedelta(hours=24)
        ).count()
        active_agents = AgentStatus.query.filter_by(is_active=True).count()
        total_agents = AgentStatus.query.count()
        
        return jsonify({
            'recent_findings': recent_findings,
            'critical_findings': critical_findings,
            'active_agents': active_agents,
            'total_agents': total_agents
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/findings/recent')
def recent_findings():
    """Get recent findings"""
    try:
        limit = min(int(request.args.get('limit', 10)), 50)
        findings = Finding.query.filter(
            Finding.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).order_by(Finding.timestamp.desc()).limit(limit).all()
        
        return jsonify([finding.to_dict() for finding in findings])
        
    except Exception as e:
        logger.error(f"Error getting recent findings: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/findings/chart_data')  
def findings_chart_data():
    """Get chart data for findings over time"""
    try:
        days = int(request.args.get('days', 7))
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Group findings by hour for better granularity
        findings_by_hour = db.session.execute(db.text("""
            SELECT 
                DATE_TRUNC('hour', timestamp) as hour,
                COUNT(*) as count,
                severity
            FROM findings 
            WHERE timestamp >= :start_date AND timestamp <= :end_date
            GROUP BY hour, severity
            ORDER BY hour
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Format for Chart.js
        chart_data = {
            'labels': [],
            'datasets': {
                'high': {'label': 'High', 'data': [], 'color': '#dc3545'},
                'medium': {'label': 'Medium', 'data': [], 'color': '#ffc107'},
                'low': {'label': 'Low', 'data': [], 'color': '#28a745'}
            }
        }
        
        # Process data by hour
        current_time = start_date.replace(minute=0, second=0, microsecond=0)
        hour_data = {}
        
        for row in findings_by_hour:
            hour_str = row.hour.strftime('%Y-%m-%d %H:00')
            if hour_str not in hour_data:
                hour_data[hour_str] = {'high': 0, 'medium': 0, 'low': 0}
            hour_data[hour_str][row.severity] = row.count
        
        # Fill in missing hours and create final chart data
        while current_time <= end_date:
            hour_str = current_time.strftime('%Y-%m-%d %H:00')
            display_label = current_time.strftime('%m/%d %H:00')
            
            chart_data['labels'].append(display_label)
            
            data = hour_data.get(hour_str, {'high': 0, 'medium': 0, 'low': 0})
            chart_data['datasets']['high']['data'].append(data['high'])
            chart_data['datasets']['medium']['data'].append(data['medium'])
            chart_data['datasets']['low']['data'].append(data['low'])
            
            current_time += timedelta(hours=1)
        
        return jsonify(chart_data)
        
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/market_data', methods=['POST'])
def store_market_data():
    """Store market data"""
    try:
        data = request.get_json()
        
        market_data = MarketData()
        market_data.symbol = data.get('symbol')
        market_data.price = data.get('price')
        market_data.volume = data.get('volume')
        market_data.market_cap = data.get('market_cap')
        market_data.data_source = data.get('data_source')
        market_data.raw_data = data.get('raw_data', {})
        
        db.session.add(market_data)
        db.session.commit()
        
        return jsonify(market_data.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error storing market data: {e}")
        return jsonify({'error': str(e)}), 500



@api_bp.route('/agents/<agent_name>/run', methods=['POST'])
def run_agent_now(agent_name):
    """Manually run an agent immediately"""
    try:
        scheduler = current_app.extensions.get('scheduler')
        if not scheduler:
            return jsonify({'error': 'Scheduler not available'}), 503
        
        # Run the agent immediately
        success = scheduler.run_agent_immediately(agent_name)
        if success:
            return jsonify({'message': f'Agent {agent_name} executed successfully'})
        else:
            return jsonify({'error': f'Failed to run agent {agent_name}'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500
