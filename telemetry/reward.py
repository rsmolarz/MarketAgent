from typing import Any, Dict
import math

def signal_strength(agent_name: str, output: Any) -> float:
    if output is None:
        return 0.0

    if isinstance(output, list) and output:
        x = output[0]
        if isinstance(x, dict):
            if "profit_pct" in x:
                return max(0.0, min(1.0, float(x["profit_pct"]) / 2.0))
            if "risk_score" in x:
                return max(0.0, min(1.0, float(x["risk_score"]) / 100.0))
            if "signal" in x and "value" in x:
                dc = float(x.get("daily_change", 0.0))
                return max(0.0, min(1.0, abs(dc) / 0.10))
    return 0.1

def reward(event: Dict[str, Any], output: Any) -> float:
    sig = signal_strength(event.get("agent", ""), output)
    cost = float(event.get("cost_usd") or 0.0)
    lat_ms = float(event.get("latency_ms") or 0.0)

    cost_penalty = math.log1p(cost * 200.0)
    lat_penalty = math.log1p(lat_ms / 500.0)

    return sig - 0.25 * cost_penalty - 0.10 * lat_penalty
