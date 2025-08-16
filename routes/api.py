from flask import Blueprint, request, jsonify
from models import Finding, AgentStatus, MarketData
from app import db
from flask import current_app
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

@api_bp.route('/findings', methods=['GET', 'POST'])
def findings():
    """Get or create findings"""
    if request.method == 'GET':
        try:
            # Query parameters
            agent_name = request.args.get('agent_name')
            severity = request.args.get('severity')
            hours = request.args.get('hours', 24, type=int)
            limit = request.args.get('limit', 100, type=int)
            
            # Build query
            query = Finding.query
            
            if agent_name:
                query = query.filter_by(agent_name=agent_name)
            
            if severity:
                query = query.filter_by(severity=severity)
            
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
            logger.error(f"Error creating finding: {e}")
            return jsonify({'error': str(e)}), 500

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
        scheduler = current_app.scheduler
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
        scheduler = current_app.scheduler
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
        
        scheduler = current_app.scheduler
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
        
        market_data = MarketData(
            symbol=data.get('symbol'),
            price=data.get('price'),
            volume=data.get('volume'),
            market_cap=data.get('market_cap'),
            data_source=data.get('data_source'),
            raw_data=data.get('raw_data', {})
        )
        
        db.session.add(market_data)
        db.session.commit()
        
        return jsonify(market_data.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error storing market data: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        # Get basic stats
        total_findings = Finding.query.count()
        active_agents = AgentStatus.query.filter_by(is_active=True).count()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'total_findings': total_findings,
            'active_agents': active_agents
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
