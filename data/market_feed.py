"""
Real-time market data feed using WebSocket consumers.

Provides streaming market data for crypto (24/7 minute-level),
equities (market hours), and derivatives. Integrates with the
sub-orchestrator refresh cycles.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class MarketTick:
    """A single market data tick."""
    symbol: str
    price: float
    volume: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    source: str = ""

    def age_seconds(self) -> float:
        return time.time() - self.timestamp


@dataclass
class OrderBookSnapshot:
    """Order book depth snapshot."""
    symbol: str
    bids: List[tuple[float, float]] = field(default_factory=list)  # (price, qty)
    asks: List[tuple[float, float]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def bid_depth(self) -> float:
        return sum(qty for _, qty in self.bids)

    @property
    def ask_depth(self) -> float:
        return sum(qty for _, qty in self.asks)

    @property
    def imbalance(self) -> float:
        """Order book imbalance: positive = buy pressure, negative = sell."""
        total = self.bid_depth + self.ask_depth
        if total == 0:
            return 0.0
        return (self.bid_depth - self.ask_depth) / total


class MarketDataFeed:
    """
    Real-time market data feed manager.

    Manages WebSocket connections to market data providers and distributes
    ticks to registered subscribers. Supports multiple data sources and
    automatic reconnection.
    """

    def __init__(self, max_buffer_size: int = 10000):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._latest_ticks: Dict[str, MarketTick] = {}
        self._tick_buffer: Dict[str, List[MarketTick]] = defaultdict(list)
        self._max_buffer = max_buffer_size
        self._running = False
        self._connections: Dict[str, Any] = {}
        self._stats = {
            "ticks_received": 0,
            "ticks_distributed": 0,
            "reconnections": 0,
        }

    def subscribe(self, symbol: str, callback: Callable[[MarketTick], None]) -> None:
        """Subscribe to real-time ticks for a symbol."""
        self._subscribers[symbol.upper()].append(callback)

    def unsubscribe(self, symbol: str, callback: Callable) -> None:
        """Unsubscribe from ticks."""
        subs = self._subscribers.get(symbol.upper(), [])
        if callback in subs:
            subs.remove(callback)

    def get_latest(self, symbol: str) -> Optional[MarketTick]:
        """Get the most recent tick for a symbol."""
        return self._latest_ticks.get(symbol.upper())

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get the most recent price for a symbol."""
        tick = self._latest_ticks.get(symbol.upper())
        return tick.price if tick else None

    def get_recent_ticks(self, symbol: str, n: int = 100) -> List[MarketTick]:
        """Get recent ticks from buffer."""
        return self._tick_buffer.get(symbol.upper(), [])[-n:]

    async def process_tick(self, tick: MarketTick) -> None:
        """Process an incoming market data tick."""
        symbol = tick.symbol.upper()
        self._latest_ticks[symbol] = tick
        self._stats["ticks_received"] += 1

        # Buffer management
        buffer = self._tick_buffer[symbol]
        buffer.append(tick)
        if len(buffer) > self._max_buffer:
            self._tick_buffer[symbol] = buffer[-self._max_buffer:]

        # Distribute to subscribers
        for callback in self._subscribers.get(symbol, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(tick)
                else:
                    callback(tick)
                self._stats["ticks_distributed"] += 1
            except Exception as e:
                logger.error(f"Subscriber callback error for {symbol}: {e}")

    async def connect_websocket(
        self,
        url: str,
        symbols: List[str],
        parser: Callable[[str], Optional[MarketTick]],
        name: str = "default",
    ) -> None:
        """
        Connect to a WebSocket feed and process incoming messages.

        Args:
            url: WebSocket URL.
            symbols: Symbols to subscribe to.
            parser: Function to parse WebSocket messages into MarketTick objects.
            name: Connection name for logging.
        """
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed")
            return

        self._running = True

        while self._running:
            try:
                async with websockets.connect(url) as ws:
                    self._connections[name] = ws
                    logger.info(f"WebSocket connected: {name} ({url})")

                    # Subscribe to symbols
                    subscribe_msg = json.dumps({
                        "type": "subscribe",
                        "symbols": symbols,
                    })
                    await ws.send(subscribe_msg)

                    async for message in ws:
                        if not self._running:
                            break
                        tick = parser(message)
                        if tick:
                            await self.process_tick(tick)

            except Exception as e:
                logger.error(f"WebSocket error ({name}): {e}")
                self._stats["reconnections"] += 1
                if self._running:
                    await asyncio.sleep(5)  # Reconnect delay

    async def stop(self) -> None:
        """Stop all WebSocket connections."""
        self._running = False
        for name, ws in self._connections.items():
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "active_connections": len(self._connections),
            "tracked_symbols": len(self._latest_ticks),
            "subscribers": sum(len(s) for s in self._subscribers.values()),
        }

    def get_all_latest(self) -> Dict[str, Dict[str, Any]]:
        """Get latest ticks for all tracked symbols."""
        return {
            symbol: {
                "price": tick.price,
                "volume": tick.volume,
                "bid": tick.bid,
                "ask": tick.ask,
                "age_seconds": tick.age_seconds(),
                "source": tick.source,
            }
            for symbol, tick in self._latest_ticks.items()
        }
