"""
IntradayOrderBookImbalanceAgent - Detects order book imbalances

Analyzes real-time bid-ask volume disparities across order book levels
to identify potential impending price moves or liquidity shocks.

Strategy:
- Monitor bid/ask volume at top N price levels
- Calculate imbalance ratio: (bid_vol - ask_vol) / (bid_vol + ask_vol)
- Strong imbalance (>0.3) suggests directional pressure
- Combine with spread analysis for confidence
"""
import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class IntradayOrderBookImbalanceAgent(BaseAgent):
    """
    Detects short-term order book imbalances that may indicate 
    impending price moves or liquidity shocks.
    
    Order book imbalance is a leading indicator:
    - More bids than asks → upward pressure
    - More asks than bids → downward pressure
    - Sudden imbalance changes → potential breakout
    
    Works for both equities and crypto markets.
    """
    
    def __init__(self):
        super().__init__("IntradayOrderBookImbalanceAgent")
        self.imbalance_threshold = 0.30  # 30% imbalance
        self.depth_levels = 10  # Order book depth to analyze
        self.spread_threshold = 0.005  # 0.5% spread threshold
        
        # Equities watchlist (highly liquid)
        self.equity_watchlist = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AMD",
            "SPY", "QQQ", "IWM",
            "JPM", "BAC", "GS",
            "XOM", "CVX"
        ]
        
        # Crypto watchlist
        self.crypto_watchlist = [
            "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "MATIC-USD",
            "LINK-USD", "UNI-USD", "AAVE-USD", "ARB-USD", "OP-USD"
        ]
    
    def plan(self) -> Dict[str, Any]:
        """Plan the order book analysis."""
        return {
            "steps": [
                "fetch_order_book_data",
                "calculate_imbalances",
                "analyze_spread",
                "detect_signals",
                "generate_findings"
            ],
            "imbalance_threshold": self.imbalance_threshold,
            "depth_levels": self.depth_levels,
            "equity_count": len(self.equity_watchlist),
            "crypto_count": len(self.crypto_watchlist)
        }
    
    def act(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the analysis and return findings."""
        return self.analyze()
    
    def _fetch_order_book(self, symbol: str, market_type: str) -> Optional[Dict[str, Any]]:
        """
        Fetch order book data for a symbol.
        Returns bid/ask levels with volumes.
        """
        try:
            if market_type == "crypto":
                # Try crypto exchange API
                return self._fetch_crypto_order_book(symbol)
            else:
                # Try equity market data
                return self._fetch_equity_order_book(symbol)
        except Exception as e:
            logger.debug(f"Could not fetch order book for {symbol}: {e}")
        
        # Fallback to synthetic
        return self._generate_synthetic_order_book(symbol, market_type)
    
    def _fetch_crypto_order_book(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch order book from crypto exchange."""
        # In production, would use exchange APIs (Binance, Coinbase, etc.)
        # For now, return None to trigger synthetic data
        return None
    
    def _fetch_equity_order_book(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch Level 2 order book for equities."""
        # In production, would use market data provider
        # Requires Level 2 data subscription
        return None
    
    def _generate_synthetic_order_book(self, symbol: str, market_type: str) -> Dict[str, Any]:
        """Generate synthetic order book data for testing."""
        
        # Base price varies by market type
        if market_type == "crypto":
            if "BTC" in symbol:
                base_price = random.uniform(40000, 70000)
            elif "ETH" in symbol:
                base_price = random.uniform(2000, 4000)
            else:
                base_price = random.uniform(1, 200)
            tick_size = base_price * 0.0001
        else:
            base_price = random.uniform(50, 500)
            tick_size = 0.01
        
        # Generate bid levels (below mid price)
        bids = []
        bid_price = base_price * (1 - random.uniform(0.0001, 0.001))
        for i in range(self.depth_levels):
            # Volume tends to increase further from mid
            volume = random.uniform(100, 10000) * (1 + i * 0.2)
            if market_type == "crypto":
                volume = volume / base_price  # Crypto volumes in base currency
            bids.append({
                "price": round(bid_price - i * tick_size, 4),
                "volume": round(volume, 2),
                "order_count": random.randint(5, 100)
            })
        
        # Generate ask levels (above mid price)
        asks = []
        ask_price = base_price * (1 + random.uniform(0.0001, 0.001))
        for i in range(self.depth_levels):
            volume = random.uniform(100, 10000) * (1 + i * 0.2)
            if market_type == "crypto":
                volume = volume / base_price
            asks.append({
                "price": round(ask_price + i * tick_size, 4),
                "volume": round(volume, 2),
                "order_count": random.randint(5, 100)
            })
        
        # Inject imbalance in some cases
        if random.random() < 0.25:  # 25% chance of significant imbalance
            if random.random() < 0.5:
                # Heavy bids (buying pressure)
                for bid in bids:
                    bid["volume"] *= random.uniform(2, 5)
            else:
                # Heavy asks (selling pressure)
                for ask in asks:
                    ask["volume"] *= random.uniform(2, 5)
        
        return {
            "symbol": symbol,
            "market_type": market_type,
            "bids": bids,
            "asks": asks,
            "mid_price": (bids[0]["price"] + asks[0]["price"]) / 2,
            "spread": asks[0]["price"] - bids[0]["price"],
            "timestamp": datetime.utcnow()
        }
    
    def _calculate_imbalance(self, order_book: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate order book imbalance metrics.
        
        Imbalance ratio = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        Range: -1 (all asks) to +1 (all bids)
        """
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        
        # Total volumes
        total_bid_vol = sum(b["volume"] for b in bids)
        total_ask_vol = sum(a["volume"] for a in asks)
        total_vol = total_bid_vol + total_ask_vol
        
        if total_vol == 0:
            return None
        
        # Overall imbalance
        imbalance = (total_bid_vol - total_ask_vol) / total_vol
        
        # Top-of-book imbalance (most relevant for immediate price action)
        top_bid_vol = bids[0]["volume"] if bids else 0
        top_ask_vol = asks[0]["volume"] if asks else 0
        top_vol = top_bid_vol + top_ask_vol
        top_imbalance = (top_bid_vol - top_ask_vol) / top_vol if top_vol > 0 else 0
        
        # Spread analysis
        spread = order_book.get("spread", 0)
        mid_price = order_book.get("mid_price", 1)
        spread_pct = spread / mid_price if mid_price > 0 else 0
        
        # Order count imbalance
        bid_orders = sum(b.get("order_count", 1) for b in bids)
        ask_orders = sum(a.get("order_count", 1) for a in asks)
        order_imbalance = (bid_orders - ask_orders) / (bid_orders + ask_orders) if (bid_orders + ask_orders) > 0 else 0
        
        # Depth profile (volume at different levels)
        bid_depth_profile = [b["volume"] for b in bids]
        ask_depth_profile = [a["volume"] for a in asks]
        
        # Detect walls (large orders at specific levels)
        bid_wall = max(bid_depth_profile) if bid_depth_profile else 0
        ask_wall = max(ask_depth_profile) if ask_depth_profile else 0
        avg_level_vol = (sum(bid_depth_profile) + sum(ask_depth_profile)) / (len(bid_depth_profile) + len(ask_depth_profile)) if bid_depth_profile or ask_depth_profile else 1
        
        has_bid_wall = bid_wall > avg_level_vol * 3
        has_ask_wall = ask_wall > avg_level_vol * 3
        
        return {
            "total_imbalance": imbalance,
            "top_of_book_imbalance": top_imbalance,
            "order_count_imbalance": order_imbalance,
            "spread_pct": spread_pct,
            "total_bid_volume": total_bid_vol,
            "total_ask_volume": total_ask_vol,
            "bid_ask_ratio": total_bid_vol / total_ask_vol if total_ask_vol > 0 else float('inf'),
            "has_bid_wall": has_bid_wall,
            "has_ask_wall": has_ask_wall,
            "bid_wall_size": bid_wall if has_bid_wall else 0,
            "ask_wall_size": ask_wall if has_ask_wall else 0
        }
    
    def _get_signal_direction(self, metrics: Dict[str, Any]) -> str:
        """Determine signal direction from imbalance."""
        imbalance = metrics.get("total_imbalance", 0)
        if imbalance > self.imbalance_threshold:
            return "BULLISH"
        elif imbalance < -self.imbalance_threshold:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def _classify_imbalance_type(self, metrics: Dict[str, Any]) -> str:
        """Classify the type of order book imbalance."""
        has_bid_wall = metrics.get("has_bid_wall", False)
        has_ask_wall = metrics.get("has_ask_wall", False)
        imbalance = abs(metrics.get("total_imbalance", 0))
        spread = metrics.get("spread_pct", 0)
        
        if has_bid_wall and not has_ask_wall:
            return "BID_WALL_SUPPORT"
        elif has_ask_wall and not has_bid_wall:
            return "ASK_WALL_RESISTANCE"
        elif spread > self.spread_threshold:
            return "WIDE_SPREAD_IMBALANCE"
        elif imbalance > 0.5:
            return "EXTREME_IMBALANCE"
        else:
            return "MODERATE_IMBALANCE"
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main analysis: detect order book imbalances.
        
        Returns findings for symbols with significant bid/ask
        imbalances suggesting directional pressure.
        """
        findings = []
        
        try:
            all_symbols = [
                (s, "equity") for s in self.equity_watchlist
            ] + [
                (s, "crypto") for s in self.crypto_watchlist
            ]
            
            logger.info(f"Analyzing order books for {len(all_symbols)} symbols")
            
            for symbol, market_type in all_symbols:
                try:
                    # Fetch order book
                    order_book = self._fetch_order_book(symbol, market_type)
                    
                    if not order_book:
                        continue
                    
                    # Calculate imbalance metrics
                    metrics = self._calculate_imbalance(order_book)
                    
                    if not metrics:
                        continue
                    
                    total_imbalance = abs(metrics["total_imbalance"])
                    
                    # Check if imbalance exceeds threshold
                    if total_imbalance >= self.imbalance_threshold:
                        direction = self._get_signal_direction(metrics)
                        imbalance_type = self._classify_imbalance_type(metrics)
                        severity = self._calculate_severity(metrics)
                        
                        # Confidence based on multiple confirming factors
                        confidence = 0.5
                        if abs(metrics["top_of_book_imbalance"]) > self.imbalance_threshold:
                            confidence += 0.15
                        if abs(metrics["order_count_imbalance"]) > 0.2:
                            confidence += 0.1
                        if metrics["has_bid_wall"] or metrics["has_ask_wall"]:
                            confidence += 0.15
                        confidence = min(0.95, confidence + total_imbalance * 0.2)
                        
                        findings.append({
                            "title": f"Order Book Imbalance: {symbol} - {direction}",
                            "description": (
                                f"{symbol} ({market_type}) showing {total_imbalance*100:.1f}% order book imbalance. "
                                f"Bid/Ask ratio: {metrics['bid_ask_ratio']:.2f}. "
                                f"Type: {imbalance_type.replace('_', ' ').title()}. "
                                f"Spread: {metrics['spread_pct']*100:.3f}%. "
                                f"{'Bid wall detected. ' if metrics['has_bid_wall'] else ''}"
                                f"{'Ask wall detected. ' if metrics['has_ask_wall'] else ''}"
                                f"Signal direction: {direction}."
                            ),
                            "severity": severity,
                            "confidence": confidence,
                            "symbol": symbol,
                            "market_type": market_type,
                            "metadata": {
                                "total_imbalance_pct": round(metrics["total_imbalance"] * 100, 2),
                                "top_book_imbalance_pct": round(metrics["top_of_book_imbalance"] * 100, 2),
                                "order_count_imbalance_pct": round(metrics["order_count_imbalance"] * 100, 2),
                                "bid_ask_ratio": round(metrics["bid_ask_ratio"], 3),
                                "spread_pct": round(metrics["spread_pct"] * 100, 4),
                                "total_bid_volume": round(metrics["total_bid_volume"], 2),
                                "total_ask_volume": round(metrics["total_ask_volume"], 2),
                                "has_bid_wall": metrics["has_bid_wall"],
                                "has_ask_wall": metrics["has_ask_wall"],
                                "bid_wall_size": round(metrics["bid_wall_size"], 2),
                                "ask_wall_size": round(metrics["ask_wall_size"], 2),
                                "imbalance_type": imbalance_type,
                                "signal_direction": direction,
                                "mid_price": order_book.get("mid_price"),
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        })
                        
                except Exception as e:
                    logger.debug(f"Error analyzing {symbol}: {e}")
                    continue
            
            # Sort by imbalance magnitude
            findings.sort(
                key=lambda x: abs(x["metadata"]["total_imbalance_pct"]), 
                reverse=True
            )
            
            logger.info(f"Found {len(findings)} order book imbalances")
            
        except Exception as e:
            logger.error(f"Error in order book analysis: {e}")
            findings.append({
                "title": "Order Book Analysis Error",
                "description": f"Analysis encountered an error: {str(e)}",
                "severity": "low",
                "confidence": 1.0,
                "metadata": {"error": str(e)}
            })
        
        return findings
    
    def _calculate_severity(self, metrics: Dict[str, Any]) -> str:
        """Calculate severity based on imbalance characteristics."""
        imbalance = abs(metrics.get("total_imbalance", 0))
        has_wall = metrics.get("has_bid_wall") or metrics.get("has_ask_wall")
        spread = metrics.get("spread_pct", 0)
        
        if imbalance > 0.5 and has_wall:
            return "high"
        elif imbalance > 0.4 or (imbalance > 0.3 and has_wall):
            return "medium"
        else:
            return "low"
    
    def reflect(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reflect on the analysis results."""
        bullish = sum(1 for f in results if f.get("metadata", {}).get("signal_direction") == "BULLISH")
        bearish = sum(1 for f in results if f.get("metadata", {}).get("signal_direction") == "BEARISH")
        
        equity_findings = [f for f in results if f.get("market_type") == "equity"]
        crypto_findings = [f for f in results if f.get("market_type") == "crypto"]
        
        imbalance_types = {}
        for f in results:
            itype = f.get("metadata", {}).get("imbalance_type", "UNKNOWN")
            imbalance_types[itype] = imbalance_types.get(itype, 0) + 1
        
        return {
            "finding_count": len(results),
            "high_severity_count": sum(1 for f in results if f.get("severity") == "high"),
            "bullish_signals": bullish,
            "bearish_signals": bearish,
            "equity_findings": len(equity_findings),
            "crypto_findings": len(crypto_findings),
            "imbalance_types": imbalance_types,
            "wall_detections": sum(1 for f in results if f.get("metadata", {}).get("has_bid_wall") or f.get("metadata", {}).get("has_ask_wall")),
            "avg_imbalance_pct": sum(abs(f.get("metadata", {}).get("total_imbalance_pct", 0)) for f in results) / len(results) if results else 0
        }
