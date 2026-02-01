"""
Intraday Volume Spike Agent

Detects unusual intraday volume spikes in equities by comparing recent volume 
against historical intraday averages to identify potential market inefficiencies 
due to sudden liquidity surges.
"""
import logging
from typing import Any, Dict, List
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient

logger = logging.getLogger(__name__)

# Stocks to monitor for volume spikes
WATCHLIST_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'AMD', 'SPY', 'QQQ',
    'NFLX', 'DIS', 'BA', 'NKE', 'COIN', 'PLTR', 'RIVN', 'UBER', 'LYFT', 'SNAP',
    'JPM', 'BAC', 'GS', 'C', 'WFC',
    'XOM', 'CVX', 'OXY', 'SLB',
    'PFE', 'MRNA', 'JNJ', 'ABBV'
]


class IntradayVolumeSpikeAgent(BaseAgent):
    """
    Detects unusual intraday volume spikes in equities by comparing recent 
    volume against historical averages to identify potential market 
    inefficiencies due to sudden liquidity surges.
    """
    
    def __init__(self):
        super().__init__("IntradayVolumeSpikeAgent")
        self.yahoo_client = YahooFinanceClient()
        
        # Thresholds
        self.moderate_spike_threshold = 2.0  # 2x average = notable
        self.high_spike_threshold = 3.0  # 3x average = significant
        self.extreme_spike_threshold = 5.0  # 5x average = extreme
        self.price_correlation_threshold = 0.01  # 1% price move
        self.relative_volume_lookback = 20  # 20-day volume average
    
    def plan(self) -> Dict[str, Any]:
        """Plan the analysis strategy."""
        return {
            "steps": ["fetch_volume_data", "calculate_relative_volume", "detect_spikes", "correlate_price", "generate_findings"]
        }
    
    def act(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the analysis and return findings."""
        return self.analyze()
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis method. Returns list of findings.
        
        Analyzes:
        1. Current day's volume vs 20-day average
        2. Volume acceleration (is it picking up?)
        3. Correlation with price movement
        4. Time-of-day patterns
        """
        findings = []
        
        for symbol in WATCHLIST_SYMBOLS:
            try:
                # Get price data with volume (need daily data for 20-day average)
                price_data = self.yahoo_client.get_price_data(symbol, period='1mo')
                ticker_info = self.yahoo_client.get_ticker_info(symbol)
                
                if price_data is None or len(price_data) < 10:
                    continue
                
                # Analyze volume patterns
                symbol_findings = self._analyze_volume_patterns(
                    symbol, price_data, ticker_info
                )
                findings.extend(symbol_findings)
                
            except Exception as e:
                self.logger.error(f"Error analyzing volume for {symbol}: {e}")
                continue
        
        return findings
    
    def _analyze_volume_patterns(
        self,
        symbol: str,
        price_data,
        ticker_info: Dict
    ) -> List[Dict[str, Any]]:
        """Analyze volume patterns for unusual spikes."""
        findings = []
        
        if len(price_data) < 5:
            return findings
        
        # Calculate volume metrics
        current_volume = price_data['Volume'].iloc[-1]
        avg_volume_20d = price_data['Volume'].iloc[:-1].mean() if len(price_data) > 1 else current_volume
        
        # Relative volume (RVOL)
        rvol = current_volume / avg_volume_20d if avg_volume_20d > 0 else 1
        
        # Volume trend (is it accelerating?)
        if len(price_data) >= 5:
            vol_3day = price_data['Volume'].iloc[-3:].mean()
            vol_prior = price_data['Volume'].iloc[-8:-3].mean() if len(price_data) >= 8 else vol_3day
            volume_acceleration = vol_3day / vol_prior if vol_prior > 0 else 1
        else:
            volume_acceleration = 1
        
        # Price metrics
        current_price = price_data['Close'].iloc[-1]
        prev_close = price_data['Close'].iloc[-2] if len(price_data) > 1 else current_price
        price_change_pct = (current_price / prev_close - 1) if prev_close > 0 else 0
        
        # Intraday range (High-Low)
        if 'High' in price_data.columns and 'Low' in price_data.columns:
            today_high = price_data['High'].iloc[-1]
            today_low = price_data['Low'].iloc[-1]
            intraday_range = (today_high - today_low) / today_low if today_low > 0 else 0
            avg_range = ((price_data['High'] - price_data['Low']) / price_data['Low']).mean()
            range_ratio = intraday_range / avg_range if avg_range > 0 else 1
        else:
            intraday_range = 0
            range_ratio = 1
        
        company_name = ticker_info.get('name', symbol) if ticker_info else symbol
        market_cap = ticker_info.get('market_cap') if ticker_info else None
        
        # Determine stock category for context
        if market_cap:
            if market_cap > 200e9:
                cap_category = "mega-cap"
            elif market_cap > 10e9:
                cap_category = "large-cap"
            elif market_cap > 2e9:
                cap_category = "mid-cap"
            else:
                cap_category = "small-cap"
        else:
            cap_category = "unknown"
        
        # Pattern 1: Extreme volume spike
        if rvol >= self.extreme_spike_threshold:
            # Determine likely cause based on correlations
            if abs(price_change_pct) > 0.05:
                likely_cause = "significant news or earnings"
            elif range_ratio > 2:
                likely_cause = "high volatility / potential breakout"
            else:
                likely_cause = "block trades or institutional activity"
            
            findings.append(self.create_finding(
                title=f"Extreme Volume Spike: {symbol}",
                description=(
                    f"{company_name} ({cap_category}) trading at {rvol:.1f}x its 20-day average volume. "
                    f"Current volume: {current_volume:,.0f} vs avg {avg_volume_20d:,.0f}. "
                    f"Price change: {price_change_pct*100:+.2f}%. "
                    f"Likely cause: {likely_cause}."
                ),
                severity='high',
                confidence=0.85,
                symbol=symbol,
                market_type='equity',
                metadata={
                    'relative_volume': rvol,
                    'current_volume': int(current_volume),
                    'avg_volume_20d': int(avg_volume_20d),
                    'price_change_pct': price_change_pct,
                    'intraday_range_pct': intraday_range,
                    'range_ratio': range_ratio,
                    'volume_acceleration': volume_acceleration,
                    'current_price': current_price,
                    'cap_category': cap_category,
                    'likely_cause': likely_cause
                }
            ))
        
        # Pattern 2: High volume spike with price correlation
        elif rvol >= self.high_spike_threshold:
            price_correlated = abs(price_change_pct) > self.price_correlation_threshold
            
            findings.append(self.create_finding(
                title=f"High Volume Spike: {symbol}",
                description=(
                    f"{company_name} trading at {rvol:.1f}x average volume. "
                    f"Volume: {current_volume:,.0f}. Price: {price_change_pct*100:+.2f}%. "
                    f"{'Price movement correlated with volume surge.' if price_correlated else 'Volume surge without major price move - possible accumulation/distribution.'}"
                ),
                severity='medium',
                confidence=0.75,
                symbol=symbol,
                market_type='equity',
                metadata={
                    'relative_volume': rvol,
                    'current_volume': int(current_volume),
                    'avg_volume_20d': int(avg_volume_20d),
                    'price_change_pct': price_change_pct,
                    'price_correlated': price_correlated,
                    'current_price': current_price
                }
            ))
        
        # Pattern 3: Moderate spike but with acceleration
        elif rvol >= self.moderate_spike_threshold and volume_acceleration > 1.5:
            findings.append(self.create_finding(
                title=f"Accelerating Volume: {symbol}",
                description=(
                    f"{company_name} volume is accelerating. "
                    f"Current RVOL: {rvol:.1f}x with {volume_acceleration:.1f}x volume growth over 3 days. "
                    f"Price: {price_change_pct*100:+.2f}%. "
                    f"Accelerating volume often precedes significant moves."
                ),
                severity='low',
                confidence=0.65,
                symbol=symbol,
                market_type='equity',
                metadata={
                    'relative_volume': rvol,
                    'volume_acceleration': volume_acceleration,
                    'price_change_pct': price_change_pct,
                    'current_price': current_price
                }
            ))
        
        # Pattern 4: Volume divergence (price flat but volume high)
        if rvol >= self.moderate_spike_threshold and abs(price_change_pct) < 0.005:
            findings.append(self.create_finding(
                title=f"Volume-Price Divergence: {symbol}",
                description=(
                    f"{company_name} showing {rvol:.1f}x normal volume but minimal price movement "
                    f"({price_change_pct*100:+.2f}%). This pattern may indicate "
                    f"quiet accumulation/distribution before a larger move."
                ),
                severity='low',
                confidence=0.6,
                symbol=symbol,
                market_type='equity',
                metadata={
                    'relative_volume': rvol,
                    'price_change_pct': price_change_pct,
                    'divergence_type': 'volume_without_price',
                    'current_price': current_price,
                    'signal_type': 'neutral'
                }
            ))
        
        # Pattern 5: Breakout volume (high volume + expanded range + directional move)
        if rvol >= self.high_spike_threshold and range_ratio > 1.5 and abs(price_change_pct) > 0.02:
            direction = "bullish breakout" if price_change_pct > 0 else "bearish breakdown"
            
            findings.append(self.create_finding(
                title=f"Volume Breakout Pattern: {symbol}",
                description=(
                    f"{company_name} showing potential {direction}. "
                    f"RVOL: {rvol:.1f}x, Range: {range_ratio:.1f}x normal, "
                    f"Price: {price_change_pct*100:+.2f}%. "
                    f"High volume breakouts with expanded range have higher probability of follow-through."
                ),
                severity='medium',
                confidence=0.7,
                symbol=symbol,
                market_type='equity',
                metadata={
                    'relative_volume': rvol,
                    'range_ratio': range_ratio,
                    'price_change_pct': price_change_pct,
                    'breakout_direction': direction,
                    'current_price': current_price,
                    'signal_type': 'bullish' if price_change_pct > 0 else 'bearish'
                }
            ))
        
        return findings
    
    def reflect(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reflect on the analysis results."""
        extreme_spikes = [f for f in results if f.get('metadata', {}).get('relative_volume', 0) >= 5]
        breakouts = [f for f in results if 'breakout' in f.get('title', '').lower()]
        
        return {
            "finding_count": len(results),
            "high_severity_count": sum(1 for f in results if f.get("severity") == "high"),
            "extreme_volume_spikes": len(extreme_spikes),
            "breakout_patterns": len(breakouts),
            "symbols_analyzed": len(WATCHLIST_SYMBOLS)
        }
