"""
Layer 1: Deterministic rule-based validation.

Synchronous, blocking — applied to every agent output with zero latency.
Catches format errors, NaN/null values, range violations, and cross-field
inconsistencies. These checks are deterministic and free.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FinancialValidationRule:
    """A single validation rule with field name and valid range."""
    field_name: str
    min_value: float
    max_value: float
    required: bool = True
    description: str = ""

    def validate(self, value: Any) -> Tuple[bool, str]:
        if value is None:
            if self.required:
                return False, f"{self.field_name}: required field is None"
            return True, ""

        try:
            num = float(value)
        except (TypeError, ValueError):
            return False, f"{self.field_name}: cannot convert '{value}' to float"

        if math.isnan(num) or math.isinf(num):
            return False, f"{self.field_name}: value is NaN or Inf"

        if num < self.min_value or num > self.max_value:
            return False, (
                f"{self.field_name}: {num} out of range "
                f"[{self.min_value}, {self.max_value}]"
            )

        return True, ""


@dataclass
class CrossFieldRule:
    """A rule that validates relationships between fields."""
    name: str
    fields: List[str]
    validator: Callable[[Dict[str, Any]], Tuple[bool, str]]
    description: str = ""


@dataclass
class ValidationResult:
    """Result of Layer 1 validation."""
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checked_fields: int = 0
    failed_fields: int = 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


# ---------------------------------------------------------------------------
# Standard financial validation rules
# ---------------------------------------------------------------------------

STANDARD_RULES: List[FinancialValidationRule] = [
    FinancialValidationRule("price", 0.0001, 1_000_000, description="Asset price"),
    FinancialValidationRule("rsi", 0, 100, description="Relative Strength Index"),
    FinancialValidationRule("macd_signal", -1000, 1000, required=False, description="MACD signal"),
    FinancialValidationRule("volume", 0, 1e15, description="Trading volume"),
    FinancialValidationRule("confidence", 0.0, 1.0, description="Confidence score"),
    FinancialValidationRule("severity_score", 0, 100, required=False, description="Severity"),
    FinancialValidationRule("daily_return_pct", -50, 50, required=False, description="Daily return %"),
    FinancialValidationRule("bid_ask_spread_pct", 0, 20, required=False, description="Bid-ask spread %"),
    FinancialValidationRule("market_cap", 0, 1e14, required=False, description="Market cap"),
    FinancialValidationRule("pe_ratio", -1000, 10000, required=False, description="P/E ratio"),
    FinancialValidationRule("dividend_yield", 0, 100, required=False, description="Dividend yield %"),
    FinancialValidationRule("beta", -10, 10, required=False, description="Beta"),
    FinancialValidationRule("sharpe_ratio", -10, 20, required=False, description="Sharpe ratio"),
    FinancialValidationRule("max_drawdown", -1, 0, required=False, description="Max drawdown"),
    FinancialValidationRule("altman_z_score", -10, 30, required=False, description="Altman Z-score"),
    FinancialValidationRule("dv01", -10000, 10000, required=False, description="Dollar duration"),
    FinancialValidationRule("oas", 0, 50000, required=False, description="Option-adj spread bps"),
    FinancialValidationRule("ltv_ratio", 0, 2.0, required=False, description="Loan-to-value"),
    FinancialValidationRule("cap_rate", 0, 50, required=False, description="Capitalization rate %"),
    FinancialValidationRule("recovery_rate", 0, 1.0, required=False, description="Expected recovery"),
    FinancialValidationRule("prob_default", 0, 1.0, required=False, description="Probability of default"),
]

# Cross-field consistency rules
CROSS_FIELD_RULES: List[CrossFieldRule] = [
    CrossFieldRule(
        name="bid_lt_ask",
        fields=["bid", "ask"],
        validator=lambda d: (
            (True, "") if d.get("bid") is None or d.get("ask") is None
            else (d["bid"] < d["ask"], f"bid ({d['bid']}) >= ask ({d['ask']})")
        ),
        description="Bid must be less than ask",
    ),
    CrossFieldRule(
        name="open_between_high_low",
        fields=["open", "high", "low"],
        validator=lambda d: (
            (True, "")
            if any(d.get(f) is None for f in ["open", "high", "low"])
            else (
                d["low"] <= d["open"] <= d["high"],
                f"open ({d['open']}) not between low ({d['low']}) and high ({d['high']})",
            )
        ),
        description="Open price between high and low",
    ),
    CrossFieldRule(
        name="close_between_high_low",
        fields=["close", "high", "low"],
        validator=lambda d: (
            (True, "")
            if any(d.get(f) is None for f in ["close", "high", "low"])
            else (
                d["low"] <= d["close"] <= d["high"],
                f"close ({d['close']}) not between low ({d['low']}) and high ({d['high']})",
            )
        ),
        description="Close price between high and low",
    ),
    CrossFieldRule(
        name="high_gte_low",
        fields=["high", "low"],
        validator=lambda d: (
            (True, "")
            if d.get("high") is None or d.get("low") is None
            else (d["high"] >= d["low"], f"high ({d['high']}) < low ({d['low']})")
        ),
        description="High must be >= low",
    ),
]


class RuleValidator:
    """
    Layer 1 validator: deterministic, blocking checks on agent output.

    Validates individual field ranges and cross-field consistency.
    Includes data staleness detection.
    """

    def __init__(
        self,
        rules: Optional[List[FinancialValidationRule]] = None,
        cross_rules: Optional[List[CrossFieldRule]] = None,
        staleness_threshold_seconds: float = 300.0,
    ):
        self.rules = {r.field_name: r for r in (rules or STANDARD_RULES)}
        self.cross_rules = cross_rules or CROSS_FIELD_RULES
        self.staleness_threshold = staleness_threshold_seconds

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate a single agent output dictionary."""
        result = ValidationResult(passed=True)

        # 1. Check for completely empty output
        if not data:
            result.add_error("Empty output dictionary")
            return result

        # 2. Field-level validation
        for field_name, rule in self.rules.items():
            if field_name in data:
                result.checked_fields += 1
                passed, msg = rule.validate(data[field_name])
                if not passed:
                    result.failed_fields += 1
                    result.add_error(msg)
            elif rule.required and field_name in data:
                result.add_error(f"{field_name}: required field missing")

        # 3. Cross-field validation
        for cross_rule in self.cross_rules:
            if all(f in data for f in cross_rule.fields):
                passed, msg = cross_rule.validator(data)
                if not passed:
                    result.add_error(f"Cross-field[{cross_rule.name}]: {msg}")

        # 4. Staleness check
        timestamp = data.get("timestamp")
        if timestamp:
            self._check_staleness(timestamp, result)

        # 5. Check for NaN/None in any numeric field
        for key, value in data.items():
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                result.add_error(f"{key}: contains NaN or Inf")

        return result

    def _check_staleness(self, timestamp: Any, result: ValidationResult) -> None:
        """Check if data timestamp indicates staleness."""
        try:
            if isinstance(timestamp, str):
                ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            elif isinstance(timestamp, (int, float)):
                ts = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            elif isinstance(timestamp, datetime):
                ts = timestamp
            else:
                result.add_warning(f"Cannot parse timestamp type: {type(timestamp)}")
                return

            now = datetime.now(timezone.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (now - ts).total_seconds()

            if age > self.staleness_threshold:
                result.add_warning(
                    f"Data is {age:.0f}s old (threshold: {self.staleness_threshold}s)"
                )
        except Exception as e:
            result.add_warning(f"Could not check staleness: {e}")

    def validate_batch(self, outputs: List[Dict[str, Any]]) -> List[ValidationResult]:
        """Validate a batch of agent outputs."""
        return [self.validate(output) for output in outputs]

    def add_rule(self, rule: FinancialValidationRule) -> None:
        self.rules[rule.field_name] = rule

    def add_cross_rule(self, rule: CrossFieldRule) -> None:
        self.cross_rules.append(rule)
