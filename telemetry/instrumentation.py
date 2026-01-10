import time
from typing import Callable, Any

from telemetry.logger import log_event, new_run_id
from telemetry.reward import reward as compute_reward
from telemetry.metrics import (
    AGENT_RUNS, AGENT_ERRORS, AGENT_LATENCY_MS, AGENT_COST_USD, AGENT_REWARD,
    AGENT_LAST_REWARD, AGENT_LAST_COST_USD, AGENT_LAST_LATENCY_MS
)


def instrument_agent_call(agent_name: str, fn: Callable[[], Any], cost_usd: float = None) -> Any:
    run_id = new_run_id()
    t0 = time.time()
    error = None
    output = None

    try:
        output = fn()
    except Exception as e:
        error = str(e)
        raise
    finally:
        lat_ms = int((time.time() - t0) * 1000)

        event = {
            "agent": agent_name,
            "latency_ms": lat_ms,
            "cost_usd": cost_usd,
        }
        r = compute_reward(event, output)

        log_event(
            agent=agent_name,
            run_id=run_id,
            latency_ms=lat_ms,
            cost_usd=cost_usd,
            error=error,
            reward=r,
        )

        AGENT_RUNS.labels(agent_name).inc()
        if error:
            AGENT_ERRORS.labels(agent_name).inc()

        AGENT_LATENCY_MS.labels(agent_name).observe(lat_ms)
        AGENT_LAST_LATENCY_MS.labels(agent_name).set(lat_ms)

        if cost_usd is not None:
            AGENT_COST_USD.labels(agent_name).observe(float(cost_usd))
            AGENT_LAST_COST_USD.labels(agent_name).set(float(cost_usd))

        AGENT_REWARD.labels(agent_name).observe(float(r))
        AGENT_LAST_REWARD.labels(agent_name).set(float(r))

    return output
