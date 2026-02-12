"""
Charles Schwab / Thinkorswim API Client

Provides access to Schwab market data including real-time quotes,
price history, options chains, movers, and market hours.
Implements OAuth 2.0 token management with automatic refresh.
"""

import os
import time
import json
import base64
import logging
import requests
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

TOKEN_FILE = Path("data/schwab_tokens.json")
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.schwabapi.com"
AUTH_URL = f"{BASE_URL}/v1/oauth/authorize"
TOKEN_URL = f"{BASE_URL}/v1/oauth/token"
MARKET_DATA_URL = f"{BASE_URL}/marketdata/v1"


class SchwabClient:
    """
    Client for Charles Schwab / Thinkorswim API.
    Handles OAuth 2.0 authentication and provides market data access.
    """

    def __init__(self):
        self.client_id = os.getenv("SCHWAB_API_KEY", "").strip()
        self.client_secret = os.getenv("SCHWAB_SECRET", "").strip()
        self.redirect_uri = os.getenv(
            "SCHWAB_REDIRECT_URI",
            "https://marketinefficiencyagents.com/oauth/callback/schwab"
        ).strip()
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0
        self._lock = threading.Lock()
        self._load_tokens()

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token and time.time() < self.token_expiry)

    @property
    def has_refresh_token(self) -> bool:
        return bool(self.refresh_token)

    def _auth_header(self) -> str:
        credentials = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(credentials.encode()).decode()

    def get_authorization_url(self, state: str = "") -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
        }
        if state:
            params["state"] = state
        qs = "&".join(f"{k}={requests.utils.quote(v)}" for k, v in params.items())
        return f"{AUTH_URL}?{qs}"

    def exchange_code(self, code: str) -> bool:
        try:
            resp = requests.post(
                TOKEN_URL,
                headers={
                    "Authorization": f"Basic {self._auth_header()}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                timeout=15,
            )
            if resp.ok:
                tokens = resp.json()
                self._set_tokens(tokens)
                logger.info("Schwab: authorization code exchanged successfully")
                return True
            else:
                logger.error(f"Schwab token exchange failed: {resp.status_code} {resp.text[:300]}")
                return False
        except Exception as e:
            logger.error(f"Schwab token exchange error: {e}")
            return False

    def refresh_access_token(self) -> bool:
        if not self.refresh_token:
            logger.warning("Schwab: no refresh token available")
            return False
        try:
            resp = requests.post(
                TOKEN_URL,
                headers={
                    "Authorization": f"Basic {self._auth_header()}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                timeout=15,
            )
            if resp.ok:
                tokens = resp.json()
                self._set_tokens(tokens)
                logger.info("Schwab: access token refreshed successfully")
                return True
            else:
                logger.error(f"Schwab refresh failed: {resp.status_code} {resp.text[:300]}")
                if resp.status_code == 401:
                    logger.warning("Schwab: refresh token expired – re-authorization required")
                return False
        except Exception as e:
            logger.error(f"Schwab refresh error: {e}")
            return False

    def _ensure_token(self) -> bool:
        with self._lock:
            if self.is_authenticated:
                return True
            if self.has_refresh_token:
                return self.refresh_access_token()
            return False

    def ensure_authenticated(self) -> bool:
        return self._ensure_token()

    def _set_tokens(self, tokens: dict):
        self.access_token = tokens.get("access_token")
        self.refresh_token = tokens.get("refresh_token", self.refresh_token)
        expires_in = tokens.get("expires_in", 1800)
        self.token_expiry = time.time() + expires_in - 60
        self._save_tokens()

    def _save_tokens(self):
        try:
            data = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "token_expiry": self.token_expiry,
                "saved_at": datetime.utcnow().isoformat(),
            }
            TOKEN_FILE.write_text(json.dumps(data))
        except Exception as e:
            logger.error(f"Schwab: failed to save tokens: {e}")

    def _load_tokens(self):
        try:
            if TOKEN_FILE.exists():
                data = json.loads(TOKEN_FILE.read_text())
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.token_expiry = data.get("token_expiry", 0)
                if self.access_token:
                    logger.info(f"Schwab: loaded saved tokens (expires {datetime.fromtimestamp(self.token_expiry).isoformat()})")
        except Exception as e:
            logger.error(f"Schwab: failed to load tokens: {e}")

    def _request(self, method: str, url: str, params: dict = None, retries: int = 1) -> Optional[dict]:
        if not self._ensure_token():
            logger.warning("Schwab: not authenticated, skipping request")
            return None

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        for attempt in range(retries + 1):
            try:
                resp = requests.request(method, url, headers=headers, params=params, timeout=15)
                if resp.ok:
                    return resp.json()
                elif resp.status_code == 401 and attempt < retries:
                    logger.info("Schwab: 401 received, refreshing token")
                    if self.refresh_access_token():
                        headers["Authorization"] = f"Bearer {self.access_token}"
                        continue
                    return None
                else:
                    logger.error(f"Schwab API error: {resp.status_code} {resp.text[:200]}")
                    return None
            except requests.exceptions.Timeout:
                logger.warning(f"Schwab API timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Schwab API error: {e}")
                return None
        return None

    def get_quotes(self, symbols: List[str], fields: str = "quote,fundamental") -> Optional[Dict]:
        if not symbols:
            return None
        url = f"{MARKET_DATA_URL}/quotes"
        params = {"symbols": ",".join(symbols), "fields": fields}
        return self._request("GET", url, params)

    def get_quote(self, symbol: str) -> Optional[Dict]:
        result = self.get_quotes([symbol])
        if result and symbol.upper() in result:
            return result[symbol.upper()]
        return result

    def get_price_history(
        self,
        symbol: str,
        period_type: str = "day",
        period: int = 10,
        frequency_type: str = "minute",
        frequency: int = 1,
        start_date: int = None,
        end_date: int = None,
    ) -> Optional[Dict]:
        url = f"{MARKET_DATA_URL}/pricehistory"
        params = {
            "symbol": symbol,
            "periodType": period_type,
            "period": period,
            "frequencyType": frequency_type,
            "frequency": frequency,
        }
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        return self._request("GET", url, params)

    def get_daily_history(self, symbol: str, days: int = 365) -> Optional[Dict]:
        return self.get_price_history(
            symbol=symbol,
            period_type="year" if days > 250 else "month" if days > 20 else "day",
            period=max(1, days // 250) if days > 250 else max(1, days // 20) if days > 20 else max(1, days),
            frequency_type="daily",
            frequency=1,
        )

    def get_option_chain(
        self,
        symbol: str,
        contract_type: str = "ALL",
        strike_count: int = 20,
        include_underlying_quote: bool = True,
        strategy: str = "SINGLE",
        exp_month: str = None,
    ) -> Optional[Dict]:
        url = f"{MARKET_DATA_URL}/chains"
        params = {
            "symbol": symbol,
            "contractType": contract_type,
            "strikeCount": strike_count,
            "includeUnderlyingQuote": str(include_underlying_quote).lower(),
            "strategy": strategy,
        }
        if exp_month:
            params["expMonth"] = exp_month
        return self._request("GET", url, params)

    def get_movers(self, index: str = "$SPX", sort: str = "PERCENT_CHANGE_UP", frequency: int = 0) -> Optional[Dict]:
        url = f"{MARKET_DATA_URL}/movers/{index}"
        params = {"sort": sort, "frequency": frequency}
        return self._request("GET", url, params)

    def get_market_hours(self, markets: str = "equity,option") -> Optional[Dict]:
        url = f"{MARKET_DATA_URL}/markets"
        params = {"markets": markets}
        return self._request("GET", url, params)

    def search_instruments(self, symbol: str, projection: str = "symbol-search") -> Optional[Dict]:
        url = f"{MARKET_DATA_URL}/instruments"
        params = {"symbol": symbol, "projection": projection}
        return self._request("GET", url, params)

    def get_current_price(self, symbol: str) -> Optional[float]:
        quote = self.get_quote(symbol)
        if not quote:
            return None
        q = quote.get("quote", quote)
        return q.get("lastPrice") or q.get("mark") or q.get("closePrice")

    def get_batch_prices(self, symbols: List[str]) -> Dict[str, float]:
        result = {}
        if not symbols:
            return result
        batch_size = 50
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            quotes = self.get_quotes(batch, fields="quote")
            if quotes:
                for sym, data in quotes.items():
                    q = data.get("quote", data)
                    price = q.get("lastPrice") or q.get("mark") or q.get("closePrice")
                    if price:
                        result[sym] = float(price)
        return result

    def get_option_implied_volatility(self, symbol: str) -> Optional[float]:
        chain = self.get_option_chain(symbol, strike_count=5)
        if not chain:
            return None
        underlying = chain.get("underlyingPrice") or chain.get("underlying", {}).get("last")
        call_map = chain.get("callExpDateMap", {})
        ivs = []
        for exp_date, strikes in call_map.items():
            for strike, contracts in strikes.items():
                for contract in contracts:
                    iv = contract.get("volatility")
                    if iv and iv > 0:
                        ivs.append(iv)
        if ivs:
            return sum(ivs) / len(ivs)
        return None

    def get_top_movers_up(self, index: str = "$SPX") -> Optional[List[Dict]]:
        data = self.get_movers(index, sort="PERCENT_CHANGE_UP")
        if data:
            return data.get("screeners", data.get("movers", []))
        return None

    def get_top_movers_down(self, index: str = "$SPX") -> Optional[List[Dict]]:
        data = self.get_movers(index, sort="PERCENT_CHANGE_DOWN")
        if data:
            return data.get("screeners", data.get("movers", []))
        return None

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured,
            "authenticated": self.is_authenticated,
            "has_refresh_token": self.has_refresh_token,
            "client_id_set": bool(self.client_id),
            "secret_set": bool(self.client_secret),
            "token_expiry": datetime.fromtimestamp(self.token_expiry).isoformat() if self.token_expiry else None,
        }


_client_instance = None
_client_lock = threading.Lock()


def get_schwab_client() -> SchwabClient:
    global _client_instance
    with _client_lock:
        if _client_instance is None:
            _client_instance = SchwabClient()
        return _client_instance
