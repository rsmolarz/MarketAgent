import uuid
import time
from telemetry.collector import RunTelemetry
from telemetry.context import set_current_run
from telemetry.logger import log_event, new_run_id
from telemetry.reward import reward as compute_reward
from telemetry.metrics import (
    AGENT_RUNS, AGENT_ERRORS, AGENT_LATENCY_MS,
    AGENT_COST_USD, AGENT_REWARD,
    AGENT_LAST_REWARD, AGENT_LAST_COST_USD, AGENT_LAST_LATENCY_MS
)


def run_with_telemetry(agent_name: str, fn, *args, capital_context=None, **kwargs):
    run = RunTelemetry(agent=agent_name, run_id=str(uuid.uuid4()))
    set_current_run(run)
    
    run_id = new_run_id()
    t0 = time.time()
    error = None
    output = None
    cost_usd = None
    
    try:
        output = fn(*args, **kwargs)
        return output
    except Exception as e:
        run.add_error()
        error = str(e)
        raise
    finally:
        lat_ms = int((time.time() - t0) * 1000)
        
        if capital_context:
            from telemetry.capital_reward import capital_weighted_reward
            reward = capital_weighted_reward(
                agent=agent_name,
                output=output,
                capital_usd=capital_context.get("capital_usd", 25000),
                max_loss_usd=capital_context.get("max_loss_usd", 300),
                fill_prob=capital_context.get("fill_prob", 0.7),
            )
        else:
            event = {"agent": agent_name, "latency_ms": lat_ms, "cost_usd": cost_usd}
            reward = compute_reward(event, output)
        
        log_event(
            agent=agent_name,
            run_id=run_id,
            latency_ms=lat_ms,
            cost_usd=cost_usd,
            error=error,
            reward=reward,
        )
        
        AGENT_RUNS.labels(agent_name).inc()
        AGENT_LATENCY_MS.labels(agent_name).observe(lat_ms)
        AGENT_LAST_LATENCY_MS.labels(agent_name).set(lat_ms)
        
        if error:
            AGENT_ERRORS.labels(agent_name).inc()
        
        if cost_usd is not None:
            AGENT_COST_USD.labels(agent_name).observe(float(cost_usd))
            AGENT_LAST_COST_USD.labels(agent_name).set(float(cost_usd))
        
        AGENT_REWARD.labels(agent_name).observe(float(reward))
        AGENT_LAST_REWARD.labels(agent_name).set(float(reward))
        
        run.flush()
        set_current_run(None)
