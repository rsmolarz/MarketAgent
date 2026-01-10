"""
Capital Allocator

Converts agent weights + signals into portfolio position sizing.
Designed to work for:
- Live trading
- Backtesting
- Meta-agent control

Inputs:
- agent_schedule.json
- agent findings (from DB or in-memory)
Outputs:
- portfolio_targets.json
"""

import json
import logging
from collections import defaultdict
from typing import Dict, List, Any
from datetime import datetime

from portfolio.agent_decay import AgentDecayModel

logger = logging.getLogger(__name__)


class CapitalAllocator:
    def __init__(
        self,
        schedule_path: str = "agent_schedule.json",
        max_agent_weight: float = 0.25,
        max_symbol_weight: float = 0.20,
        cash_buffer: float = 0.10
    ):
        self.schedule_path = schedule_path
        self.max_agent_weight = max_agent_weight
        self.max_symbol_weight = max_symbol_weight
        self.cash_buffer = cash_buffer

        self.agent_config = self._load_schedule()
        self.decay_model = AgentDecayModel()

    def _load_schedule(self) -> Dict[str, Any]:
        with open(self.schedule_path, "r") as f:
            return json.load(f)

    def allocate(
        self,
        findings: List[Dict[str, Any]],
        portfolio_value: float = 1.0
    ) -> Dict[str, Any]:
        """
        Main allocation entrypoint.

        Returns normalized portfolio targets.
        """
        raw_allocations = defaultdict(float)
        agent_contributions = defaultdict(float)

        for f in findings:
            agent = f.get("agent") or f.get("agent_name")
            symbol = f.get("symbol")
            severity = f.get("severity", "low")
            confidence = float(f.get("confidence", 0.5))

            if not agent or not symbol:
                continue

            cfg = self.agent_config.get(agent)
            if not cfg or not cfg.get("enabled", False):
                continue

            base_weight = min(cfg.get("weight", 0), self.max_agent_weight)
            score = cfg.get("score", 0.0)
            days = cfg.get("days_since_eval", 30)
            
            decay = self.decay_model.decay_factor(score, days)
            agent_weight = base_weight * decay
            
            severity_mult = self._severity_multiplier(severity)

            capital = agent_weight * confidence * severity_mult

            raw_allocations[symbol] += capital
            agent_contributions[agent] += capital

        total_risk = sum(raw_allocations.values())
        if total_risk == 0:
            return self._empty_portfolio(portfolio_value)

        normalized = {}
        for symbol, w in raw_allocations.items():
            norm = w / total_risk
            capped = min(norm, self.max_symbol_weight)
            normalized[symbol] = capped

        used = sum(normalized.values())
        cash = max(self.cash_buffer, 1.0 - used)

        scale = (1.0 - cash) / max(sum(normalized.values()), 1e-9)
        for symbol in normalized:
            normalized[symbol] *= scale * portfolio_value

        from meta.uncertainty_decay import uncertainty_multiplier, get_decay_status
        unc_mult = uncertainty_multiplier(datetime.utcnow())
        decay_status = get_decay_status(datetime.utcnow())
        
        for symbol in normalized:
            normalized[symbol] *= unc_mult

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "portfolio_value": portfolio_value,
            "targets": normalized,
            "cash": cash * portfolio_value,
            "agent_contributions": dict(agent_contributions),
            "uncertainty_multiplier": unc_mult,
            "uncertainty_decay": decay_status,
        }

    def _severity_multiplier(self, severity: str) -> float:
        return {
            "low": 0.5,
            "medium": 1.0,
            "high": 1.5,
            "critical": 2.0,
        }.get(severity, 1.0)

    def _empty_portfolio(self, portfolio_value: float = 1.0):
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "portfolio_value": portfolio_value,
            "targets": {},
            "cash": portfolio_value,
            "agent_contributions": {},
        }


def write_portfolio_targets(result: Dict, path: str = "portfolio_targets.json"):
    """Save portfolio targets to JSON file."""
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Portfolio targets written to {path}")


def run_allocation(portfolio_value: float = 1_000_000, limit: int = 500) -> Dict:
    """
    Run allocation from live database findings with regime rotation.
    
    Usage:
        from portfolio.capital_allocator import run_allocation
        portfolio = run_allocation(portfolio_value=1_000_000)
    """
    from models import Finding
    from meta.regime_rotation import apply_regime_rotation
    
    allocator = CapitalAllocator()
    
    findings = [
        {
            "agent": f.agent_name,
            "symbol": f.symbol,
            "severity": f.severity,
            "confidence": float(f.confidence or 0.5),
        }
        for f in Finding.query.order_by(Finding.timestamp.desc()).limit(limit).all()
    ]
    
    portfolio = allocator.allocate(findings, portfolio_value=portfolio_value)
    
    regime_state = get_regime_state()
    if regime_state and "active_regime" in regime_state:
        rotated_contrib = apply_regime_rotation(
            portfolio.get("agent_contributions", {}),
            regime_state["active_regime"],
            regime_state.get("confidence", 0.5)
        )
        portfolio["agent_contributions_rotated"] = rotated_contrib
        portfolio["regime"] = regime_state["active_regime"]
        portfolio["regime_confidence"] = regime_state.get("confidence", 0.5)
    
    write_portfolio_targets(portfolio)
    
    return portfolio


def get_regime_state() -> Dict:
    """Get current regime state from API or cache."""
    try:
        from regime import extract_features, score_regimes, regime_confidence
        from regime.confidence import get_cached_regime, cache_regime
        from data_sources.price_loader import load_spy
        import yfinance as yf
        
        spy = load_spy(start="2020-01-01", use_cache=True)
        
        try:
            vix = yf.download("^VIX", period="3mo", progress=False)
        except Exception:
            vix = spy.copy()
            vix["Close"] = 20.0
        
        try:
            tnx = yf.download("^TNX", period="3mo", progress=False)
        except Exception:
            tnx = spy.copy()
            tnx["Close"] = 4.0
        
        try:
            gld = yf.download("GLD", period="3mo", progress=False)
        except Exception:
            gld = None
        
        if len(spy) < 20 or len(vix) < 20 or len(tnx) < 20:
            return {}
        
        features = extract_features(spy, vix, tnx, gld)
        scores = score_regimes(features)
        
        state = regime_confidence(
            features,
            scores,
            prev_regime=get_cached_regime()
        )
        
        cache_regime(state["active_regime"])
        return state
        
    except Exception as e:
        logger.error(f"Error getting regime state: {e}")
        return {}
