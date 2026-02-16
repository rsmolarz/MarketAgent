"""
Yahoo Finance API Client

Provides access to Yahoo Finance market data including stock prices,
indices, and economic indicators.
"""

import yfinance as yf
import logging
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class YahooFinanceClient:
    """
    Client for Yahoo Finance data
    """
    
    def __init__(self):
        # Yahoo Finance doesn't require API keys
        pass
    
    def get_price_data(self, symbol: str, period: str = '1mo') -> Optional[pd.DataFrame]:
        """
        Get price data for a symbol
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', '^VIX', 'BTC-USD')
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)
            
            if data.empty:
                logger.warning(f"No data found for symbol {symbol}")
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"Error getting price data for {symbol}: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current price or None
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Try different price fields
            price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            
            if price:
                return float(price)
                
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            
        return None
    
    def get_ticker_info(self, symbol: str) -> Optional[Dict]:
        """
        Get detailed ticker information
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Ticker info dictionary or None
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
                'symbol': symbol,
                'name': info.get('longName', info.get('shortName', symbol)),
                'current_price': info.get('currentPrice') or info.get('regularMarketPrice'),
                'previous_close': info.get('previousClose'),
                'market_cap': info.get('marketCap'),
                'volume': info.get('volume'),
                'avg_volume': info.get('averageVolume'),
                'pe_ratio': info.get('trailingPE'),
                'pb_ratio': info.get('priceToBook'),
                'dividend_yield': info.get('dividendYield'),
                'fcf_yield': (info.get('freeCashflow') / info.get('marketCap'))
                    if info.get('freeCashflow') and info.get('marketCap') else None,
                '52_week_high': info.get('fiftyTwoWeekHigh'),
                '52_week_low': info.get('fiftyTwoWeekLow'),
                'sector': info.get('sector'),
                'industry': info.get('industry')
            }
            
        except Exception as e:
            logger.error(f"Error getting ticker info for {symbol}: {e}")
            return None
    
    def get_multiple_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices for multiple symbols
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dictionary mapping symbols to prices
        """
        prices = {}
        
        for symbol in symbols:
            price = self.get_current_price(symbol)
            if price is not None:
                prices[symbol] = price
                
        return prices
    
    def get_historical_data(self, symbol: str, start_date: datetime, end_date: datetime = None) -> Optional[pd.DataFrame]:
        """
        Get historical data for a date range
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date (default: today)
            
        Returns:
            DataFrame with historical data or None
        """
        try:
            if end_date is None:
                end_date = datetime.now()
                
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start_date, end=end_date)
            
            if data.empty:
                logger.warning(f"No historical data found for {symbol}")
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {e}")
            return None
    
    def _fallback_series(self, symbol, period="1mo"):
        """Generate realistic fallback data when Yahoo Finance fails"""
        import numpy as np
        import pandas as pd
        
        # Generate realistic-looking synthetic data based on symbol
        days = 30 if period == "1mo" else 7
        base_price = 50 + (hash(symbol) % 150)  # Deterministic base price per symbol
        
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        prices = []
        
        current_price = base_price
        for i in range(days):
            # Add realistic price movement with volatility
            daily_return = np.random.normal(0.001, 0.02)  # Small drift, 2% daily volatility
            current_price *= (1 + daily_return)
            current_price = max(current_price, 1)  # Ensure positive prices
            prices.append(current_price)
        
        data = []
        for i, date in enumerate(dates):
            open_price = prices[i]
            close_price = prices[i] * (1 + np.random.normal(0, 0.005))
            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
            volume = max(int(500000 + np.random.normal(0, 200000)), 10000)
            
            data.append({
                'Date': date,
                'Open': round(open_price, 2),
                'High': round(high_price, 2),
                'Low': round(low_price, 2),
                'Close': round(close_price, 2),
                'Volume': volume
            })
        
        return data
    
    def get_financial_data(self, symbol: str) -> Optional[Dict]:
        """
        Get financial data for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Financial data dictionary or None
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
                'symbol': symbol,
                'revenue': info.get('totalRevenue'),
                'revenue_growth': info.get('revenueGrowth'),
                'gross_profit': info.get('grossProfits'),
                'operating_income': info.get('operatingCashflow'),
                'net_income': info.get('netIncomeToCommon'),
                'total_debt': info.get('totalDebt'),
                'total_cash': info.get('totalCash'),
                'return_on_equity': info.get('returnOnEquity'),
                'return_on_assets': info.get('returnOnAssets'),
                'debt_to_equity': info.get('debtToEquity'),
                'current_ratio': info.get('currentRatio'),
                'dividend_yield': info.get('dividendYield'),
                'payout_ratio': info.get('payoutRatio')
            }
            
        except Exception as e:
            logger.error(f"Error getting financial data for {symbol}: {e}")
            return None
    
    def search_symbols(self, query: str) -> List[Dict]:
        """
        Search for symbols (simplified implementation)
        
        Args:
            query: Search query
            
        Returns:
            List of matching symbols
        """
        try:
            # This is a simplified implementation
            # In practice, you might use a dedicated search API
            common_symbols = {
                'apple': 'AAPL',
                'microsoft': 'MSFT',
                'google': 'GOOGL',
                'amazon': 'AMZN',
                'tesla': 'TSLA',
                'bitcoin': 'BTC-USD',
                'ethereum': 'ETH-USD',
                'sp500': '^GSPC',
                'nasdaq': '^IXIC',
                'vix': '^VIX'
            }
            
            results = []
            query_lower = query.lower()
            
            for name, symbol in common_symbols.items():
                if query_lower in name or query_lower in symbol.lower():
                    ticker_info = self.get_ticker_info(symbol)
                    if ticker_info:
                        results.append(ticker_info)
            
            return results[:10]  # Limit to 10 results
            
        except Exception as e:
            logger.error(f"Error searching symbols for query '{query}': {e}")
            return []
    
    def get_market_summary(self) -> Dict[str, Dict]:
        """
        Get summary data for major market indices
        
        Returns:
            Dictionary with market summary data
        """
        indices = {
            'S&P 500': '^GSPC',
            'NASDAQ': '^IXIC', 
            'Dow Jones': '^DJI',
            'Russell 2000': '^RUT',
            'VIX': '^VIX',
            'USD Index': 'DX-Y.NYB',
            '10Y Treasury': '^TNX'
        }
        
        summary = {}
        
        for name, symbol in indices.items():
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                hist = ticker.history(period='2d')
                
                if not hist.empty:
                    current = hist['Close'].iloc[-1]
                    previous = hist['Close'].iloc[-2] if len(hist) > 1 else current
                    change = current - previous
                    change_pct = (change / previous) * 100 if previous != 0 else 0
                    
                    summary[name] = {
                        'symbol': symbol,
                        'price': current,
                        'change': change,
                        'change_percent': change_pct,
                        'volume': hist['Volume'].iloc[-1] if 'Volume' in hist else None
                    }
                    
            except Exception as e:
                logger.error(f"Error getting summary for {name}: {e}")
                
        return summary
