import os

def trading_mode() -> str:
    return (os.environ.get("TRADING_MODE") or "shadow").lower()

def is_shadow() -> bool:
    return trading_mode() != "live"
