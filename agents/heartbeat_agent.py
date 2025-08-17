import logging
from datetime import datetime
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class HeartbeatAgent(BaseAgent):
    """
    Heartbeat agent that generates periodic findings to ensure the pipeline is working
    """

    def __init__(self):
        super().__init__()
        self.name = "HeartbeatAgent"

    def _plan(self):
        """Plan heartbeat check"""
        return ["Generate heartbeat finding to verify system is operational"]

    def _act(self, plan):
        """Generate a heartbeat finding"""
        try:
            current_time = datetime.utcnow()
            
            finding = {
                'title': 'System Heartbeat',
                'description': f'Market monitoring system operational at {current_time.strftime("%Y-%m-%d %H:%M:%S")} UTC. All agents responding.',
                'severity': 'low',
                'confidence': 1.0,
                'symbol': 'SYSTEM',
                'market_type': 'system',
                'metadata': {
                    'type': 'heartbeat',
                    'timestamp': current_time.isoformat(),
                    'status': 'operational'
                }
            }
            
            return [finding]
            
        except Exception as e:
            logger.error(f"HeartbeatAgent error: {e}")
            return []

    def _reflect(self, results):
        """Reflect on heartbeat results"""
        if results:
            logger.info(f"HeartbeatAgent: Generated heartbeat signal - system operational")
        else:
            logger.warning(f"HeartbeatAgent: Failed to generate heartbeat signal")
        return results

    def analyze(self):
        """Required abstract method implementation for BaseAgent"""
        plan = self._plan()
        results = self._act(plan)
        return self._reflect(results)