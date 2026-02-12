"""
ZillowDistressAgent
-------------------
Turns Zillow Research metro datasets into Finding objects for distressed market detection.
Identifies metros with: liquidity freeze, affordability shock, oversupply, rent compression.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from agents.base_agent import BaseAgent
from models import db, Finding

logger = logging.getLogger(__name__)


@dataclass
class ZillowDistressConfig:
    data_dir: Path = field(default_factory=lambda: Path("data/zillow"))
    z_lookback_months: int = 60
    yoy_months: int = 12
    mom_months: int = 1

    w_price_drawdown: float = 0.25
    w_sales_collapse: float = 0.20
    w_inventory_spike: float = 0.15
    w_liquidity_freeze: float = 0.15
    w_affordability_stress: float = 0.15
    w_rent_price_divergence: float = 0.10

    watch_threshold: float = 0.60
    act_threshold: float = 0.75
    critical_threshold: float = 0.90

    min_points: int = 36
    emit_top_n: int = 25

    include_metros: Optional[List[str]] = None
    exclude_metros: Optional[List[str]] = None


def _load_zillow_wide_csv(path: Path) -> pd.DataFrame:
    """Load Zillow Research metro wide-format CSV."""
    df = pd.read_csv(path)
    
    if "RegionName" not in df.columns:
        raise ValueError(f"Missing RegionName in {path.name}")
    
    date_cols = [c for c in df.columns if _looks_like_date_col(c)]
    if not date_cols:
        raise ValueError(f"No date columns found in {path.name}")
    
    wide = df[["RegionName"] + date_cols].copy()
    dt_cols = [pd.to_datetime(c) for c in date_cols]
    wide.columns = ["RegionName"] + dt_cols
    wide = wide.set_index("RegionName").sort_index(axis=1)
    wide = wide.apply(pd.to_numeric, errors="coerce")
    return wide


def _looks_like_date_col(col: str) -> bool:
    if len(col) != 10:
        return False
    if col[4] != "-" or col[7] != "-":
        return False
    try:
        pd.to_datetime(col)
        return True
    except Exception:
        return False


def _to_long(series_wide: pd.Series) -> pd.Series:
    s = series_wide.dropna()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    return s


def _zscore_latest(ts: pd.Series, lookback: int) -> Tuple[float, float, float]:
    ts = ts.dropna()
    if len(ts) < max(12, lookback // 2):
        return (0.0, float("nan"), float("nan"))

    window = ts.iloc[-lookback:] if len(ts) >= lookback else ts
    mu = window.mean()
    sig = window.std(ddof=0)
    if sig == 0 or np.isnan(sig):
        return (0.0, mu, sig)
    z = (ts.iloc[-1] - mu) / sig
    return (float(z), float(mu), float(sig))


def _pct_change(ts: pd.Series, periods: int) -> float:
    ts = ts.dropna()
    if len(ts) <= periods:
        return float("nan")
    prev = ts.iloc[-(periods + 1)]
    cur = ts.iloc[-1]
    if prev == 0 or np.isnan(prev) or np.isnan(cur):
        return float("nan")
    return float((cur / prev) - 1.0)


def _safe_sigmoid(x: float) -> float:
    if np.isnan(x):
        return 0.5
    x = max(-8.0, min(8.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def classify_distress_regime(features: Dict[str, float]) -> Tuple[str, float, Dict[str, float]]:
    """Classify distress regime from feature z-scores."""
    z_dom = features.get("z_dom", 0.0)
    z_inv = features.get("z_inventory", 0.0)
    z_sales = features.get("z_sales", 0.0)
    z_aff = features.get("z_afford", 0.0)
    z_rpd = features.get("z_rent_price_div", 0.0)

    s_liq = 0.45 * _safe_sigmoid(z_dom) + 0.35 * _safe_sigmoid(-z_sales) + 0.20 * _safe_sigmoid(z_inv)
    s_aff = 0.60 * _safe_sigmoid(z_aff) + 0.25 * _safe_sigmoid(-z_sales) + 0.15 * _safe_sigmoid(z_dom)
    s_over = 0.55 * _safe_sigmoid(z_inv) + 0.25 * _safe_sigmoid(z_dom) + 0.20 * _safe_sigmoid(-z_sales)
    s_rent = 0.65 * _safe_sigmoid(z_rpd) + 0.20 * _safe_sigmoid(z_dom) + 0.15 * _safe_sigmoid(-z_sales)

    candidates = {
        "liquidity_freeze": s_liq,
        "affordability_shock": s_aff,
        "oversupply": s_over,
        "rent_compression": s_rent,
    }
    best = max(candidates, key=candidates.get)
    best_score = float(candidates[best])

    sorted_scores = sorted(candidates.values(), reverse=True)
    margin = sorted_scores[0] - (sorted_scores[1] if len(sorted_scores) > 1 else 0.0)
    conf = float(min(1.0, 0.55 * best_score + 0.45 * margin))

    return best, conf, candidates


def estimate_time_to_mean_months(
    ts: pd.Series,
    lookback: int = 60,
    target_z: float = -0.5,
) -> Dict[str, float]:
    """Estimate time for distressed metric to mean-revert."""
    ts = ts.dropna()
    if len(ts) < max(24, lookback // 2):
        return {"half_life_months": float("nan"), "current_z": float("nan"), "target_z": target_z, "eta_months": float("nan")}

    window = ts.iloc[-lookback:] if len(ts) >= lookback else ts
    x = window.values.astype(float)
    x1 = x[1:]
    x0 = x[:-1]
    dx = x1 - x0

    A = np.vstack([np.ones_like(x0), x0]).T
    try:
        coef, *_ = np.linalg.lstsq(A, dx, rcond=None)
        a, b = float(coef[0]), float(coef[1])
    except Exception:
        a, b = 0.0, 0.0

    k = -b
    if k <= 1e-6:
        half_life = 120.0
    else:
        half_life = float(math.log(2.0) / k)

    mu = window.mean()
    sig = window.std(ddof=0) or 1.0
    current = float(window.iloc[-1])
    current_z = float((current - mu) / sig)

    if k <= 1e-6 or current_z == 0:
        eta = 120.0
    else:
        if current_z >= target_z:
            eta = 0.0
        else:
            ratio = abs(target_z) / (abs(current_z) + 1e-9)
            ratio = min(0.999, max(0.001, ratio))
            eta = float(-math.log(ratio) / k)

    return {
        "half_life_months": half_life,
        "current_z": current_z,
        "target_z": target_z,
        "eta_months": eta,
    }


def evaluate_deal_kill_rules(
    regime: str,
    features: Dict[str, float],
    *,
    normalize_threshold: float = 0.35,
    min_confirmations: int = 2,
) -> Dict[str, object]:
    """Kill rules based on regime normalization."""
    z_dom = features.get("z_dom", 0.0)
    z_inv = features.get("z_inventory", 0.0)
    z_aff = features.get("z_afford", 0.0)
    z_sales = features.get("z_sales", 0.0)
    z_price = features.get("z_price_drawdown", 0.0)

    normalized = {
        "liquidity": (z_dom < 0.5) and (z_sales > -0.5),
        "oversupply": (z_inv < 0.5),
        "affordability": (z_aff < 0.5),
        "price_stabilizing": (z_price > -0.5),
    }

    reasons: List[str] = []
    confirmations = 0

    if regime == "liquidity_freeze":
        if normalized["liquidity"]:
            confirmations += 1
            reasons.append("Liquidity freeze normalizing")
        if normalized["price_stabilizing"]:
            confirmations += 1
            reasons.append("Prices stabilizing")
    elif regime == "oversupply":
        if normalized["oversupply"]:
            confirmations += 1
            reasons.append("Inventory normalizing")
        if normalized["liquidity"]:
            confirmations += 1
            reasons.append("Absorption improving")
    elif regime == "affordability_shock":
        if normalized["affordability"]:
            confirmations += 1
            reasons.append("Affordability easing")
        if normalized["liquidity"]:
            confirmations += 1
            reasons.append("Buyer activity returning")
    elif regime == "rent_compression":
        z_rpd = features.get("z_rent_price_div", 0.0)
        if z_rpd < 0.5:
            confirmations += 1
            reasons.append("Rent/price divergence normalizing")
        if normalized["liquidity"]:
            confirmations += 1
            reasons.append("Liquidity improving")
    else:
        if normalized["liquidity"] and normalized["oversupply"]:
            confirmations += 1
            reasons.append("Multiple stress indicators normalizing")

    kill = confirmations >= min_confirmations
    return {"kill": kill, "reasons": reasons, "normalized": normalized}


DISTRESSED_IC_MEMO_SYSTEM_PROMPT = """You are an institutional real estate investment committee (IC) analyst.
You specialize in identifying distressed housing markets and designing acquisition strategies
(REO, short sales, builder closeouts, note purchases, seller-carry, loan assumptions).

