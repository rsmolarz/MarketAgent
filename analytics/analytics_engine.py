"""
Advanced Analytics Engine
Provides trend analysis, anomaly detection, forecasting, and insights
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import statistics


class AnalyticsEngine:
    """Comprehensive analytics for system monitoring and optimization"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnalyticsEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.historical_data = {}
        self._initialized = True
    
    def analyze_trend(self, metric_name: str, values: List[float]) -> Dict:
        """Analyze trend in metric"""
        if len(values) < 2:
            return {'error': 'Insufficient data'}
        
        n = len(values)
        x_values = list(range(n))
        
        # Calculate trend
        mean_x = sum(x_values) / n
        mean_y = sum(values) / n
        
        numerator = sum((x_values[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        denominator = sum((x_values[i] - mean_x) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        intercept = mean_y - slope * mean_x
        
        # Calculate moving average
        ma_5 = self._moving_average(values, 5)
        
        return {
            'metric': metric_name,
            'trend_slope': slope,
            'current_value': values[-1],
            'average': mean_y,
            'trend_direction': 'up' if slope > 0.01 else 'down' if slope < -0.01 else 'stable',
            'moving_average_5': ma_5[-1] if ma_5 else None
        }
    
    def detect_anomalies(self, values: List[float], threshold_sigma: float = 3.0) -> List[Dict]:
        """Detect statistical anomalies"""
        if len(values) < 3:
            return []
        
        mean = statistics.mean(values)
        try:
            stdev = statistics.stdev(values)
        except:
            stdev = 0
        
        if stdev == 0:
            return []
        
        anomalies = []
        for i, val in enumerate(values):
            z_score = abs((val - mean) / stdev)
            if z_score > threshold_sigma:
                anomalies.append({
                    'index': i,
                    'value': val,
                    'z_score': z_score,
                    'severity': 'critical' if z_score > 4 else 'high'
                })
        
        return anomalies
    
    def forecast(self, values: List[float], periods: int = 24) -> List[float]:
        """Simple forecasting using moving average"""
        if len(values) < 5:
            return [values[-1]] * periods
        
        ma = self._moving_average(values, 5)
        if not ma:
            return [values[-1]] * periods
        
        trend = (ma[-1] - ma[-5]) / 5 if len(ma) >= 5 else 0
        forecast = []
        
        for i in range(periods):
            forecast.append(ma[-1] + (trend * (i + 1)))
        
        return forecast
    
    def correlation_analysis(self, metric1: List[float], metric2: List[float]) -> Dict:
        """Analyze correlation between two metrics"""
        if len(metric1) < 2 or len(metric1) != len(metric2):
            return {'error': 'Invalid data'}
        
        n = len(metric1)
        mean1 = statistics.mean(metric1)
        mean2 = statistics.mean(metric2)
        
        try:
            std1 = statistics.stdev(metric1)
            std2 = statistics.stdev(metric2)
        except:
            return {'correlation': 0}
        
        if std1 == 0 or std2 == 0:
            return {'correlation': 0}
        
        covariance = sum((metric1[i] - mean1) * (metric2[i] - mean2) for i in range(n)) / n
        correlation = covariance / (std1 * std2)
        
        return {
            'correlation': round(correlation, 3),
            'strength': self._correlation_strength(correlation),
            'direction': 'positive' if correlation > 0 else 'negative'
        }
    
    def cost_optimization(self, api_costs: Dict[str, float], throughput: Dict[str, int]) -> Dict:
        """Provide cost optimization recommendations"""
        recommendations = []
        
        for api, cost in api_costs.items():
            if api in throughput:
                cost_per_unit = cost / throughput[api] if throughput[api] > 0 else 0
                
                if cost_per_unit > 0.01:  # Expensive
                    recommendations.append({
                        'api': api,
                        'current_cost': cost,
                        'cost_per_unit': cost_per_unit,
                        'recommendation': 'Consider switching to cheaper alternative',
                        'potential_savings': cost * 0.3  # Est. 30% savings
                    })
        
        return {
            'total_current_cost': sum(api_costs.values()),
            'recommendations': recommendations,
            'potential_monthly_savings': sum(r['potential_savings'] for r in recommendations)
        }
    
    def _moving_average(self, values: List[float], window: int) -> List[float]:
        """Calculate moving average"""
        if len(values) < window:
            return []
        
        return [
            statistics.mean(values[i-window+1:i+1])
            for i in range(window-1, len(values))
        ]
    
    def _correlation_strength(self, correlation: float) -> str:
        """Describe correlation strength"""
        abs_corr = abs(correlation)
        if abs_corr > 0.8:
            return 'very strong'
        elif abs_corr > 0.6:
            return 'strong'
        elif abs_corr > 0.4:
            return 'moderate'
        elif abs_corr > 0.2:
            return 'weak'
        else:
            return 'very weak'
    
    def generate_report(self, metric_data: Dict) -> Dict:
        """Generate comprehensive analytics report"""
        return {
            'report_timestamp': datetime.utcnow().isoformat(),
            'metrics_analyzed': len(metric_data),
            'insights': [
                self.analyze_trend(name, values) 
                for name, values in metric_data.items()
            ]
        }


# Global instance
analytics_engine = AnalyticsEngine()
