"""
Meta-Agent Scorer: Severity-weighted scoring and schedule enforcement.

Closed loop: agents → findings → forward returns → ranking → disable/weight → scheduler enforcement
"""
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging

import pandas as pd

logger = logging.getLogger(__name__)

SEVERITY_WEIGHT = {
    "low": 0.5,
    "medium": 1.0,
    "high": 1.5,
    "critical": 2.0,
}

DEFAULT_HORIZONS = [1, 5, 20]
DEFAULT_SYMBOL_FOR_LABELING = "SPY"


@dataclass
class AgentScore:
    agent: str
    n: int
    score: float
    avg_ret_5d: float
    hit_rate_5d: float


def _load_spy(start: str = "2007-01-01") -> pd.DataFrame:
    """Load SPY price data for forward return labeling (uses caching if available)."""
    try:
        from data_sources.price_loader import load_spy
        return load_spy(start=start, use_cache=True)
    except ImportError:
        pass
    
    import yfinance as yf
    df = yf.download("SPY", start=start, progress=False)
    if df.empty:
        return pd.DataFrame(columns=["Date", "Close"])
    df = df.reset_index()
    
    if "Date" in df.columns:
        date_col = df["Date"]
    else:
        date_col = df.iloc[:, 0]
    
    if "Close" in df.columns:
        close_col = df["Close"]
    elif ("Close", "SPY") in df.columns:
        close_col = df[("Close", "SPY")]
    else:
        close_col = df.iloc[:, 4]
    
    result = pd.DataFrame({
        "Date": pd.to_datetime(date_col).dt.tz_localize(None),
        "Close": close_col.values.flatten() if hasattr(close_col.values, 'flatten') else close_col.values
    })
    result = result.dropna().sort_values("Date")
    return result


def _nearest_trading_index(dates: pd.Series, t: pd.Timestamp) -> Optional[int]:
    """Find first date >= t."""
    idx = dates.searchsorted(t)
    if idx >= len(dates):
        return None
    return int(idx)


def label_forward_returns(
    events: pd.DataFrame,
    spy: pd.DataFrame,
    horizons: List[int] = None,
) -> pd.DataFrame:
    """Label each event with forward returns at multiple horizons."""
    horizons = horizons or DEFAULT_HORIZONS

    if spy.empty or events.empty:
        return pd.DataFrame()

    spy_dates = spy["Date"].values
    spy_close = spy["Close"].values

    out_rows = []
    for _, e in events.iterrows():
        ts = pd.to_datetime(e.get("timestamp"))
        if pd.isna(ts):
            continue
        t = pd.Timestamp(ts)
        if t.tz is not None:
            t = t.tz_localize(None)

        i0 = _nearest_trading_index(pd.Series(spy_dates), t)
        if i0 is None:
            continue

        p0 = float(spy_close[i0])

        row = dict(e)
        for h in horizons:
            i1 = i0 + h
            if i1 >= len(spy_close):
                row[f"fwd_ret_{h}d"] = None
            else:
                p1 = float(spy_close[i1])
                row[f"fwd_ret_{h}d"] = (p1 / p0) - 1.0
        out_rows.append(row)

    return pd.DataFrame(out_rows)


def compute_agent_scores(
    labeled: pd.DataFrame,
    min_signals: int = 15,
    primary_horizon: int = 5,
) -> List[AgentScore]:
    """Compute severity-weighted agent scores."""
    if labeled.empty:
        return []

    hcol = f"fwd_ret_{primary_horizon}d"
    labeled = labeled.dropna(subset=[hcol])

    scores: List[AgentScore] = []

    for agent, g in labeled.groupby("agent_name"):
        n = len(g)
        if n < min_signals:
            continue

        w = g["severity"].map(lambda s: SEVERITY_WEIGHT.get(str(s).lower(), 1.0)).astype(float)
        r = g[hcol].astype(float)

        wr = (w * r)
        avg = float(wr.sum() / max(w.sum(), 1e-9))
        hit = float((r > 0).mean())

        vol = float(r.std(ddof=1)) if n > 1 else 0.0
        sharpe_like = avg / (vol + 1e-6)

        score = (0.55 * avg) + (0.35 * (hit - 0.5)) + (0.10 * sharpe_like)

        scores.append(AgentScore(
            agent=agent,
            n=n,
            score=float(score),
            avg_ret_5d=avg,
            hit_rate_5d=hit,
        ))

    scores.sort(key=lambda x: x.score, reverse=True)
    return scores


