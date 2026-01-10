"""Technical Analysis module for signal generation and regime detection"""
from ta.signals import generate_signals
from ta.indicators import rsi, macd, bollinger, ma, ema, atr, adx
from ta.regime import classify_ta_regime, get_regime_agent_weights

__all__ = [
    'generate_signals',
    'rsi', 'macd', 'bollinger', 'ma', 'ema', 'atr', 'adx',
    'classify_ta_regime', 'get_regime_agent_weights'
]
