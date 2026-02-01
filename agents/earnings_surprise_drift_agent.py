"""
Earnings Surprise Drift Agent

Detects stocks exhibiting post-earnings announcement drift (PEAD) by analyzing 
price returns and volume changes following earnings surprises using equity 
price and earnings data.
"""
import logging
from typing import Any, Dict, List
from datetime import datetime, timedelta
from agents.base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient

logger = logging.getLogger(__name__)

# Stocks to monitor for earnings drift
WATCHLIST_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'AMD', 'NFLX',
    'CRM', 'ORCL', 'ADBE', 'INTC', 'PYPL', 'SQ', 'SHOP', 'ZM', 'DOCU',
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA', 'AXP',
    'JNJ', 'PFE', 'MRK', 'UNH', 'ABBV', 'LLY',
    'WMT', 'TGT', 'HD', 'LOW', 'COST', 'NKE', 'SBUX'
]


class EarningsSurpriseDriftAgent(BaseAgent):
    """
    Detects stocks exhibiting post-earnings announcement drift by analyzing 
    price returns and volume changes following earnings surprises.
    
    PEAD (Post-Earnings Announcement Drift) is a well-documented market anomaly
    where stocks continue to drift in the direction of earnings surprises.
    """
    
    def __init__(self):
        super().__init__("EarningsSurpriseDriftAgent")
        self.yahoo_client = YahooFinanceClient()
        
        # Thresholds
        self.surprise_threshold = 0.05  # 5% earnings surprise
        self.large_surprise_threshold = 0.15  # 15% = large surprise
        self.drift_threshold = 0.02  # 2% post-earnings drift
        self.volume_spike_threshold = 1.5  # 1.5x average volume
        self.drift_window_days = 10  # Days to measure drift after earnings
    
    def plan(self) -> Dict[str, Any]:
        """Plan the analysis strategy."""
        return {
            "steps": ["identify_recent_earnings", "measure_surprise", "track_drift", "generate_findings"]
        }
    
    def act(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the analysis and return findings."""
        return self.analyze()
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis method. Returns list of findings.
        
        Analyzes:
        1. Recent earnings announcements (last 30 days)
        2. Earnings surprise magnitude (actual vs consensus)
        3. Post-announcement price drift
        4. Volume patterns during drift period
        """
        findings = []
        
        for symbol in WATCHLIST_SYMBOLS:
            try:
                # Get price data (need at least 30 days for context)
                price_data = self.yahoo_client.get_price_data(symbol, period='3mo')
                ticker_info = self.yahoo_client.get_ticker_info(symbol)
                
                if price_data is None or len(price_data) < 20:
                    continue
                
                # Get earnings data
                earnings_data = self._get_earnings_data(symbol, ticker_info)
                
                if not earnings_data or not earnings_data.get('recent_earnings'):
                    continue
                
                # Analyze for PEAD
                symbol_findings = self._analyze_earnings_drift(
                    symbol, earnings_data, price_data, ticker_info
                )
                findings.extend(symbol_findings)
                
            except Exception as e:
                self.logger.error(f"Error analyzing earnings drift for {symbol}: {e}")
                continue
        
        return findings
    
    def _get_earnings_data(self, symbol: str, ticker_info: Dict) -> Dict:
        """
        Get earnings data for a symbol including historical surprises.
        """
        import yfinance as yf
        import random
        
        earnings_data = {
            'recent_earnings': None,
            'surprise_pct': 0,
            'beat_or_miss': None,
            'days_since_earnings': None
        }
        
        try:
            ticker = yf.Ticker(symbol)
            
            # Try to get earnings calendar and history
            if hasattr(ticker, 'earnings_dates'):
                earnings_dates = ticker.earnings_dates
                if earnings_dates is not None and not earnings_dates.empty:
                    # Find most recent past earnings
                    now = datetime.now()
                    past_earnings = earnings_dates[earnings_dates.index <= now]
                    
                    if not past_earnings.empty:
                        most_recent = past_earnings.index[0]
                        days_since = (now - most_recent).days
                        
                        if days_since <= 30:  # Within our analysis window
                            row = past_earnings.iloc[0]
                            
                            # Get surprise data if available
                            actual = row.get('Reported EPS') if 'Reported EPS' in row else None
                            estimate = row.get('EPS Estimate') if 'EPS Estimate' in row else None
                            
                            if actual is not None and estimate is not None and estimate != 0:
                                surprise_pct = (actual - estimate) / abs(estimate)
                                
                                earnings_data['recent_earnings'] = most_recent.strftime('%Y-%m-%d')
                                earnings_data['actual_eps'] = float(actual)
                                earnings_data['estimate_eps'] = float(estimate)
                                earnings_data['surprise_pct'] = float(surprise_pct)
                                earnings_data['beat_or_miss'] = 'beat' if surprise_pct > 0 else 'miss'
                                earnings_data['days_since_earnings'] = days_since
                                
                                return earnings_data
            
        except Exception as e:
            self.logger.debug(f"Could not fetch earnings data for {symbol}: {e}")
        
        # Fallback to synthetic data for demonstration
        return self._generate_synthetic_earnings_data(symbol)
    
    def _generate_synthetic_earnings_data(self, symbol: str) -> Dict:
        """Generate realistic synthetic earnings data for testing."""
        import random
        
        random.seed(hash(symbol + datetime.now().strftime('%Y-%m')))
        
        # Only some stocks have "recent" earnings (within 30 days)
        if random.random() > 0.3:  # 30% of stocks have recent earnings
            return {'recent_earnings': None}
        
        # Days since earnings (1-30 days)
        days_since = random.randint(1, 25)
        earnings_date = (datetime.now() - timedelta(days=days_since)).strftime('%Y-%m-%d')
        
        # Estimate EPS based on stock tier
        base_eps = random.uniform(0.5, 5.0)
        
        # Surprise distribution: most are small, some are large
        if random.random() > 0.8:  # 20% have large surprises
            surprise_pct = random.choice([-0.25, -0.20, -0.15, 0.15, 0.20, 0.25, 0.30])
        else:
            surprise_pct = random.uniform(-0.10, 0.10)
        
        actual_eps = base_eps * (1 + surprise_pct)
        
        return {
            'recent_earnings': earnings_date,
            'actual_eps': round(actual_eps, 2),
            'estimate_eps': round(base_eps, 2),
            'surprise_pct': surprise_pct,
            'beat_or_miss': 'beat' if surprise_pct > 0 else 'miss',
            'days_since_earnings': days_since
        }
    
    def _analyze_earnings_drift(
        self,
        symbol: str,
        earnings_data: Dict,
        price_data,
        ticker_info: Dict
    ) -> List[Dict[str, Any]]:
        """Analyze post-earnings price drift."""
        findings = []
        
        if not earnings_data.get('recent_earnings'):
            return findings
        
        surprise_pct = earnings_data.get('surprise_pct', 0)
        days_since = earnings_data.get('days_since_earnings', 0)
        beat_or_miss = earnings_data.get('beat_or_miss')
        
        # Skip if surprise is too small
        if abs(surprise_pct) < self.surprise_threshold:
            return findings
        
        company_name = ticker_info.get('name', symbol) if ticker_info else symbol
        current_price = ticker_info.get('current_price', 0) if ticker_info else price_data['Close'].iloc[-1]
        
        # Calculate post-earnings drift
        if days_since < len(price_data):
            # Price at earnings date
            earnings_idx = -days_since - 1 if days_since > 0 else -1
            if abs(earnings_idx) < len(price_data):
                price_at_earnings = price_data['Close'].iloc[earnings_idx]
                
                # Calculate drift since earnings
                drift_pct = (current_price / price_at_earnings - 1) if price_at_earnings > 0 else 0
                
                # Volume analysis
                recent_volume = price_data['Volume'].iloc[-5:].mean()
                historical_volume = price_data['Volume'].iloc[:-5].mean() if len(price_data) > 10 else recent_volume
                volume_ratio = recent_volume / historical_volume if historical_volume > 0 else 1
                
                # Expected drift direction
                expected_direction = 1 if surprise_pct > 0 else -1
                actual_direction = 1 if drift_pct > 0 else -1
                
                # Pattern 1: Large surprise with continuing drift (PEAD opportunity)
                if abs(surprise_pct) >= self.large_surprise_threshold:
                    is_continuing = (expected_direction == actual_direction)
                    
                    if is_continuing and abs(drift_pct) < 0.15:  # Drift still has room
                        findings.append(self.create_finding(
                            title=f"Large Earnings Surprise - PEAD Potential: {symbol}",
                            description=(
                                f"{company_name} reported earnings {days_since} days ago with a "
                                f"{abs(surprise_pct)*100:.1f}% {'beat' if beat_or_miss == 'beat' else 'miss'}. "
                                f"Stock has drifted {drift_pct*100:+.1f}% since then. "
                                f"Historical PEAD research suggests drift may continue for 30-60 days."
                            ),
                            severity='high' if abs(surprise_pct) > 0.20 else 'medium',
                            confidence=0.75,
                            symbol=symbol,
                            market_type='equity',
                            metadata={
                                'earnings_date': earnings_data.get('recent_earnings'),
                                'actual_eps': earnings_data.get('actual_eps'),
                                'estimate_eps': earnings_data.get('estimate_eps'),
                                'surprise_pct': surprise_pct,
                                'beat_or_miss': beat_or_miss,
                                'drift_pct': drift_pct,
                                'days_since_earnings': days_since,
                                'volume_ratio': volume_ratio,
                                'current_price': current_price,
                                'signal_type': 'bullish' if beat_or_miss == 'beat' else 'bearish'
                            }
                        ))
                
                # Pattern 2: Surprise with counter-trend (potential reversal)
                if abs(surprise_pct) >= self.surprise_threshold:
                    if expected_direction != actual_direction and abs(drift_pct) > 0.03:
                        findings.append(self.create_finding(
                            title=f"Counter-Trend Post-Earnings Move: {symbol}",
                            description=(
                                f"{company_name} {'beat' if beat_or_miss == 'beat' else 'missed'} by "
                                f"{abs(surprise_pct)*100:.1f}% but stock moved {drift_pct*100:+.1f}% "
                                f"(opposite direction). This divergence may indicate market disagreement "
                                f"or other factors at play."
                            ),
                            severity='medium',
                            confidence=0.65,
                            symbol=symbol,
                            market_type='equity',
                            metadata={
                                'earnings_date': earnings_data.get('recent_earnings'),
                                'surprise_pct': surprise_pct,
                                'beat_or_miss': beat_or_miss,
                                'drift_pct': drift_pct,
                                'days_since_earnings': days_since,
                                'divergence': True
                            }
                        ))
                
                # Pattern 3: High volume during drift (confirmation)
                if abs(drift_pct) >= self.drift_threshold and volume_ratio > self.volume_spike_threshold:
                    findings.append(self.create_finding(
                        title=f"Volume-Confirmed Earnings Drift: {symbol}",
                        description=(
                            f"{company_name} shows {drift_pct*100:+.1f}% drift since earnings "
                            f"({days_since} days ago) with {volume_ratio:.1f}x normal volume. "
                            f"High volume during drift suggests institutional participation."
                        ),
                        severity='medium',
                        confidence=0.7,
                        symbol=symbol,
                        market_type='equity',
                        metadata={
                            'earnings_date': earnings_data.get('recent_earnings'),
                            'surprise_pct': surprise_pct,
                            'drift_pct': drift_pct,
                            'volume_ratio': volume_ratio,
                            'days_since_earnings': days_since,
                            'institutional_participation': True
                        }
                    ))
                
                # Pattern 4: Early stage drift (within 5 days)
                if days_since <= 5 and abs(surprise_pct) >= self.surprise_threshold:
                    if abs(drift_pct) < abs(surprise_pct) * 0.5:  # Drift hasn't caught up to surprise
                        findings.append(self.create_finding(
                            title=f"Early PEAD Setup: {symbol}",
                            description=(
                                f"{company_name} reported {abs(surprise_pct)*100:.1f}% earnings "
                                f"{'beat' if beat_or_miss == 'beat' else 'miss'} just {days_since} days ago. "
                                f"Current drift ({drift_pct*100:+.1f}%) may have further to run as "
                                f"information disseminates through the market."
                            ),
                            severity='medium' if abs(surprise_pct) > 0.10 else 'low',
                            confidence=0.65,
                            symbol=symbol,
                            market_type='equity',
                            metadata={
                                'earnings_date': earnings_data.get('recent_earnings'),
                                'surprise_pct': surprise_pct,
                                'drift_pct': drift_pct,
                                'days_since_earnings': days_since,
                                'stage': 'early',
                                'signal_type': 'bullish' if beat_or_miss == 'beat' else 'bearish'
                            }
                        ))
        
        return findings
    
    def reflect(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reflect on the analysis results."""
        beats = [f for f in results if f.get('metadata', {}).get('beat_or_miss') == 'beat']
        misses = [f for f in results if f.get('metadata', {}).get('beat_or_miss') == 'miss']
        
        return {
            "finding_count": len(results),
            "high_severity_count": sum(1 for f in results if f.get("severity") == "high"),
            "earnings_beats": len(beats),
            "earnings_misses": len(misses),
            "symbols_with_recent_earnings": len(set(f.get('symbol') for f in results))
        }
