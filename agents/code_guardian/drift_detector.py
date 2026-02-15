"""
Layer 3: Statistical drift detection.

Batch, periodic — performs statistical drift detection across all agent
outputs, tracking rolling distributions of conviction scores, response
times, and error rates per agent. When an agent's output distribution
shifts significantly, raises a system-level alert.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DriftAlert:
    """Alert raised when statistical drift is detected."""
    agent_name: str
    metric_name: str
    drift_type: str  # "mean_shift", "variance_change", "error_rate_spike"
    baseline_value: float
    current_value: float
    z_score: float
    severity: str  # "low", "medium", "high", "critical"
    description: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentMetricWindow:
    """Rolling window of metric values for one agent."""
    values: Deque[float] = field(default_factory=lambda: deque(maxlen=200))
    timestamps: Deque[float] = field(default_factory=lambda: deque(maxlen=200))

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> float:
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)

    @property
    def std(self) -> float:
        if len(self.values) < 2:
            return 0.0
        m = self.mean
        variance = sum((x - m) ** 2 for x in self.values) / (len(self.values) - 1)
        return math.sqrt(variance)

    def add(self, value: float) -> None:
        self.values.append(value)
        self.timestamps.append(time.time())

    def recent(self, n: int = 20) -> List[float]:
        return list(self.values)[-n:]

    def recent_mean(self, n: int = 20) -> float:
        recent = self.recent(n)
        if not recent:
            return 0.0
        return sum(recent) / len(recent)

    def recent_std(self, n: int = 20) -> float:
        recent = self.recent(n)
        if len(recent) < 2:
            return 0.0
        m = sum(recent) / len(recent)
        variance = sum((x - m) ** 2 for x in recent) / (len(recent) - 1)
        return math.sqrt(variance)


class DriftDetector:
    """
    Monitors rolling distributions of agent metrics and detects drift.

    Tracks per-agent:
    - Conviction scores distribution
    - Response times
    - Error rates
    - Output value ranges

    Uses z-score based detection: if the recent window's mean deviates
    more than `z_threshold` standard deviations from the baseline,
    a drift alert is raised.
    """

    def __init__(
        self,
        window_size: int = 200,
        recent_window: int = 20,
        z_threshold: float = 2.5,
        min_samples: int = 30,
    ):
        self.window_size = window_size
        self.recent_window = recent_window
        self.z_threshold = z_threshold
        self.min_samples = min_samples

        # metrics[agent_name][metric_name] -> AgentMetricWindow
        self._metrics: Dict[str, Dict[str, AgentMetricWindow]] = defaultdict(
            lambda: defaultdict(AgentMetricWindow)
        )
        self._error_counts: Dict[str, Deque[Tuple[float, bool]]] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        self._alerts: List[DriftAlert] = []

    def record(self, agent_name: str, metric_name: str, value: float) -> None:
        """Record a metric observation for an agent."""
        self._metrics[agent_name][metric_name].add(value)

    def record_error(self, agent_name: str, is_error: bool) -> None:
        """Record an error/success for error rate tracking."""
        self._error_counts[agent_name].append((time.time(), is_error))

    def record_output(self, agent_name: str, output: Dict[str, Any]) -> None:
        """Record all trackable metrics from an agent output."""
        # Track conviction/confidence
        for key in ("confidence", "conviction", "score", "severity_score"):
            if key in output and isinstance(output[key], (int, float)):
                self.record(agent_name, key, float(output[key]))

        # Track response time if present
        if "response_time_ms" in output:
            self.record(agent_name, "response_time_ms", float(output["response_time_ms"]))

    def check_drift(self, agent_name: Optional[str] = None) -> List[DriftAlert]:
        """
        Check for drift in all metrics for an agent (or all agents).
        Returns list of new alerts.
        """
        new_alerts = []
        agents = [agent_name] if agent_name else list(self._metrics.keys())

        for name in agents:
            if name not in self._metrics:
                continue

            for metric_name, window in self._metrics[name].items():
                if window.count < self.min_samples:
                    continue

                alert = self._check_metric_drift(name, metric_name, window)
                if alert:
                    new_alerts.append(alert)

            # Check error rate drift
            alert = self._check_error_rate_drift(name)
            if alert:
                new_alerts.append(alert)

        self._alerts.extend(new_alerts)
        return new_alerts

    def _check_metric_drift(
        self, agent_name: str, metric_name: str, window: AgentMetricWindow
    ) -> Optional[DriftAlert]:
        """Check a single metric for distribution shift."""
        baseline_mean = window.mean
        baseline_std = window.std
        recent_mean = window.recent_mean(self.recent_window)

        if baseline_std == 0:
            return None

        z_score = abs(recent_mean - baseline_mean) / baseline_std

        if z_score < self.z_threshold:
            return None

        # Determine severity
        if z_score > 4.0:
            severity = "critical"
        elif z_score > 3.5:
            severity = "high"
        elif z_score > 3.0:
            severity = "medium"
        else:
            severity = "low"

        # Check for variance change
        recent_std = window.recent_std(self.recent_window)
        variance_ratio = recent_std / baseline_std if baseline_std > 0 else 1.0
        drift_type = "mean_shift"
        if variance_ratio > 2.0 or variance_ratio < 0.5:
            drift_type = "variance_change"

        return DriftAlert(
            agent_name=agent_name,
            metric_name=metric_name,
            drift_type=drift_type,
            baseline_value=baseline_mean,
            current_value=recent_mean,
            z_score=z_score,
            severity=severity,
            description=(
                f"{agent_name}.{metric_name}: baseline={baseline_mean:.4f}, "
                f"recent={recent_mean:.4f}, z={z_score:.2f}, "
                f"variance_ratio={variance_ratio:.2f}"
            ),
        )

    def _check_error_rate_drift(self, agent_name: str) -> Optional[DriftAlert]:
        """Check if an agent's error rate has spiked."""
        records = self._error_counts.get(agent_name)
        if not records or len(records) < self.min_samples:
            return None

        all_records = list(records)
        total_errors = sum(1 for _, is_err in all_records if is_err)
        baseline_rate = total_errors / len(all_records)

        recent = all_records[-self.recent_window:]
        recent_errors = sum(1 for _, is_err in recent if is_err)
        recent_rate = recent_errors / len(recent)

        if baseline_rate == 0 and recent_rate == 0:
            return None

        # Use binomial approximation for z-score
        if baseline_rate > 0 and baseline_rate < 1:
            std = math.sqrt(baseline_rate * (1 - baseline_rate) / len(recent))
            if std > 0:
                z_score = (recent_rate - baseline_rate) / std
            else:
                z_score = 0
        else:
            z_score = 0

        if z_score < self.z_threshold:
            return None

        severity = "critical" if recent_rate > 0.5 else "high" if recent_rate > 0.3 else "medium"

        return DriftAlert(
            agent_name=agent_name,
            metric_name="error_rate",
            drift_type="error_rate_spike",
            baseline_value=baseline_rate,
            current_value=recent_rate,
            z_score=z_score,
            severity=severity,
            description=(
                f"{agent_name} error rate: baseline={baseline_rate:.2%}, "
                f"recent={recent_rate:.2%}, z={z_score:.2f}"
            ),
        )

    def get_alerts(self, severity: Optional[str] = None) -> List[DriftAlert]:
        if severity:
            return [a for a in self._alerts if a.severity == severity]
        return list(self._alerts)

    def clear_alerts(self) -> int:
        count = len(self._alerts)
        self._alerts.clear()
        return count

    def get_agent_summary(self, agent_name: str) -> Dict[str, Any]:
        """Get a summary of tracked metrics for an agent."""
        if agent_name not in self._metrics:
            return {"agent_name": agent_name, "metrics": {}}

        summary: Dict[str, Any] = {"agent_name": agent_name, "metrics": {}}
        for metric_name, window in self._metrics[agent_name].items():
            summary["metrics"][metric_name] = {
                "count": window.count,
                "mean": window.mean,
                "std": window.std,
                "recent_mean": window.recent_mean(self.recent_window),
                "recent_std": window.recent_std(self.recent_window),
            }

        # Error rate
        records = self._error_counts.get(agent_name)
        if records:
            all_records = list(records)
            total_errors = sum(1 for _, is_err in all_records if is_err)
            summary["error_rate"] = total_errors / len(all_records) if all_records else 0

        return summary

    def get_all_summaries(self) -> Dict[str, Dict[str, Any]]:
        return {name: self.get_agent_summary(name) for name in self._metrics}
