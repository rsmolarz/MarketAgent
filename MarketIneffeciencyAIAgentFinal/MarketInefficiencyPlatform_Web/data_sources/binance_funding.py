
import requests

def get_btc_perp_funding():
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT")
        if r.status_code == 200:
            return float(r.json()["fundingRate"]) * 100  # Convert to %
        return 0.0
    except Exception as e:
        print("[BinanceFunding] Error:", e)
        return 0.0
