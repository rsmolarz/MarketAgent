"""
Circuit breaker infrastructure for agent failure isolation.

Wraps each agent in an individual circuit breaker with configurable failure
thresholds and reset timeouts. Provides exponential backoff retry and
degraded mode operation when agents fail.

Pattern: Each agent gets its own CircuitBreaker instance. When an agent fails
`fail_max` consecutive times, the breaker opens and prevents further calls
until a `reset_timeout` window passes. This prevents cascade failures and
allows the system to operate in degraded mode.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BreakerState(str, enum.Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerStats:
    """Tracks circuit breaker statistics for observability."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)


class CircuitBreaker:
    """
    Async-native circuit breaker for individual agent protection.

    States:
    - CLOSED: Normal operation. Failures increment counter.
    - OPEN: Too many failures. All calls rejected until reset_timeout.
    - HALF_OPEN: After reset_timeout, allow one test call. Success -> CLOSED, Fail -> OPEN.
    """

    def __init__(
        self,
        name: str,
        fail_max: int = 3,
        reset_timeout: float = 60.0,
        call_timeout: float = 30.0,
    ):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.call_timeout = call_timeout
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> BreakerState:
        if self._state == BreakerState.OPEN:
            if (
                self._last_failure_time is not None
                and time.monotonic() - self._last_failure_time >= self.reset_timeout
            ):
                return BreakerState.HALF_OPEN
        return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        return self._stats

    def _transition_to(self, new_state: BreakerState) -> None:
        old_state = self._state
        self._state = new_state
        self._stats.state_transitions.append({
            "from": old_state.value,
            "to": new_state.value,
            "time": time.monotonic(),
        })
        logger.info(f"CircuitBreaker[{self.name}]: {old_state.value} -> {new_state.value}")

    def _record_success(self) -> None:
        self._failure_count = 0
        self._stats.successful_calls += 1
        self._stats.consecutive_failures = 0
        self._stats.last_success_time = time.monotonic()
        if self._state != BreakerState.CLOSED:
            self._transition_to(BreakerState.CLOSED)

    def _record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        self._stats.failed_calls += 1
        self._stats.consecutive_failures += 1
        self._stats.last_failure_time = time.monotonic()
        if self._failure_count >= self.fail_max:
            self._transition_to(BreakerState.OPEN)

    async def call(self, func: Callable[..., Coroutine], *args: Any, **kwargs: Any) -> Any:
        """
        Execute an async function through the circuit breaker.

        Raises:
            CircuitBreakerOpenError: If the breaker is open.
            asyncio.TimeoutError: If the call exceeds call_timeout.
        """
        async with self._lock:
            current_state = self.state

            if current_state == BreakerState.OPEN:
                self._stats.rejected_calls += 1
                raise CircuitBreakerOpenError(
                    f"CircuitBreaker[{self.name}] is OPEN. "
                    f"Failures: {self._failure_count}/{self.fail_max}. "
                    f"Reset in {self.reset_timeout - (time.monotonic() - (self._last_failure_time or 0)):.1f}s"
                )

            self._stats.total_calls += 1

        try:
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.call_timeout)
            async with self._lock:
                self._record_success()
            return result
        except asyncio.TimeoutError:
            async with self._lock:
                self._record_failure()
            logger.error(f"CircuitBreaker[{self.name}]: Call timed out after {self.call_timeout}s")
            raise
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            async with self._lock:
                self._record_failure()
            logger.error(f"CircuitBreaker[{self.name}]: Call failed: {e}")
            raise


class CircuitBreakerOpenError(Exception):
    """Raised when a call is made to an open circuit breaker."""
    pass


class CircuitBreakerRegistry:
    """
    Registry of circuit breakers, one per agent.
    Provides a centralized view of all breaker states for monitoring.
    """

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        agent_name: str,
        fail_max: int = 3,
        reset_timeout: float = 60.0,
        call_timeout: float = 30.0,
    ) -> CircuitBreaker:
        if agent_name not in self._breakers:
            self._breakers[agent_name] = CircuitBreaker(
                name=agent_name,
                fail_max=fail_max,
                reset_timeout=reset_timeout,
                call_timeout=call_timeout,
            )
        return self._breakers[agent_name]

    def get_all_states(self) -> Dict[str, str]:
        return {name: cb.state.value for name, cb in self._breakers.items()}

    def get_open_breakers(self) -> List[str]:
        return [name for name, cb in self._breakers.items() if cb.state == BreakerState.OPEN]

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        for name, cb in self._breakers.items():
            s = cb.stats
            result[name] = {
                "state": cb.state.value,
                "total_calls": s.total_calls,
                "successful_calls": s.successful_calls,
                "failed_calls": s.failed_calls,
                "rejected_calls": s.rejected_calls,
                "consecutive_failures": s.consecutive_failures,
            }
        return result

    def reset_all(self) -> None:
        for cb in self._breakers.values():
            cb._failure_count = 0
            cb._state = BreakerState.CLOSED


# Global registry
breaker_registry = CircuitBreakerRegistry()


async def with_retry(
    func: Callable[..., Coroutine],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 2.0,
    **kwargs: Any,
) -> Any:
    """
    Execute an async function with exponential backoff retry.

    Delays: base_delay * 2^attempt seconds (2s, 4s, 8s, 16s, ...).
    """
    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except CircuitBreakerOpenError:
            raise  # Don't retry open breakers
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} after {delay}s: {e}"
                )
                await asyncio.sleep(delay)
    raise last_error  # type: ignore[misc]
