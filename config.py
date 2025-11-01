import os
from typing import Dict, Any

class Config:
    # API Keys from environment
    COINBASE_API_KEY = os.getenv("COINBASE_API_KEY", "")
    COINBASE_SECRET = os.getenv("COINBASE_SECRET", "")
    COINBASE_PASSPHRASE = os.getenv("COINBASE_PASSPHRASE", "")
    ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Email configuration
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    
    # Agent configuration
    DEFAULT_AGENT_INTERVAL = 60  # minutes
    MAX_FINDINGS_PER_AGENT = 100
    
    # Risk thresholds
    WHALE_WALLET_THRESHOLD = 1000  # ETH
    ARBITRAGE_PROFIT_THRESHOLD = 0.02  # 2%
    SENTIMENT_DIVERGENCE_THRESHOLD = 0.3
    GEOPOLITICAL_RISK_THRESHOLD = 50  # 0-100 scale
    MARKET_CORRECTION_THRESHOLD = 0.10  # 10% decline
    RSI_OVERBOUGHT = 70  # RSI threshold
    VIX_WARNING = 25  # VIX warning level
    VIX_CRITICAL = 35  # VIX critical level
    
    @classmethod
    def get_agent_config(cls, agent_name: str) -> Dict[str, Any]:
        """Get configuration specific to an agent"""
        configs = {
            "MacroWatcherAgent": {
                "interval": 60,
                "sources": ["yahoo", "fed"],
                "indicators": ["vix", "dxy", "rates"]
            },
            "WhaleWalletWatcherAgent": {
                "interval": 15,
                "threshold": cls.WHALE_WALLET_THRESHOLD,
                "networks": ["ethereum", "bitcoin"]
            },
            "ArbitrageFinderAgent": {
                "interval": 5,
                "exchanges": ["coinbase", "kraken", "kucoin"],
                "min_profit": cls.ARBITRAGE_PROFIT_THRESHOLD
            },
            "SentimentDivergenceAgent": {
                "interval": 30,
                "sources": ["twitter", "reddit", "news"],
                "threshold": cls.SENTIMENT_DIVERGENCE_THRESHOLD
            },
            "GeopoliticalRiskAgent": {
                "interval": 30,
                "risk_threshold": cls.GEOPOLITICAL_RISK_THRESHOLD,
                "max_articles_per_region": 5,
                "hotspots": ["Taiwan", "Ukraine", "Middle East", "China-US", "North Korea", "South China Sea"]
            },
            "MarketCorrectionAgent": {
                "interval": 15,
                "correction_threshold": cls.MARKET_CORRECTION_THRESHOLD,
                "rsi_overbought": cls.RSI_OVERBOUGHT,
                "vix_warning": cls.VIX_WARNING,
                "vix_critical": cls.VIX_CRITICAL
            }
        }
        return configs.get(agent_name, {"interval": cls.DEFAULT_AGENT_INTERVAL})
