"""
Sentiment Divergence Agent

Detects divergences between market sentiment and price action,
which can indicate potential market inefficiencies.
"""

import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
from data_sources.github_client import GitHubClient
from config import Config

class SentimentDivergenceAgent(BaseAgent):
    """
    Detects sentiment vs price divergences using multiple data sources
    """
    
    def __init__(self):
        super().__init__()
        self.yahoo_client = YahooFinanceClient()
        self.github_client = GitHubClient()
        
        # Assets to monitor - expanded for more findings
        self.assets = {
            'BTC-USD': {'name': 'Bitcoin', 'type': 'crypto'},
            'ETH-USD': {'name': 'Ethereum', 'type': 'crypto'},
            'SPY': {'name': 'S&P 500', 'type': 'equity'},
            'QQQ': {'name': 'NASDAQ', 'type': 'equity'},
            'TSLA': {'name': 'Tesla', 'type': 'equity'},
            'AAPL': {'name': 'Apple', 'type': 'equity'},
            'MSFT': {'name': 'Microsoft', 'type': 'equity'},
            'GOOGL': {'name': 'Google', 'type': 'equity'},
            'NVDA': {'name': 'NVIDIA', 'type': 'equity'},
            'META': {'name': 'Meta', 'type': 'equity'}
        }
        
        self.divergence_threshold = Config.SENTIMENT_DIVERGENCE_THRESHOLD
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze sentiment vs price divergences
        """
        findings = []
        
        for symbol, asset_info in self.assets.items():
            try:
                # Get price data
                price_data = self.yahoo_client.get_price_data(symbol, period='7d')
                if price_data is None or len(price_data) < 5:
                    continue
                
                # Calculate price momentum
                price_momentum = self._calculate_price_momentum(price_data)
                
                # Get sentiment data
                sentiment_score = self._get_sentiment_score(symbol, asset_info)
                
                if sentiment_score is not None:
                    # Check for divergence
                    divergence = self._check_divergence(
                        symbol, asset_info, price_momentum, sentiment_score
                    )
                    if divergence:
                        findings.append(divergence)
                        
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")
                
        return findings
    
    def _calculate_price_momentum(self, price_data) -> float:
        """Calculate price momentum over the period"""
        try:
            start_price = price_data['Close'].iloc[0]
            end_price = price_data['Close'].iloc[-1]
            momentum = (end_price - start_price) / start_price
            return momentum
        except Exception as e:
            self.logger.error(f"Error calculating price momentum: {e}")
            return 0.0
    
    def _get_sentiment_score(self, symbol: str, asset_info: Dict) -> float:
        """
        Get sentiment score from various sources
        Returns value between -1 (very negative) and 1 (very positive)
        """
        sentiment_scores = []
        
        try:
            # GitHub activity for crypto projects
            if asset_info['type'] == 'crypto' and symbol.startswith(('BTC', 'ETH')):
                github_sentiment = self._get_github_sentiment(symbol)
                if github_sentiment is not None:
                    sentiment_scores.append(github_sentiment)
            
            # Fear & Greed Index for crypto
            if asset_info['type'] == 'crypto':
                fear_greed = self._get_fear_greed_index()
                if fear_greed is not None:
                    sentiment_scores.append(fear_greed)
            
            # News sentiment (simplified)
            news_sentiment = self._get_news_sentiment(asset_info['name'])
            if news_sentiment is not None:
                sentiment_scores.append(news_sentiment)
                
        except Exception as e:
            self.logger.error(f"Error getting sentiment for {symbol}: {e}")
        
        # Return average sentiment or None if no data
        if sentiment_scores:
            return sum(sentiment_scores) / len(sentiment_scores)
        return None
    
    def _get_github_sentiment(self, symbol: str) -> float:
        """Get sentiment from GitHub activity for crypto projects"""
        try:
            if not self.validate_config(['GITHUB_TOKEN']):
                return None
            
            # Map symbols to GitHub repos
            repo_map = {
                'BTC': 'bitcoin/bitcoin',
                'ETH': 'ethereum/ethereum'
            }
            
            base_symbol = symbol.split('-')[0]
            repo = repo_map.get(base_symbol)
            
            if not repo:
                return None
            
            # Get recent activity
            activity = self.github_client.get_repo_activity(repo)
            if not activity:
                return None
            
            # Simple sentiment based on activity level
            # More commits/issues = more positive sentiment
            total_activity = (
                activity.get('commits', 0) + 
                activity.get('issues', 0) + 
                activity.get('pull_requests', 0)
            )
            
            # Normalize to -1 to 1 scale (very simple)
            if total_activity > 100:
                return 0.5  # High activity = positive
            elif total_activity > 50:
                return 0.2  # Medium activity = slightly positive
            else:
                return -0.1  # Low activity = slightly negative
                
        except Exception as e:
            self.logger.error(f"Error getting GitHub sentiment: {e}")
            return None
    
    def _get_fear_greed_index(self) -> float:
        """Get Fear & Greed Index for crypto"""
        try:
            # Free API for Fear & Greed Index
            response = requests.get(
                'https://api.alternative.me/fng/',
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    value = int(data['data'][0]['value'])
                    # Convert 0-100 scale to -1 to 1 scale
                    # 0 = extreme fear (-1), 100 = extreme greed (1)
                    normalized = (value - 50) / 50
                    return max(-1, min(1, normalized))
                    
        except Exception as e:
            self.logger.error(f"Error getting Fear & Greed Index: {e}")
            
        return None
    
    def _get_news_sentiment(self, asset_name: str) -> float:
        """
        Get news sentiment (simplified implementation)
        In production, you'd use services like NewsAPI or sentiment analysis
        """
        try:
            # This is a placeholder - in real implementation you'd:
            # 1. Fetch recent news about the asset
            # 2. Run sentiment analysis on headlines/content
            # 3. Return sentiment score
            
            # For now, return a random-ish sentiment based on asset name hash
            # This simulates varying sentiment
            hash_val = hash(asset_name + str(datetime.now().date())) % 100
            
            if hash_val > 70:
                return 0.3  # Positive sentiment
            elif hash_val > 30:
                return 0.0  # Neutral sentiment
            else:
                return -0.2  # Negative sentiment
                
        except Exception as e:
            self.logger.error(f"Error getting news sentiment: {e}")
            return None
    
    def _check_divergence(self, symbol: str, asset_info: Dict, 
                         price_momentum: float, sentiment_score: float) -> Dict[str, Any]:
        """Check for sentiment-price divergence"""
        try:
            # Calculate divergence
            # Positive divergence: negative sentiment but positive price
            # Negative divergence: positive sentiment but negative price
            
            divergence_score = abs(price_momentum - sentiment_score)
            
            if divergence_score > self.divergence_threshold:
                # Determine type of divergence
                if price_momentum > 0 and sentiment_score < -0.1:
                    divergence_type = "Bullish Divergence"
                    description = (f"Price rising ({price_momentum*100:.1f}%) while sentiment "
                                 f"remains negative ({sentiment_score:.2f}). "
                                 f"This could indicate undervalued asset or sentiment lag.")
                    severity = 'medium'
                    
                elif price_momentum < 0 and sentiment_score > 0.1:
                    divergence_type = "Bearish Divergence"
                    description = (f"Price falling ({price_momentum*100:.1f}%) while sentiment "
                                 f"remains positive ({sentiment_score:.2f}). "
                                 f"This could indicate overvalued asset or denial phase.")
                    severity = 'medium'
                    
                else:
                    return None  # No significant divergence pattern
                
                # Increase severity for larger divergences
                if divergence_score > self.divergence_threshold * 2:
                    severity = 'high'
                
                return self.create_finding(
                    title=f"{divergence_type} in {asset_info['name']}",
                    description=description,
                    severity=severity,
                    confidence=0.6,
                    symbol=symbol,
                    market_type=asset_info['type'],
                    metadata={
                        'divergence_type': divergence_type,
                        'price_momentum': price_momentum,
                        'sentiment_score': sentiment_score,
                        'divergence_score': divergence_score,
                        'threshold': self.divergence_threshold
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Error checking divergence for {symbol}: {e}")
            
        return None
