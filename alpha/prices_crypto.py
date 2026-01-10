import requests
from datetime import datetime, timezone

BINANCE_BASE = "https://api.binance.com"
COINBASE_BASE = "https://api.exchange.coinbase.com"

def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)

def _parse_iso(ts_iso: str) -> datetime:
    return datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))

def _binance_symbol(sym: str) -> str:
    s = sym.upper().replace("/", "")
    if s.endswith("USDT"):
        return s
    return f"{s}USDT"

def get_binance_close(symbol: str, ts_iso: str, interval: str = "1h") -> float | None:
    dt = _parse_iso(ts_iso)
    sym = _binance_symbol(symbol)

    start = _to_ms(dt) - 2 * 60 * 60 * 1000
    end = _to_ms(dt) + 2 * 60 * 60 * 1000

    try:
        r = requests.get(
            f"{BINANCE_BASE}/api/v3/klines",
            params={"symbol": sym, "interval": interval, "startTime": start, "endTime": end, "limit": 10},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None

        target_ms = _to_ms(dt)
        best = None
        for k in data:
            open_ms = int(k[0])
            close_px = float(k[4])
            if open_ms <= target_ms:
                best = close_px
        if best is None:
            best = float(data[0][4])
        return best
    except Exception:
        return None

def get_coinbase_spot(symbol: str) -> float | None:
    sym = symbol.upper()
    pair = f"{sym}-USD"
    try:
        r = requests.get(f"{COINBASE_BASE}/products/{pair}/ticker", timeout=15)
        if r.status_code != 200:
            return None
        j = r.json()
        return float(j["price"])
    except Exception:
        return None

def get_price(symbol: str, ts_iso: str, horizon_hours: int) -> float | None:
    interval = "1h" if horizon_hours <= 1 else ("4h" if horizon_hours <= 4 else "1d")
    px = get_binance_close(symbol, ts_iso, interval=interval)
    if px is not None:
        return px
    return get_coinbase_spot(symbol)
