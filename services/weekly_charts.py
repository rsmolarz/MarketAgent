import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RECON = Path("alpha/reconciled.jsonl")
OUTDIR = Path("meta_supervisor/reports/weekly_assets")

def _load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def _now_tag():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

def _week_slice(rows: list[dict], days: int = 7) -> list[dict]:
    return rows[-5000:]

def cvar_heatmap_by_regime_png(horizon_hours: int = 24) -> Path | None:
    rows = [r for r in _load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == horizon_hours]
    rows = _week_slice(rows)

    by_regime = defaultdict(list)
    for r in rows:
        rg = r.get("regime") or r.get("regime_label") or "UNKNOWN"
        try:
            by_regime[rg].append(float(r.get("realized_pnl_bps", 0.0)))
        except Exception:
            continue

    if not by_regime:
        return None

    def cvar95(xs):
        xs = sorted(xs)
        if not xs:
            return 0.0
        k = max(0, int((1.0 - 0.95) * len(xs)))
        tail = xs[: max(k+1, 1)]
        return sum(tail) / len(tail)

    regimes = sorted(by_regime.keys())
    vals = [abs(cvar95(by_regime[r])) for r in regimes]

    mat = np.array([vals], dtype=float)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / f"cvar_heatmap_{_now_tag()}.png"

    plt.figure(figsize=(10, 2.2))
    plt.imshow(mat, aspect="auto")
    plt.yticks([0], ["|CVaR95|"])
    plt.xticks(range(len(regimes)), regimes, rotation=45, ha="right", fontsize=8)
    plt.colorbar(label="bps (tail magnitude)")
    plt.title("Regime Tail Risk Heatmap (|CVaR95|, last window)")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()
    return out

def live_vs_sim_attribution_png(horizon_hours: int = 24) -> Path | None:
    rows = [r for r in _load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == horizon_hours]
    rows = _week_slice(rows)
    if not rows:
        return None

    live = []
    sim = []

    for r in rows:
        try:
            pnl = float(r.get("realized_pnl_bps", 0.0))
            sf = float(r.get("score_final") or r.get("ensemble_score_final") or 0.0)
        except Exception:
            continue
        exp = max(min(sf * 25.0, 200.0), -200.0)
        live.append(pnl)
        sim.append(exp)

    if not live:
        return None

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / f"live_vs_sim_{_now_tag()}.png"

    cum_live, cum_sim = [], []
    a = b = 0.0
    for x, y in zip(live, sim):
        a += x
        b += y
        cum_live.append(a)
        cum_sim.append(b)

    plt.figure(figsize=(10, 3.2))
    plt.plot(cum_live, label="Live cumulative PnL (bps)")
    plt.plot(cum_sim, label="Sim cumulative (proxy) (bps)")
    plt.title("Live vs Sim (proxy) Cumulative Attribution")
    plt.xlabel("Signal index (last window)")
    plt.ylabel("Cumulative bps")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()
    return out
