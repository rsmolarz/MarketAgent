"""
Base Agent Class

All market inefficiency detection agents inherit from this base class.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import Config
from telemetry.instrumentation import instrument_agent_call

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    Base class for all market inefficiency detection agents
    """
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.config = Config.get_agent_config(self.name)
        self.logger = logging.getLogger(f"agent.{self.name}")
        
    @abstractmethod
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Perform the main analysis and return findings
        
        Returns:
            List of finding dictionaries with keys:
            - title: str
            - description: str  
            - severity: str ('low', 'medium', 'high', 'critical')
            - confidence: float (0.0 - 1.0)
            - metadata: dict (additional data)
            - symbol: str (optional)
            - market_type: str (optional)
        """
        pass
    
    def run(self) -> List[Dict[str, Any]]:
        """
        Canonical execution entrypoint for telemetry.
        Routes through instrumentation for latency, error, and reward logging.
        
        Returns:
            List of findings or empty list if error
        """
        def _execute():
            self.logger.info(f"Starting {self.name} analysis")
            findings = self.analyze()
            
            if findings:
                self.logger.info(f"{self.name} found {len(findings)} anomalies")
                for finding in findings:
                    self.logger.info(f"Finding: {finding.get('title', 'Unknown')} "
                                   f"(severity: {finding.get('severity', 'unknown')})")
            else:
                self.logger.info(f"{self.name} found no anomalies")
                
            return findings or []
        
        try:
            return instrument_agent_call(
                agent_name=self.name,
                fn=_execute
            )
        except Exception as e:
            self.logger.error(f"Error in {self.name}: {e}", exc_info=True)
            return []
    
    def create_finding(self, 
                      title: str,
                      description: str,
                      severity: str = 'medium',
                      confidence: float = 0.5,
                      metadata: Dict[str, Any] = None,
                      symbol: str = None,
                      market_type: str = None) -> Dict[str, Any]:
        """
        Create a standardized finding dictionary
        
        Args:
            title: Short title of the finding
            description: Detailed description
            severity: 'low', 'medium', 'high', or 'critical'
            confidence: Confidence level (0.0 - 1.0)
            metadata: Additional data
            symbol: Related symbol/ticker
            market_type: Type of market (crypto, equity, forex, etc.)
            
        Returns:
            Finding dictionary
        """
        return {
            'title': title,
            'description': description,
            'severity': severity,
            'confidence': confidence,
            'metadata': metadata or {},
            'symbol': symbol,
            'market_type': market_type,
            'timestamp': datetime.utcnow().isoformat(),
            'agent': self.name
        }
    
    def validate_config(self, required_keys: List[str]) -> bool:
        """
        Validate that required configuration keys are present
        
        Args:
            required_keys: List of required config keys
            
        Returns:
            True if all keys present, False otherwise
        """
        for key in required_keys:
            if not getattr(Config, key, None):
                self.logger.warning(f"Missing required config: {key}")
                return False
        return True
    
    def log_metric(self, metric_name: str, value: float, metadata: Dict = None):
        """
        Log a metric for monitoring purposes
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            metadata: Additional metadata
        """
        self.logger.info(f"METRIC: {metric_name}={value}", extra={
            'metric_name': metric_name,
            'metric_value': value,
            'metadata': metadata or {},
            'agent': self.name
        })
