"""
Crypto Prediction Agent

Generates daily cryptocurrency price predictions using modular analyzers:
- Technical Analysis (RSI, MACD, ADX)
- Orderflow Analysis (funding rates, OI, volume)
- Market Profile (POC, VAH, VAL)
- VWAP Analysis

Features:
- Regime-aware predictions
- Crypto-specific risk gating
- Multi-signal ensemble
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent
from .analyzers.crypto_technical import CryptoTechnicalAnalyzer
from .analyzers.crypto_orderflow import CryptoOrderflowAnalyzer
from .analyzers.crypto_profile import CryptoProfileAnalyzer
from .analyzers.crypto_vwap import CryptoVWAPAnalyzer
from .analyzers.crypto_risk_gate import CryptoRiskGate
from .analyzers.crypto_ensemble import CryptoEnsemblePredictor, CryptoRegimeDetector
from data_sources.coinbase_client import CoinbaseClient
from data_sources.yahoo_finance_client import YahooFinanceClient

logger = logging.getLogger(__name__)


class CryptoPredictionAgent(BaseAgent):
    """
    Daily Crypto Prediction Agent.
    
    Generates actionable predictions for major cryptocurrencies
    using technical, orderflow, profile, and VWAP signals.
    """
    
    def __init__(self):
        super().__init__()
        
        self.coinbase_client = CoinbaseClient()
        self.yahoo_client = YahooFinanceClient()
        
        self.technical_analyzer = CryptoTechnicalAnalyzer()
        self.orderflow_analyzer = CryptoOrderflowAnalyzer()
        self.profile_analyzer = CryptoProfileAnalyzer()
        self.vwap_analyzer = CryptoVWAPAnalyzer()
        self.risk_gate = CryptoRiskGate()
        self.ensemble = CryptoEnsemblePredictor()
        self.regime_detector = CryptoRegimeDetector()
        
        self.instruments = [
            {
                'symbol': 'BTC-USD',
                'coinbase_symbol': 'BTC/USD',
                'exchange': 'Coinbase',
                'market_type': 'spot',
                'description': 'Bitcoin / US Dollar'
            },
            {
                'symbol': 'ETH-USD',
                'coinbase_symbol': 'ETH/USD',
                'exchange': 'Coinbase',
                'market_type': 'spot',
                'description': 'Ethereum / US Dollar'
            },
            {
                'symbol': 'SOL-USD',
                'coinbase_symbol': 'SOL/USD',
                'exchange': 'Coinbase',
                'market_type': 'spot',
                'description': 'Solana / US Dollar'
            },
            {
                'symbol': 'AVAX-USD',
                'coinbase_symbol': 'AVAX/USD',
                'exchange': 'Coinbase',
                'market_type': 'spot',
                'description': 'Avalanche / US Dollar'
            },
            {
                'symbol': 'LINK-USD',
                'coinbase_symbol': 'LINK/USD',
                'exchange': 'Coinbase',
                'market_type': 'spot',
                'description': 'Chainlink / US Dollar'
            },
            {
                'symbol': 'DOGE-USD',
                'coinbase_symbol': 'DOGE/USD',
                'exchange': 'Coinbase',
                'market_type': 'spot',
                'description': 'Dogecoin / US Dollar'
            }
        ]
        
        self.confidence_thresholds = {
            'high': 0.70,
            'medium': 0.55
        }
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Generate daily crypto predictions.
        
        Returns:
            List of prediction findings
        """
        findings = []
        
        for instrument in self.instruments:
            try:
                prediction = self._generate_prediction(instrument)
                if prediction and prediction.get('status') == 'success':
                    finding = self._create_finding(prediction, instrument)
                    if finding:
                        findings.append(finding)
            except Exception as e:
                self.logger.error(f"Error predicting {instrument['symbol']}: {e}")
        
        self._log_summary(findings)
        
        return findings
    
    def _generate_prediction(self, instrument: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate prediction for a single cryptocurrency"""
        symbol = instrument['symbol']
        
        price_data = self.yahoo_client.get_price_data(symbol, period='60d')
        
        if price_data is None or len(price_data) < 30:
            self.logger.warning(f"Insufficient data for {symbol}")
            return None
        
        technical = self.technical_analyzer.analyze(price_data)
        
        ticker_data = self._get_ticker_data(instrument['coinbase_symbol'])
        funding_rate = ticker_data.get('funding_rate')
        oi = ticker_data.get('open_interest')
        oi_change = ticker_data.get('oi_change_pct')
        
        orderflow = self.orderflow_analyzer.analyze(
            price_data,
            funding_rate=funding_rate,
            open_interest=oi,
            oi_change_pct=oi_change
        )
        
        profile = self.profile_analyzer.analyze(price_data)
        
        vwap = self.vwap_analyzer.analyze(price_data)
        
        vol_pct = self._calculate_volatility(price_data)
        regime_info = self.regime_detector.detect(
            adx=technical.get('adx'),
            vwap_z=vwap.get('vwap_z'),
            vol_pct=vol_pct
        )
        
        risk_eval = self.risk_gate.evaluate(
            funding_rate=funding_rate,
            oi_change_pct=oi_change,
            price_volatility_pct=vol_pct,
            vwap_z=vwap.get('vwap_z'),
            adx=technical.get('adx')
        )
        
        ensemble_prediction = self.ensemble.generate_prediction(
            technical=technical,
            orderflow=orderflow,
            profile=profile,
            vwap=vwap,
            risk_gate=risk_eval,
            regime=regime_info.get('regime', 'MIXED'),
            regime_confidence=regime_info.get('regime_confidence', 0.5)
        )
        
        result = {
            'symbol': symbol,
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'instrument_meta': instrument,
            **ensemble_prediction,
            'regime': regime_info.get('regime'),
            'regime_confidence': regime_info.get('regime_confidence'),
            'macro_risk_level': risk_eval.get('risk_level'),
            'macro_risk_score': risk_eval.get('risk_score'),
            'macro_reasons': risk_eval.get('reasons', []),
            'rsi': technical.get('rsi'),
            'adx': technical.get('adx'),
            'macd_hist': technical.get('macd_hist'),
            'funding_rate': funding_rate,
            'open_interest': oi,
            'oi_change_pct': oi_change,
            'rth_vwap': vwap.get('rth_vwap'),
            'rth_vwap_std': vwap.get('rth_vwap_std'),
            'rth_close': vwap.get('rth_close'),
            'vwap_z': vwap.get('vwap_z'),
            'poc': profile.get('poc'),
            'vah': profile.get('vah'),
            'val': profile.get('val'),
            'in_value': profile.get('in_value'),
            'vol_pct': vol_pct,
            'daily_lookback_days': 60,
            'intraday_lookback_hours': 24,
            'timeframe': '1d',
            'status': 'success'
        }
        
        return result
    
    def _get_ticker_data(self, coinbase_symbol: str) -> Dict[str, Any]:
        """Get ticker data from Coinbase"""
        try:
            ticker = self.coinbase_client.get_ticker(coinbase_symbol)
            if ticker:
                return {
                    'last_price': float(ticker.get('last', 0)),
                    'price_change_pct': float(ticker.get('percentage', 0)),
                    'volume': float(ticker.get('baseVolume', 0)),
                    'funding_rate': None,
                    'open_interest': None,
                    'oi_change_pct': None
                }
        except Exception as e:
            self.logger.debug(f"Error getting ticker for {coinbase_symbol}: {e}")
        
        return {}
    
    def _calculate_volatility(self, price_data) -> float:
        """Calculate recent price volatility percentage"""
        try:
            if price_data is None or len(price_data) < 5:
                return 1.0
            
            close = price_data['Close'].values
            returns = (close[1:] - close[:-1]) / close[:-1]
            volatility = float(abs(returns[-1]) * 100) if len(returns) > 0 else 1.0
            
            return volatility
        except Exception:
            return 1.0
    
    def _create_finding(self, prediction: Dict[str, Any], instrument: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a finding from prediction"""
        confidence = prediction.get('confidence', 'LOW')
        direction = prediction.get('direction', 'NEUTRAL')
        prob_up = prediction.get('prob_up', 0.5)
        
        if confidence == 'LOW' and direction == 'NEUTRAL':
            return None
        
        symbol = prediction['symbol']
        
        if direction == 'UP':
            title = f"Crypto Forecast: {symbol} BULLISH ({confidence} confidence)"
            severity = 'high' if confidence == 'HIGH' else 'medium'
        elif direction == 'DOWN':
            title = f"Crypto Forecast: {symbol} BEARISH ({confidence} confidence)"
            severity = 'high' if confidence == 'HIGH' else 'medium'
        else:
            title = f"Crypto Forecast: {symbol} NEUTRAL"
            severity = 'low'
        
        regime = prediction.get('regime', 'MIXED')
        macro_level = prediction.get('macro_risk_level', 'low')
        
        description = (
            f"AI Crypto Prediction for {symbol}: {direction} with {confidence} confidence. "
            f"P(UP)={prob_up:.1%}. Market regime: {regime}. "
            f"Risk level: {macro_level}. "
            f"Technical RSI={prediction.get('rsi', 'N/A')}, ADX={prediction.get('adx', 'N/A')}. "
            f"Price vs VWAP: {prediction.get('vwap_z', 0):.1f}σ."
        )
        
        conf_score = {'HIGH': 0.85, 'MEDIUM': 0.65, 'LOW': 0.45}.get(confidence, 0.5)
        
        return self.create_finding(
            title=title,
            description=description,
            severity=severity,
            confidence=conf_score,
            symbol=symbol.replace('-USD', ''),
            market_type='crypto',
            metadata={
                'prediction_type': 'crypto_daily_forecast',
                'direction': direction,
                'confidence_level': confidence,
                'prob_up': prob_up,
                'ensemble_score_final': prediction.get('ensemble_score_final'),
                'regime': regime,
                'regime_confidence': prediction.get('regime_confidence'),
                'macro_risk_level': macro_level,
                'macro_risk_score': prediction.get('macro_risk_score'),
                'macro_reasons': prediction.get('macro_reasons', []),
                'technical': {
                    'rsi': prediction.get('rsi'),
                    'adx': prediction.get('adx'),
                    'macd_hist': prediction.get('macd_hist'),
                    'bias': prediction.get('technical_bias')
                },
                'orderflow': {
                    'funding_rate': prediction.get('funding_rate'),
                    'open_interest': prediction.get('open_interest'),
                    'oi_change_pct': prediction.get('oi_change_pct'),
                    'bias': prediction.get('orderflow_bias')
                },
                'profile': {
                    'poc': prediction.get('poc'),
                    'vah': prediction.get('vah'),
                    'val': prediction.get('val'),
                    'in_value': prediction.get('in_value'),
                    'bias': prediction.get('auction_bias')
                },
                'vwap': {
                    'vwap': prediction.get('rth_vwap'),
                    'vwap_std': prediction.get('rth_vwap_std'),
                    'vwap_z': prediction.get('vwap_z'),
                    'bias': prediction.get('vwap_bias')
                },
                'contributions': prediction.get('contributions', {}),
                'exchange': instrument.get('exchange'),
                'market_type': instrument.get('market_type')
            }
        )
    
    def _log_summary(self, findings: List[Dict[str, Any]]):
        """Log prediction summary"""
        if not findings:
            self.logger.info("CryptoPredictionAgent: No actionable predictions generated")
            return
        
        bullish = sum(1 for f in findings if 'BULLISH' in f.get('title', ''))
        bearish = sum(1 for f in findings if 'BEARISH' in f.get('title', ''))
        neutral = len(findings) - bullish - bearish
        
        self.logger.info(
            f"CryptoPredictionAgent: Generated {len(findings)} predictions "
            f"(Bullish: {bullish}, Bearish: {bearish}, Neutral: {neutral})"
        )