def write_schedule_updates(
    scores: List[AgentScore],
    schedule_path: str = "agent_schedule.json",
    min_signals: int = 25,
    disable_quantile: float = 0.30,
) -> Dict:
    """
    Updates agent_schedule.json in-place using the existing schema:
      - enabled
      - weight
      - rank
      - score
      - reason

    Leaves interval untouched.
    """
    with open(schedule_path, "r") as f:
        schedule = json.load(f)

    eligible = [s for s in scores if s.n >= min_signals]

    if not eligible:
        for agent, cfg in schedule.items():
            if cfg.get("enabled") is True:
                cfg["enabled"] = False
                cfg["weight"] = 0.0
                cfg["reason"] = "insufficient data (0 < {})".format(min_signals)
                cfg["rank"] = None
                cfg["score"] = 0.0

        with open(schedule_path, "w") as f:
            json.dump(schedule, f, indent=2)
        return schedule

    eligible.sort(key=lambda x: x.score, reverse=True)

    cutoff_index = int(len(eligible) * (1.0 - disable_quantile))
    cutoff_score = eligible[cutoff_index].score if cutoff_index < len(eligible) else -999

    max_score = eligible[0].score
    min_score = eligible[-1].score
    span = max(max_score - min_score, 1e-6)

    for rank, s in enumerate(eligible, start=1):
        cfg = schedule.get(s.agent)
        if not cfg:
            continue

        norm = (s.score - min_score) / span
        weight = round(0.1 + 0.9 * norm, 3)

        if s.score < cutoff_score or s.score < 0:
            cfg["enabled"] = False
            cfg["weight"] = 0.0
            cfg["reason"] = (
                "mean_return {:.2f}% < 0%".format(s.avg_ret_5d * 100)
                if s.score < 0 else
                "rank {} below cutoff".format(rank)
            )
            cfg["rank"] = None
            cfg["score"] = round(s.score, 6)
        else:
            cfg["enabled"] = True
            cfg["weight"] = weight
            cfg["rank"] = rank
            cfg["score"] = round(s.score, 6)
            cfg["reason"] = "meta-ranked"

    scored_agents = {s.agent for s in scores}
    for agent, cfg in schedule.items():
        if agent not in scored_agents:
            cfg["enabled"] = False
            cfg["weight"] = 0.0
            cfg["rank"] = None
            cfg["score"] = 0.0
            cfg["reason"] = "insufficient data (0 < {})".format(min_signals)

    with open(schedule_path, "w") as f:
        json.dump(schedule, f, indent=2)

    logger.info(f"Updated schedule for {len(eligible)} agents")
    return schedule


def run_scoring(
    lookback_days: int = 365 * 5,
    schedule_path: str = "agent_schedule.json",
    min_signals: int = 25,
) -> List[AgentScore]:
    """
    Pull findings from DB, label forward returns vs SPY,
    compute ranking, write schedule updates.
    """
    from models import db, Finding
    
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    q = (
        db.session.query(Finding)
        .filter(Finding.timestamp >= cutoff)
        .order_by(Finding.timestamp.asc())
    )
    
    rows = []
    for f in q.all():
        rows.append({
            "id": f.id,
            "timestamp": f.timestamp,
            "agent_name": f.agent_name,
            "severity": f.severity,
            "symbol": f.symbol,
            "title": f.title,
        })

    events = pd.DataFrame(rows)
    if events.empty:
        logger.warning("No findings found for meta-agent evaluation")
        return []

    spy = _load_spy(start="2007-01-01")
    labeled = label_forward_returns(events, spy, horizons=DEFAULT_HORIZONS)

    scores = compute_agent_scores(labeled, min_signals=min_signals, primary_horizon=5)

    write_schedule_updates(
        scores,
        schedule_path=schedule_path,
        min_signals=min_signals,
        disable_quantile=0.30,
    )
    
    logger.info(f"Meta-Agent computed scores for {len(scores)} agents")
    return scores


def is_agent_disabled(agent_name: str, schedule_path: str = "agent_schedule.json") -> bool:
    """Check if agent is disabled by Meta-Agent."""
    try:
        with open(schedule_path, "r") as f:
            sched = json.load(f)
        cfg = sched.get(agent_name, {})
        return bool(cfg.get("disabled", False))
    except Exception:
        return False
