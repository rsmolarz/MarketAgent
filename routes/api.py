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
