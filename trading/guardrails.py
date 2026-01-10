from dataclasses import dataclass
from typing import Dict, Any, Tuple
import time


@dataclass
class GuardrailConfig:
    paper_only: bool = True
    max_order_notional_usd: float = 10_000
    max_daily_loss_usd: float = 500
    min_expected_edge_bps: float = 10.0
    max_spread_bps: float = 15.0
    max_slippage_bps: float = 20.0
    max_staleness_sec: int = 30
    max_error_rate_5m: float = 0.10


class KillSwitch:
    def __init__(self):
        self._enabled = False
        self._reason = ""

    def trip(self, reason: str):
        self._enabled = True
        self._reason = reason

    def clear(self):
        self._enabled = False
        self._reason = ""

    @property
    def enabled(self):
        return self._enabled

    @property
    def reason(self):
        return self._reason


class TradeGuardrails:
    def __init__(self, cfg: GuardrailConfig, kill: KillSwitch):
        self.cfg = cfg
        self.kill = kill
        self.daily_loss_usd = 0.0
        self.day_key = time.strftime("%Y-%m-%d")

    def _roll_day(self):
        k = time.strftime("%Y-%m-%d")
        if k != self.day_key:
            self.day_key = k
            self.daily_loss_usd = 0.0

    def record_pnl(self, pnl_usd: float):
        self._roll_day()
        self.daily_loss_usd += min(0.0, pnl_usd)

    def check(self, signal: Dict[str, Any]) -> Tuple[bool, str]:
        self._roll_day()

        if self.kill.enabled:
            return False, f"KillSwitch enabled: {self.kill.reason}"

        if self.cfg.paper_only and not signal.get("paper", True):
            return False, "Paper-only mode enabled"

        notional = float(signal.get("notional_usd", 0.0))
        if notional > self.cfg.max_order_notional_usd:
            return False, "Order notional exceeds limit"

        if abs(self.daily_loss_usd) > self.cfg.max_daily_loss_usd:
            self.kill.trip("Daily loss limit breached")
            return False, "Daily loss limit breached"

        if float(signal.get("expected_edge_bps", 0.0)) < self.cfg.min_expected_edge_bps:
            return False, "Expected edge below minimum"

        if float(signal.get("spread_bps", 0.0)) > self.cfg.max_spread_bps:
            return False, "Spread too wide"

        if float(signal.get("slippage_bps", 0.0)) > self.cfg.max_slippage_bps:
            return False, "Slippage too high"

        if int(signal.get("data_age_sec", 10**9)) > self.cfg.max_staleness_sec:
            return False, "Signal data too stale"

        return True, "OK"
