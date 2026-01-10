"""
DistressedPropertyAgent
=======================
Identifies high-signal distressed real estate opportunities.
Fetches from configured APIs, scores properties, and emits actionable signals.

Analysis-only. Sandbox-editable. Non-execution-sensitive.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)


class DistressedPropertyAgent:
    """
    Agent that analyzes distressed property data for investment signals.
    
    Signal Types:
    - deep_discount: Property priced >20% below estimated value
    - auction_imminent: Auction within 7 days
    - price_drop: Recent price reduction >10%
    - high_yield: Estimated rental yield >12%
    """

    # Configurable thresholds (can be tuned by Meta-Agent)
    DEEP_DISCOUNT_THRESHOLD = 0.20      # 20% below value
    AUCTION_IMMINENT_DAYS = 7           # days until auction
    PRICE_DROP_THRESHOLD = 0.10         # 10% price reduction
    HIGH_YIELD_THRESHOLD = 0.12         # 12% rental yield
    MIN_SIGNAL_STRENGTH = 50            # minimum score to emit

    def __init__(self):
        self.api_endpoints = self._load_endpoints()
        self.timeout = int(os.getenv("PROPERTY_API_TIMEOUT", "30"))

    def _load_endpoints(self) -> List[Dict[str, Any]]:
        """Load API endpoints from environment."""
        endpoints = []
        i = 1
        while True:
            url = os.getenv(f"PROPERTY_API_{i}_URL")
            if not url:
                break
            endpoints.append({
                "name": os.getenv(f"PROPERTY_API_{i}_NAME", f"PropertyAPI_{i}"),
                "url": url,
                "key": os.getenv(f"PROPERTY_API_{i}_KEY"),
                "response_key": os.getenv(f"PROPERTY_API_{i}_RESPONSE_KEY", "properties"),
            })
            i += 1
        return endpoints

    def analyze(self) -> List[Dict[str, Any]]:
        """
        Main entry point. Fetches properties and returns scored signals.
        
        Returns:
            List of signal dicts matching canonical output shape.
        """
        signals = []
        
        # If APIs configured, fetch from them
        if self.api_endpoints:
            for endpoint in self.api_endpoints:
                try:
                    properties = self._fetch_from_endpoint(endpoint)
                    for prop in properties:
                        signal = self._score_property(prop, endpoint["name"])
                        if signal and signal["signal_strength"] >= self.MIN_SIGNAL_STRENGTH:
                            signals.append(signal)
                except Exception as e:
                    logger.error(f"[DistressedPropertyAgent] {endpoint['name']} failed: {e}")
                    continue
        else:
            # Use sample data for demo/testing
            for prop in self._get_sample_properties():
                signal = self._score_property(prop, "sample")
                if signal and signal["signal_strength"] >= self.MIN_SIGNAL_STRENGTH:
                    signals.append(signal)

        # Sort by signal strength descending
        signals.sort(key=lambda x: x["signal_strength"], reverse=True)
        
        logger.info(f"[DistressedPropertyAgent] Emitting {len(signals)} signals")
        return signals

    def _fetch_from_endpoint(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch properties from a single API endpoint."""
        headers = {}
        if endpoint.get("key"):
            headers["Authorization"] = f"Bearer {endpoint['key']}"

        response = requests.get(
            endpoint["url"],
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Handle nested response keys (e.g., "data.properties")
        result = data
        for key in endpoint["response_key"].split("."):
            result = result.get(key, [])
        
        return result if isinstance(result, list) else []

    def _score_property(self, prop: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
        """
        Score a property and determine signal type.
        
        Returns:
            Signal dict if property meets threshold, None otherwise.
        """
        # Normalize field names (APIs vary)
        price = self._extract_float(prop, ["price", "list_price", "asking_price"])
        estimated_value = self._extract_float(prop, ["estimated_value", "zestimate", "avm", "market_value"])
        
        if not price or price <= 0:
            return None

        # Calculate metrics
        discount_pct = 0.0
        if estimated_value and estimated_value > 0:
            discount_pct = (estimated_value - price) / estimated_value

        days_to_auction = self._extract_int(prop, ["days_to_auction", "auction_days"])
        price_change_pct = self._extract_float(prop, ["price_change_pct", "price_reduction"])
        rental_yield = self._extract_float(prop, ["rental_yield", "cap_rate", "yield"])

        # Determine signal type and strength
        signal_type, signal_strength = self._classify_signal(
            discount_pct=discount_pct,
            days_to_auction=days_to_auction,
            price_change_pct=price_change_pct,
            rental_yield=rental_yield
        )

        if not signal_type:
            return None

        return {
            "property_id": str(prop.get("id", prop.get("property_id", f"prop-{hash(str(prop)) % 100000}"))),
            "address": self._extract_str(prop, ["address", "street_address", "street"]),
            "city": self._extract_str(prop, ["city", "property_city"]),
            "state": self._extract_str(prop, ["state", "state_code"]),
            "signal_type": signal_type,
            "signal_strength": round(signal_strength, 1),
            "price": price,
            "estimated_value": estimated_value or price,
            "discount_pct": round(discount_pct * 100, 1),
            "property_type": self._extract_str(prop, ["property_type", "type", "home_type"]) or "unknown",
            "status": self._extract_str(prop, ["status", "foreclosure_status"]) or "unknown",
            "days_on_market": self._extract_int(prop, ["days_on_market", "dom"]) or 0,
            "source": source,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    def _classify_signal(
        self,
        discount_pct: float,
        days_to_auction: Optional[int],
        price_change_pct: Optional[float],
        rental_yield: Optional[float]
    ) -> tuple:
        """
        Classify signal type and calculate strength.
        
        Returns:
            (signal_type, signal_strength) or (None, 0) if no signal.
        """
        signals = []

        # Deep discount signal
        if discount_pct >= self.DEEP_DISCOUNT_THRESHOLD:
            strength = min(100, 50 + (discount_pct - self.DEEP_DISCOUNT_THRESHOLD) * 200)
            signals.append(("deep_discount", strength))

        # Auction imminent signal
        if days_to_auction is not None and 0 < days_to_auction <= self.AUCTION_IMMINENT_DAYS:
            strength = min(100, 100 - (days_to_auction * 7))
            signals.append(("auction_imminent", strength))

        # Price drop signal
        if price_change_pct and abs(price_change_pct) >= self.PRICE_DROP_THRESHOLD:
            strength = min(100, 50 + abs(price_change_pct) * 300)
            signals.append(("price_drop", strength))

        # High yield signal
        if rental_yield and rental_yield >= self.HIGH_YIELD_THRESHOLD:
            strength = min(100, 50 + (rental_yield - self.HIGH_YIELD_THRESHOLD) * 500)
            signals.append(("high_yield", strength))

        if not signals:
            return None, 0

        # Return strongest signal
        return max(signals, key=lambda x: x[1])

    def _extract_float(self, data: Dict, keys: List[str]) -> Optional[float]:
        for key in keys:
            if key in data and data[key] is not None:
                try:
                    return float(data[key])
                except (ValueError, TypeError):
                    continue
        return None

    def _extract_int(self, data: Dict, keys: List[str]) -> Optional[int]:
        for key in keys:
            if key in data and data[key] is not None:
                try:
                    return int(data[key])
                except (ValueError, TypeError):
                    continue
        return None

    def _extract_str(self, data: Dict, keys: List[str]) -> Optional[str]:
        for key in keys:
            if key in data and data[key]:
                return str(data[key])
        return None

    def _get_sample_properties(self) -> List[Dict[str, Any]]:
        """Sample properties for testing/demo."""
        return [
            {
                "id": "prop-001",
                "address": "123 Foreclosure Lane",
                "city": "Phoenix",
                "state": "AZ",
                "property_type": "Single Family",
                "status": "foreclosure",
                "price": 185000,
                "estimated_value": 250000,
                "days_on_market": 45,
                "days_to_auction": 5
            },
            {
                "id": "prop-002",
                "address": "456 Auction Drive",
                "city": "Las Vegas",
                "state": "NV",
                "property_type": "Condo",
                "status": "auction",
                "price": 125000,
                "estimated_value": 160000,
                "days_on_market": 30,
                "days_to_auction": 3
            },
            {
                "id": "prop-003",
                "address": "789 Pre-Foreclosure Blvd",
                "city": "Denver",
                "state": "CO",
                "property_type": "Townhouse",
                "status": "pre-foreclosure",
                "price": 320000,
                "estimated_value": 380000,
                "days_on_market": 90,
                "price_change_pct": 0.15
            },
            {
                "id": "prop-004",
                "address": "321 Bank Owned Street",
                "city": "Phoenix",
                "state": "AZ",
                "property_type": "Single Family",
                "status": "bank-owned",
                "price": 225000,
                "estimated_value": 290000,
                "days_on_market": 60
            },
            {
                "id": "prop-005",
                "address": "555 Short Sale Avenue",
                "city": "San Diego",
                "state": "CA",
                "property_type": "Single Family",
                "status": "short-sale",
                "price": 450000,
                "estimated_value": 580000,
                "days_on_market": 120,
                "rental_yield": 0.14
            }
        ]