Write concise, decision-useful IC memos. Be explicit about:
- what data supports the claim
- what could falsify it
- what to do next operationally (documents, underwriting, sourcing channels)
Do not include fluff or generic macro commentary.
"""

DISTRESSED_IC_MEMO_USER_TEMPLATE = """Create an IC memo for a distressed-market opportunity.

Context
- Metro: {metro}
- Distress regime: {regime} (confidence={regime_conf:.2f})
- Distress score: {distress_score:.2f} (severity={severity})
- Key metrics (latest):
{metrics_block}

Signals & Diagnostics
- Components (0..1; higher=worse):
{components_block}

Recovery Modeling
- Estimated time-to-mean (months): {eta_months:.1f}
- Half-life (months): {half_life_months:.1f}
- Current z (distress metric): {current_z:.2f}
- Target z: {target_z:.2f}

Required Output Format (exact sections)
1) One-paragraph thesis (what is breaking and why now)
2) Distress drivers (bullets; tie to metrics)
3) Trade expression (what assets to buy; which channels; what discounts)
4) Underwriting assumptions (recovery path + base/bull/bear)
5) Kill criteria (what would prove this wrong; hard triggers)
6) Next actions (7-day sprint plan: docs, brokers, deal room checklist)
"""


def _format_kv_block(d: Dict[str, float]) -> str:
    lines = []
    for k, v in d.items():
        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            vv = "NA"
        elif isinstance(v, float):
            vv = f"{v:.4f}"
        else:
            vv = str(v)
        lines.append(f"- {k}: {vv}")
    return "\n".join(lines)


class ZillowDistressAgent(BaseAgent):
    """Produces Findings for metros with distressed housing conditions."""

    def __init__(self, config: Optional[ZillowDistressConfig] = None):
        super().__init__()
        self.config = config or ZillowDistressConfig()

    @property
    def name(self) -> str:
        return "ZillowDistressAgent"

    def analyze(self) -> List[Dict]:
        """Required abstract method implementation - delegates to run()."""
        findings = self.run()
        result = []
        for f in findings:
            result.append({
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
                "confidence": f.confidence,
                "symbol": f.symbol,
                "market_type": f.market_type,
            })
        return result

    def run(self) -> List[Finding]:
        cfg = self.config
        data_dir = cfg.data_dir

        files = {
            "zhvi": data_dir / "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
            "income_needed": data_dir / "Metro_new_homeowner_income_needed_downpayment_0.20_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
            "doz_pending": data_dir / "Metro_mean_doz_pending_uc_sfrcondo_sm_month.csv",
            "sales_now": data_dir / "Metro_sales_count_now_uc_sfrcondo_month.csv",
            "inventory_fs": data_dir / "Metro_invt_fs_uc_sfrcondo_sm_month.csv",
            "zori": data_dir / "Metro_zori_uc_sfrcondomfr_sm_month.csv",
        }

        missing = [k for k, p in files.items() if not p.exists()]
        if missing:
            logger.warning(f"{self.name}: missing data files: {missing}. data_dir={data_dir.resolve()}")
            return []

        try:
            wide = {k: _load_zillow_wide_csv(p) for k, p in files.items()}
        except Exception as e:
            logger.exception(f"{self.name}: failed loading zillow datasets: {e}")
            return []

        metros = set(wide["zhvi"].index)
        for k in ["sales_now", "inventory_fs", "doz_pending", "income_needed", "zori"]:
            metros &= set(wide[k].index)

        metros = sorted(list(metros))
        if cfg.include_metros:
            include = set(cfg.include_metros)
            metros = [m for m in metros if m in include]
        if cfg.exclude_metros:
            exclude = set(cfg.exclude_metros)
            metros = [m for m in metros if m not in exclude]

        scored: List[Tuple[str, float, Dict, Dict, Dict]] = []

        for metro in metros:
            try:
                s_zhvi = _to_long(wide["zhvi"].loc[metro])
                s_sales = _to_long(wide["sales_now"].loc[metro])
                s_inv = _to_long(wide["inventory_fs"].loc[metro])
                s_dom = _to_long(wide["doz_pending"].loc[metro])
                s_aff = _to_long(wide["income_needed"].loc[metro])
                s_rent = _to_long(wide["zori"].loc[metro])
            except Exception:
                continue

            if min(len(s_zhvi), len(s_sales), len(s_inv), len(s_dom), len(s_aff), len(s_rent)) < cfg.min_points:
                continue

            yoy_price = _pct_change(s_zhvi, cfg.yoy_months)
            yoy_rent = _pct_change(s_rent, cfg.yoy_months)
            yoy_sales = _pct_change(s_sales, cfg.yoy_months)
            yoy_inv = _pct_change(s_inv, cfg.yoy_months)
            yoy_dom = _pct_change(s_dom, cfg.yoy_months)
            yoy_aff = _pct_change(s_aff, cfg.yoy_months)

            z_dom, *_ = _zscore_latest(s_dom, cfg.z_lookback_months)
            z_inv, *_ = _zscore_latest(s_inv, cfg.z_lookback_months)
            z_aff, *_ = _zscore_latest(s_aff, cfg.z_lookback_months)

            sales_yoy_series = s_sales.pct_change(cfg.yoy_months).dropna()
            z_sales, *_ = _zscore_latest(sales_yoy_series, cfg.z_lookback_months)

            price_yoy_series = s_zhvi.pct_change(cfg.yoy_months).dropna()
            z_price_yoy, *_ = _zscore_latest(price_yoy_series, cfg.z_lookback_months)

            rp_div_series = (s_rent.pct_change(cfg.yoy_months) - s_zhvi.pct_change(cfg.yoy_months)).dropna()
            z_rpd, *_ = _zscore_latest(rp_div_series, cfg.z_lookback_months)

            c_price_drawdown = _safe_sigmoid(-z_price_yoy)
            c_sales_collapse = _safe_sigmoid(-z_sales)
            c_inventory_spike = _safe_sigmoid(z_inv)
            c_liquidity_freeze = _safe_sigmoid(z_dom)
            c_affordability = _safe_sigmoid(z_aff)
            c_rent_price_div = _safe_sigmoid(-z_rpd)

            distress_score = (
                cfg.w_price_drawdown * c_price_drawdown
                + cfg.w_sales_collapse * c_sales_collapse
                + cfg.w_inventory_spike * c_inventory_spike
                + cfg.w_liquidity_freeze * c_liquidity_freeze
                + cfg.w_affordability_stress * c_affordability
                + cfg.w_rent_price_divergence * c_rent_price_div
            )

            features = {
                "z_dom": z_dom,
                "z_inventory": z_inv,
                "z_afford": z_aff,
                "z_sales": z_sales,
                "z_price_drawdown": -z_price_yoy,
                "z_rent_price_div": -z_rpd,
            }

            regime, regime_conf, regime_scores = classify_distress_regime(features)
            recovery = estimate_time_to_mean_months(price_yoy_series, lookback=cfg.z_lookback_months, target_z=-0.5)
            kill_eval = evaluate_deal_kill_rules(regime, features)

            if distress_score < cfg.watch_threshold:
                continue

            if distress_score >= cfg.critical_threshold:
                severity = "critical"
            elif distress_score >= cfg.act_threshold:
                severity = "high"
            else:
                severity = "medium"

            components = {
                "price_drawdown": c_price_drawdown,
                "sales_collapse": c_sales_collapse,
                "inventory_spike": c_inventory_spike,
                "liquidity_freeze": c_liquidity_freeze,
                "affordability_stress": c_affordability,
                "rent_price_divergence": c_rent_price_div,
            }

            metrics = {
                "yoy_price": yoy_price,
                "yoy_rent": yoy_rent,
                "yoy_sales": yoy_sales,
                "yoy_inventory": yoy_inv,
                "yoy_dom": yoy_dom,
                "yoy_affordability": yoy_aff,
                "latest_zhvi": float(s_zhvi.dropna().iloc[-1]),
                "latest_zori": float(s_rent.dropna().iloc[-1]),
                "latest_dom": float(s_dom.dropna().iloc[-1]),
                "latest_inventory": float(s_inv.dropna().iloc[-1]),
                "latest_sales": float(s_sales.dropna().iloc[-1]),
                "latest_income_needed": float(s_aff.dropna().iloc[-1]),
                "asof": str(s_zhvi.dropna().index[-1].date()),
            }

            scored.append((metro, float(distress_score), components, metrics, {
                "regime": regime,
                "regime_confidence": regime_conf,
                "regime_scores": regime_scores,
                "recovery": recovery,
                "kill_rules": kill_eval,
                "features": features,
            }))

        if not scored:
            return []

        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[: cfg.emit_top_n]

        findings: List[Finding] = []
        now = datetime.utcnow()

        for metro, score, components, metrics, meta in scored:
            severity = (
                "critical" if score >= cfg.critical_threshold else
                "high" if score >= cfg.act_threshold else
                "medium"
            )

            regime = meta["regime"]
            regime_conf = meta["regime_confidence"]
            recovery = meta["recovery"]
            kill_rules = meta["kill_rules"]

            title = f"Distressed Metro Signal: {metro} ({regime.replace('_',' ')})"
            description = (
                f"Distress score={score:.2f}. Regime={regime} ({regime_conf:.0%}). "
                f"Key stress: sales collapse={components['sales_collapse']:.2f}, "
                f"liquidity freeze={components['liquidity_freeze']:.2f}, "
                f"price drawdown={components['price_drawdown']:.2f}, "
                f"inventory spike={components['inventory_spike']:.2f}."
            )

            f = Finding(
                agent_name=self.name,
                timestamp=now,
                title=title,
                description=description,
                severity=severity,
                confidence=min(0.95, max(0.50, score)),
                symbol=metro,
                market_type="real_estate",
                finding_metadata={
                    "distress_score": score,
                    "distress_regime": regime,
                    "regime_confidence": regime_conf,
                    "components": components,
                    "metrics": metrics,
                    "recovery_model": recovery,
                    "kill_rules": kill_rules,
                    "deal_stage_suggested": "screened" if score < cfg.act_threshold else "underwritten",
                    "ic_memo_prompt": {
                        "system": DISTRESSED_IC_MEMO_SYSTEM_PROMPT,
                        "user": DISTRESSED_IC_MEMO_USER_TEMPLATE.format(
                            metro=metro,
                            regime=regime,
                            regime_conf=regime_conf,
                            distress_score=score,
                            severity=severity,
                            metrics_block=_format_kv_block(metrics),
                            components_block=_format_kv_block(components),
                            eta_months=float(recovery.get("eta_months", float("nan"))),
                            half_life_months=float(recovery.get("half_life_months", float("nan"))),
                            current_z=float(recovery.get("current_z", float("nan"))),
                            target_z=float(recovery.get("target_z", -0.5)),
                        ),
                    },
                },
            )
            findings.append(f)

        return findings
