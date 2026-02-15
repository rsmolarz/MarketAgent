"""
WebSocket manager for real-time streaming to UI.

Supports LangGraph's five streaming modes:
1. values - Stream full state after each node
2. updates - Stream only state deltas
3. events - Stream lifecycle events (node start/end)
4. messages - Stream LLM token-level output
5. custom - Application-defined event streams

Integrates with the portfolio orchestrator to stream analysis
progress in real time.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class StreamMode(str, Enum):
    VALUES = "values"
    UPDATES = "updates"
    EVENTS = "events"
    MESSAGES = "messages"
    CUSTOM = "custom"


class WebSocketManager:
    """
    Manages WebSocket connections with channel-based subscriptions.

    Clients can subscribe to specific channels:
    - "orchestrator" - Portfolio orchestrator events
    - "bonds", "crypto", "real_estate", "distressed" - Asset class events
    - "regime" - Regime detection updates
    - "alerts" - Drift and circuit breaker alerts
    - "all" - Everything
    """

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, channels: Optional[List[str]] = None):
        """Accept a WebSocket connection and subscribe to channels."""
        await websocket.accept()
        self._all_connections.add(websocket)

        channels = channels or ["all"]
        for channel in channels:
            if channel not in self._connections:
                self._connections[channel] = set()
            self._connections[channel].add(websocket)

        logger.info(f"WebSocket connected, channels: {channels}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket from all channels."""
        self._all_connections.discard(websocket)
        for channel_sockets in self._connections.values():
            channel_sockets.discard(websocket)

    async def send_to_channel(self, channel: str, data: Dict[str, Any]):
        """Send a message to all subscribers of a channel."""
        data["channel"] = channel
        data["timestamp"] = datetime.utcnow().isoformat()

        targets = set()
        targets.update(self._connections.get(channel, set()))
        targets.update(self._connections.get("all", set()))

        disconnected = set()
        for ws in targets:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast to all connected clients."""
        data["timestamp"] = datetime.utcnow().isoformat()

        disconnected = set()
        for ws in self._all_connections:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def stream_orchestrator_progress(
        self,
        run_id: str,
        node_name: str,
        status: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """Stream orchestrator node progress."""
        await self.send_to_channel("orchestrator", {
            "type": "node_progress",
            "mode": StreamMode.EVENTS.value,
            "run_id": run_id,
            "node": node_name,
            "status": status,
            "data": data or {},
        })

    async def stream_agent_result(
        self,
        asset_class: str,
        agent_name: str,
        result: Dict[str, Any],
    ):
        """Stream an individual agent result."""
        await self.send_to_channel(asset_class, {
            "type": "agent_result",
            "mode": StreamMode.UPDATES.value,
            "agent_name": agent_name,
            "result": result,
        })

    async def stream_regime_update(self, regime_data: Dict[str, Any]):
        """Stream regime classification update."""
        await self.send_to_channel("regime", {
            "type": "regime_update",
            "mode": StreamMode.VALUES.value,
            **regime_data,
        })

    async def stream_alert(self, alert_type: str, alert_data: Dict[str, Any]):
        """Stream an alert (drift detection, circuit breaker, etc.)."""
        await self.send_to_channel("alerts", {
            "type": "alert",
            "mode": StreamMode.CUSTOM.value,
            "alert_type": alert_type,
            **alert_data,
        })

    @property
    def connection_count(self) -> int:
        return len(self._all_connections)

    def get_channel_counts(self) -> Dict[str, int]:
        return {ch: len(sockets) for ch, sockets in self._connections.items()}


# Global WebSocket manager
ws_manager = WebSocketManager()
