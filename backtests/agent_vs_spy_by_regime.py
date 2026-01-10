"""
Backtest agent signals vs SPY by regime

Computes hit-rate, mean return, and alpha vs SPY baseline
for each agent and each market regime.
"""
import pandas as pd
from datetime import timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def _build_daily_regime_map(spy_df: pd.DataFrame) -> pd.DataFrame:
    """
    Produces daily regime labels based on existing regime pipeline.
    Returns DataFrame with Date, regime, confidence.
    """
    try:
        from regime.features import extract_features
        from regime.scoring import score_regimes
        from meta.regime import regime_confidence
    except ImportError:
        return pd.DataFrame({"Date": spy_df["Date"], "regime": "unknown", "conf": 0.0})
    
    spy = spy_df.copy()
    spy = spy.sort_values("Date")
    spy = spy.set_index("Date")
    
    out = []
    dates = spy.index
    for i in range(60, len(dates)):
        window = spy.iloc[:i + 1].reset_index()
        try:
            features = extract_features(window, window, window, None)
            scores = score_regimes(features)
            state = regime_confidence(features, scores, prev_regime=None)
            out.append({
                "Date": window["Date"].iloc[-1],
                "regime": state.get("active_regime", "unknown"),
                "conf": float(state.get("confidence", 0.0)),
            })
        except Exception:
            out.append({
                "Date": window["Date"].iloc[-1],
                "regime": "unknown",
                "conf": 0.0,
            })
    return pd.DataFrame(out)


def _spy_forward_return(spy_df: pd.DataFrame, date: pd.Timestamp, lookahead_days: int) -> Optional[float]:
    """Calculate SPY forward return from a given date."""
    spy_df = spy_df.sort_values("Date").reset_index(drop=True)
    matches = spy_df[spy_df["Date"] == date]
    if matches.empty:
        return None
    
    i = matches.index[0]
    j = i + lookahead_days
    if j >= len(spy_df):
        return None
    
    p0 = float(spy_df.loc[i, "Close"])
    p1 = float(spy_df.loc[j, "Close"])
    if p0 <= 0:
        return None
    return (p1 / p0) - 1.0


def backtest_agent_vs_spy_by_regime(
    agent_name: str,
    lookahead_days: int = 1,
    last_n_events: int = 20000,
    spy_start: str = "2020-01-01",
) -> Dict[str, Any]:
    """
    Backtest an agent's signals against SPY by regime.
    
    Args:
        agent_name: Name of the agent to backtest
        lookahead_days: Forward return horizon
        last_n_events: Number of telemetry events to scan
        spy_start: Start date for SPY data
    
    Returns:
        Dict with hit rates, returns, and alpha by regime
    """
    from telemetry.events_store import iter_events
    from data_sources.price_loader import load_spy
    
    try:
        spy = load_spy(start=spy_start, use_cache=True)
    except Exception as e:
        logger.warning(f"Failed to load SPY: {e}")
        return {"ok": False, "error": str(e)}
    
    spy["Date"] = pd.to_datetime(spy["Date"]).dt.normalize()
    
    regime_map = _build_daily_regime_map(spy)
    if regime_map.empty:
        regime_map = pd.DataFrame({"Date": spy["Date"], "regime": "unknown", "conf": 0.0})
    regime_map["Date"] = pd.to_datetime(regime_map["Date"]).dt.normalize()
    
    regime_by_date = dict(zip(regime_map["Date"], regime_map["regime"]))
    
    rows = []
    for e in iter_events(last_n=last_n_events):
        if e.get("agent") != agent_name:
            continue
        dt = e.get("_dt")
        if not dt:
            continue
        d = pd.Timestamp(dt.date())
        regime = regime_by_date.get(d, "unknown")
        
        fwd = _spy_forward_return(spy, d, lookahead_days)
        if fwd is None:
            continue
        
        reward = e.get("reward")
        direction = (e.get("direction") or "").lower().strip()
        
        if reward is not None:
            success = float(reward) > 0
            agent_ret = float(reward)
        elif direction in ("up", "long", "bull"):
            success = fwd > 0
            agent_ret = fwd
        elif direction in ("down", "short", "bear"):
            success = fwd < 0
            agent_ret = -fwd
        else:
            continue
        
        rows.append({
            "date": d,
            "regime": regime,
            "spy_fwd_ret": float(fwd),
            "agent_ret": float(agent_ret),
            "success": int(success),
        })
    
    df = pd.DataFrame(rows)
    if df.empty:
        return {
            "ok": True,
            "agent": agent_name,
            "lookahead_days": lookahead_days,
            "rows": 0,
            "by_regime": []
        }
    
    grp = df.groupby("regime")
    by_regime = []
    for regime, g in grp:
        count = int(len(g))
        hit = float(g["success"].mean()) if count else 0.0
        agent_mean_ret = float(g["agent_ret"].mean()) if count else 0.0
        spy_baseline = float(g["spy_fwd_ret"].mean()) if count else 0.0
        alpha = agent_mean_ret - spy_baseline
        
        by_regime.append({
            "regime": regime,
            "count": count,
            "hit_rate": round(hit, 4),
            "mean_return": round(agent_mean_ret, 6),
            "spy_baseline": round(spy_baseline, 6),
            "alpha_vs_spy": round(alpha, 6),
        })
    
    by_regime.sort(key=lambda x: x["count"], reverse=True)
    
    return {
        "ok": True,
        "agent": agent_name,
        "lookahead_days": lookahead_days,
        "rows": int(len(df)),
        "by_regime": by_regime,
    }
