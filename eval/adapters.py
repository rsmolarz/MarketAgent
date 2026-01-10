from datetime import datetime
from typing import Dict, Any, List

def now():
    return datetime.utcnow().isoformat() + "Z"

def run_arbitrage_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "pair": "BTC/USD",
        "buy_exchange": "coinbase",
        "sell_exchange": "kraken",
        "buy_price": 50000.0,
        "sell_price": 50250.0,
        "profit_pct": 0.50,
        "timestamp": now()
    }]

def run_geopolitical_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "region": "Taiwan",
        "risk_score": 78,
        "headline": "Military exercises increase tensions near Taiwan Strait",
        "sentiment": -0.62,
        "source": "fixture",
        "timestamp": now()
    }]

def run_macro_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "symbol": "^VIX",
        "name": "VIX",
        "signal": "spike",
        "value": 34.7,
        "daily_change": 0.11,
        "timestamp": now()
    }]

def run_crypto_prediction_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "symbol": "BTC",
        "prediction": "bullish",
        "confidence": 0.72,
        "price_target": 52000.0,
        "timeframe": "24h",
        "timestamp": now()
    }]

def run_equity_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "symbol": "AAPL",
        "momentum_score": 0.85,
        "signal": "strong_buy",
        "rsi": 62.5,
        "macd_signal": "bullish",
        "timestamp": now()
    }]

def run_greatest_trade_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "signal_type": "bubble_risk",
        "sector": "real_estate",
        "risk_level": "elevated",
        "confidence": 0.68,
        "evidence": ["yield spread widening", "CDS pricing anomaly"],
        "timestamp": now()
    }]

def run_market_correction_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "signal": "correction_warning",
        "probability": 0.45,
        "indicators": ["RSI overbought", "VIX elevated"],
        "severity": "moderate",
        "timestamp": now()
    }]

def run_daily_prediction_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "symbol": "SPY",
        "direction": "up",
        "confidence": 0.65,
        "target_move_pct": 0.3,
        "regime": "bullish",
        "timestamp": now()
    }]

def run_sentiment_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "symbol": "TSLA",
        "price_sentiment_divergence": 0.32,
        "news_sentiment": -0.15,
        "price_trend": "up",
        "signal": "bearish_divergence",
        "timestamp": now()
    }]

def run_distressed_property_offline(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "property_id": "prop-12345",
            "address": "123 Foreclosure Lane",
            "city": "Phoenix",
            "state": "AZ",
            "signal_type": "deep_discount",
            "signal_strength": 78.5,
            "price": 185000.0,
            "estimated_value": 250000.0,
            "discount_pct": 26.0,
            "property_type": "single_family",
            "status": "foreclosure",
            "days_on_market": 45,
            "source": "fixture",
            "timestamp": now()
        },
        {
            "property_id": "prop-67890",
            "address": "456 Auction Drive",
            "city": "Las Vegas",
            "state": "NV",
            "signal_type": "auction_imminent",
            "signal_strength": 86.0,
            "price": 125000.0,
            "estimated_value": 160000.0,
            "discount_pct": 21.9,
            "property_type": "condo",
            "status": "auction",
            "days_on_market": 12,
            "source": "fixture",
            "timestamp": now()
        }
    ]
