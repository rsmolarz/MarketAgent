"""
PHASE 1 FIX: Agent Telemetry Collector
Collects and aggregates agent performance metrics
"""

import os
import json
from datetime import datetime
from collections import defaultdict

class AgentTelemetryCollector:
    """Collect and aggregate agent performance telemetry"""
    
    def __init__(self):
        self.metrics = {}
        self.enabled = os.getenv('ENABLE_TELEMETRY', 'true').lower() == 'true'
        self.batch_size = int(os.getenv('TELEMETRY_BATCH_SIZE', '100'))
        self.flush_interval = int(os.getenv('TELEMETRY_FLUSH_INTERVAL', '300'))
    
    def record_agent_run(self, agent_name, execution_time, findings_count=0, success=True, error_msg=None):
        """Record a single agent run
        
        Args:
            agent_name (str): Name of the agent
            execution_time (float): Time taken in seconds
            findings_count (int): Number of findings/signals generated
            success (bool): Whether run was successful
            error_msg (str): Error message if failed
        """
        if not self.enabled:
            return
        
        if agent_name not in self.metrics:
            self.metrics[agent_name] = {
                'total_runs': 0,
                'total_time': 0.0,
                'total_findings': 0,
                'successes': 0,
                'failures': 0,
                'errors': [],
                'last_run': None,
                'first_run': None,
                'avg_time': 0.0,
                'success_rate': 0.0
            }
        
        m = self.metrics[agent_name]
        m['total_runs'] += 1
        m['total_time'] += execution_time
        m['total_findings'] += findings_count
        m['last_run'] = datetime.now().isoformat()
        
        if m['first_run'] is None:
            m['first_run'] = m['last_run']
        
        if success:
            m['successes'] += 1
        else:
            m['failures'] += 1
            if error_msg and len(m['errors']) < 10:  # Keep last 10 errors
                m['errors'].append({
                    'timestamp': m['last_run'],
                    'error': error_msg
                })
        
        m['avg_time'] = m['total_time'] / m['total_runs']
        m['success_rate'] = m['successes'] / m['total_runs'] if m['total_runs'] > 0 else 0
    
    def get_metrics(self, agent_name=None):
        """Get telemetry metrics
        
        Args:
            agent_name (str): Specific agent name or None for all
            
        Returns:
            dict: Metrics for specified agent or all agents
        """
        if agent_name:
            return self.metrics.get(agent_name, {})
        return self.metrics
    
    def get_agent_performance(self, agent_name):
        """Get performance summary for an agent
        
        Returns:
            dict: Performance metrics with efficiency score
        """
        if agent_name not in self.metrics:
            return None
        
        m = self.metrics[agent_name]
        efficiency_score = (m['success_rate'] * 0.7 + (1 - min(m['avg_time'] / 10, 1)) * 0.3) * 100
        
        return {
            'agent': agent_name,
            'total_runs': m['total_runs'],
            'success_rate': round(m['success_rate'] * 100, 2),
            'avg_execution_time': round(m['avg_time'], 3),
            'total_findings': m['total_findings'],
            'efficiency_score': round(efficiency_score, 2),
            'last_run': m['last_run']
        }
    
    def export_metrics(self, filepath=None):
        """Export metrics to JSON file
        
        Args:
            filepath (str): Path to save metrics
            
        Returns:
            str: JSON string of metrics
        """
        metrics_json = json.dumps(self.metrics, indent=2, default=str)
        
        if filepath:
            with open(filepath, 'w') as f:
                f.write(metrics_json)
        
        return metrics_json

# Global instance
telemetry_collector = AgentTelemetryCollector()
