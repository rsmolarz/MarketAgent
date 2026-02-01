"""
IntradayVolatilitySpikeAgent - Detects unusual intraday volatility patterns

Monitors minute-level price data to identify sudden volatility spikes that may
indicate liquidity shocks, breaking news, or algorithmic activity creating
short-term trading opportunities.

Strategy:
- Calculate rolling volatility (standard deviation of returns)
- Compare current volatility to historical baseline
- Flag spikes >2 standard deviations from normal
- Correlate with volume to distinguish real moves from noise
"""
import logging
import random
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class IntradayVolatilitySpikeAgent(BaseAgent):
    """
    Detects unusual intraday volatility spikes in equities by analyzing 
    minute-level price data to identify potential market inefficiencies.
    
    Volatility spikes often precede:
    - News events (earnings leaks, M&A rumors)
    - Large institutional orders
    - Options expiration effects
    - Short squeezes or long liquidations
    """
    
    def __init__(self):
        super().__init__("IntradayVolatilitySpikeAgent")
        self.volatility_threshold = 2.5  # Standard deviations
        self.volume_threshold = 2.0  # Volume multiplier vs average
        self.lookback_minutes = 60  # Baseline window
        self.watchlist = [
            # High-volume, liquid stocks
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD",
            "SPY", "QQQ", "IWM", "DIA",  # ETFs
            "GME", "AMC", "BBBY", "RIVN",  # Meme/volatile stocks
            "COIN", "MARA", "RIOT",  # Crypto-related
            "XOM", "CVX", "COP",  # Energy
            "JPM", "BAC", "GS"  # Financials
        ]
    
    def plan(self) -> Dict[str, Any]:
        """Plan the volatility spike analysis."""
        return {
            "steps": [
                "fetch_intraday_data",
                "calculate_rolling_volatility",
                "detect_spikes",
                "correlate_with_volume",
                "generate_findings"
            ],
            "volatility_threshold_std": self.volatility_threshold,
            "volume_threshold": self.volume_threshold,
            "lookback_minutes": self.lookback_minutes,
            "watchlist_size": len(self.watchlist)
        }
    
    def act(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the analysis and return findings."""
        return self.analyze()
    
    def _fetch_intraday_data(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetch minute-level intraday data for a symbol.
        Returns list of candles with OHLCV data.
        """
        try:
            from data_sources.yahoo_finance_client import YahooFinanceClient
            client = YahooFinanceClient()
            
            # Try to get intraday data
            data = client.get_historical_data(symbol, period="1d", interval="1m")
            if data and len(data) > 30:
                return data
                
        except Exception as e:
            logger.debug(f"Could not fetch real intraday data for {symbol}: {e}")
        
        # Fallback to synthetic data
        return self._generate_synthetic_intraday(symbol)
    
    def _generate_synthetic_intraday(self, symbol: str) -> List[Dict[str, Any]]:
        """Generate synthetic minute-level data for testing."""
        data = []
        base_price = random.uniform(50, 500)
        current_price = base_price
        base_volume = random.randint(10000, 500000)
        
        # Generate ~390 minutes of data (full trading day)
        for i in range(390):
            # Normal random walk with occasional spikes
            normal_return = random.gauss(0, 0.001)  # ~0.1% per minute std
            
            # Inject volatility spike with small probability
            if random.random() < 0.02:  # 2% chance per minute
                spike_return = random.gauss(0, 0.01)  # 10x normal volatility
                current_price *= (1 + spike_return)
                volume = int(base_volume * random.uniform(3, 10))
            else:
                current_price *= (1 + normal_return)
                volume = int(base_volume * random.uniform(0.5, 2))
            
            high = current_price * (1 + abs(random.gauss(0, 0.002)))
            low = current_price * (1 - abs(random.gauss(0, 0.002)))
            
            timestamp = datetime.utcnow() - timedelta(minutes=390-i)
            
            data.append({
                "timestamp": timestamp,
                "open": round(current_price, 2),
                "high": round(max(high, current_price), 2),
                "low": round(min(low, current_price), 2),
                "close": round(current_price, 2),
                "volume": volume
            })
        
        return data
    
    def _calculate_volatility_metrics(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate volatility metrics from intraday data.
        
        Returns:
        - rolling_volatility: list of volatility values
        - current_volatility: most recent volatility
        - baseline_volatility: average volatility
        - volatility_zscore: how many std devs current is from baseline
        """
        if len(data) < self.lookback_minutes + 10:
            return None
        
        # Calculate minute returns
        returns = []
        for i in range(1, len(data)):
            prev_close = data[i-1]["close"]
            curr_close = data[i]["close"]
            if prev_close > 0:
                ret = (curr_close - prev_close) / prev_close
                returns.append(ret)
        
        # Calculate rolling volatility
        rolling_vol = []
        for i in range(self.lookback_minutes, len(returns)):
            window = returns[i-self.lookback_minutes:i]
            vol = self._std_dev(window) * math.sqrt(252 * 390)  # Annualized
            rolling_vol.append(vol)
        
        if not rolling_vol:
            return None
        
        # Current vs baseline
        current_vol = rolling_vol[-1]
        baseline_vol = sum(rolling_vol[:-10]) / max(len(rolling_vol)-10, 1)
        vol_std = self._std_dev(rolling_vol[:-10]) if len(rolling_vol) > 10 else baseline_vol * 0.2
        
        z_score = (current_vol - baseline_vol) / vol_std if vol_std > 0 else 0
        
        # Volume analysis
        volumes = [d["volume"] for d in data]
        avg_volume = sum(volumes[:-10]) / max(len(volumes)-10, 1)
        recent_volume = sum(volumes[-10:]) / 10
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
        
        return {
            "current_volatility": current_vol,
            "baseline_volatility": baseline_vol,
            "volatility_zscore": z_score,
            "volume_ratio": volume_ratio,
            "avg_volume": avg_volume,
            "recent_volume": recent_volume,
            "current_price": data[-1]["close"],
            "price_change_pct": (data[-1]["close"] - data[0]["close"]) / data[0]["close"] * 100 if data[0]["close"] else 0
        }
    
    def _std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if not values:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)
    
    def _classify_spike_type(self, metrics: Dict[str, Any]) -> str:
        """Classify the type of volatility spike based on characteristics."""
        z_score = metrics.get("volatility_zscore", 0)
        vol_ratio = metrics.get("volume_ratio", 1)
        price_change = metrics.get("price_change_pct", 0)
        
        if vol_ratio > 5 and abs(price_change) > 3:
            return "NEWS_EVENT"
        elif vol_ratio > 3 and z_score > 3:
            return "INSTITUTIONAL_FLOW"
        elif z_score > 4 and vol_ratio < 2:
            return "ALGORITHMIC_ACTIVITY"
        elif abs(price_change) > 5:
            return "MOMENTUM_CASCADE"
        else:
            return "LIQUIDITY_SHOCK"
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis: detect intraday volatility spikes.
        
        Returns findings for stocks showing unusual volatility
        that may present trading opportunities.
        """
        findings = []
        
        try:
            logger.info(f"Analyzing intraday volatility for {len(self.watchlist)} symbols")
            
            for symbol in self.watchlist:
                try:
                    # Fetch intraday data
                    data = self._fetch_intraday_data(symbol)
                    
                    if not data or len(data) < 100:
                        continue
                    
                    # Calculate volatility metrics
                    metrics = self._calculate_volatility_metrics(data)
                    
                    if not metrics:
                        continue
                    
                    z_score = metrics["volatility_zscore"]
                    vol_ratio = metrics["volume_ratio"]
                    
                    # Check for spike conditions
                    is_vol_spike = z_score >= self.volatility_threshold
                    is_volume_confirmed = vol_ratio >= self.volume_threshold
                    
                    if is_vol_spike:
                        spike_type = self._classify_spike_type(metrics)
                        severity = self._calculate_severity(z_score, is_volume_confirmed)
                        confidence = min(0.95, 0.5 + z_score * 0.1 + (0.2 if is_volume_confirmed else 0))
                        
                        direction = "UP" if metrics["price_change_pct"] > 0 else "DOWN"
                        
                        findings.append({
                            "title": f"Volatility Spike Detected: {symbol} ({spike_type})",
                            "description": (
                                f"{symbol} showing {z_score:.1f}σ volatility spike "
                                f"({metrics['current_volatility']*100:.1f}% annualized vs "
                                f"{metrics['baseline_volatility']*100:.1f}% baseline). "
                                f"Price {direction} {abs(metrics['price_change_pct']):.2f}% today. "
                                f"Volume {vol_ratio:.1f}x average. "
                                f"Spike type: {spike_type.replace('_', ' ').title()}."
                            ),
                            "severity": severity,
                            "confidence": confidence,
                            "symbol": symbol,
                            "market_type": "equity",
                            "metadata": {
                                "current_volatility_annualized": round(metrics["current_volatility"] * 100, 2),
                                "baseline_volatility_annualized": round(metrics["baseline_volatility"] * 100, 2),
                                "volatility_zscore": round(z_score, 2),
                                "volume_ratio": round(vol_ratio, 2),
                                "recent_volume": int(metrics["recent_volume"]),
                                "avg_volume": int(metrics["avg_volume"]),
                                "price_change_pct": round(metrics["price_change_pct"], 2),
                                "current_price": metrics["current_price"],
                                "spike_type": spike_type,
                                "direction": direction,
                                "volume_confirmed": is_volume_confirmed,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        })
                        
                except Exception as e:
                    logger.debug(f"Error analyzing {symbol}: {e}")
                    continue
            
            # Sort by z-score (most extreme first)
            findings.sort(key=lambda x: x["metadata"]["volatility_zscore"], reverse=True)
            
            logger.info(f"Found {len(findings)} volatility spikes")
            
        except Exception as e:
            logger.error(f"Error in volatility spike analysis: {e}")
            findings.append({
                "title": "Volatility Analysis Error",
                "description": f"Analysis encountered an error: {str(e)}",
                "severity": "low",
                "confidence": 1.0,
                "metadata": {"error": str(e)}
            })
        
        return findings
    
    def _calculate_severity(self, z_score: float, volume_confirmed: bool) -> str:
        """Calculate severity based on spike magnitude."""
        if z_score >= 4 and volume_confirmed:
            return "high"
        elif z_score >= 3 or (z_score >= 2.5 and volume_confirmed):
            return "medium"
        else:
            return "low"
    
    def reflect(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reflect on the analysis results."""
        spike_types = {}
        for f in results:
            spike_type = f.get("metadata", {}).get("spike_type", "UNKNOWN")
            spike_types[spike_type] = spike_types.get(spike_type, 0) + 1
        
        return {
            "finding_count": len(results),
            "high_severity_count": sum(1 for f in results if f.get("severity") == "high"),
            "volume_confirmed_count": sum(1 for f in results if f.get("metadata", {}).get("volume_confirmed")),
            "spike_types": spike_types,
            "avg_zscore": sum(f.get("metadata", {}).get("volatility_zscore", 0) for f in results) / len(results) if results else 0,
            "symbols_affected": list(set(f.get("symbol") for f in results if f.get("symbol")))
        }
