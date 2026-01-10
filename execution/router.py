from meta_supervisor.policy.mode import is_shadow

def route_signal(signal: dict) -> dict:
    if is_shadow():
        return {"status": "shadow", "routed": False, "reason": "TRADING_MODE=shadow", "signal": signal}

    return {"status": "live", "routed": True, "signal": signal}
