import json
from pathlib import Path
from typing import Optional, Tuple, List, Dict

import numpy as np

RECON = Path("alpha/reconciled.jsonl")
MODEL_DIR = Path("alpha/models")

FEATURES = ["score_final", "confidence"]


def _load_jsonl(p: Path) -> List[Dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _f(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def train(horizon_hours: int = 24, ridge: float = 5.0, min_rows: int = 250, max_rows: int = 12000) -> dict:
    rows = [r for r in _load_jsonl(RECON) if int(r.get("horizon_hours", 0)) == horizon_hours]
    rows = rows[-max_rows:]
    if len(rows) < min_rows:
        return {"ok": False, "reason": "insufficient_rows", "n": len(rows), "horizon_hours": horizon_hours}

    X = []
    y = []
    for r in rows:
        X.append([_f(r.get("score_final")), _f(r.get("confidence")), 1.0])
        y.append(_f(r.get("realized_pnl_bps")))

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=float)

    XtX = X.T @ X
    I = np.eye(X.shape[1], dtype=float)
    I[-1, -1] = 0.0
    w = np.linalg.inv(XtX + ridge * I) @ (X.T @ y)

    pred = X @ w
    resid = y - pred
    rmse = float(np.sqrt(np.mean(resid ** 2)))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / f"ridge_h{horizon_hours}.json"
    model = {
        "ok": True,
        "model": "ridge",
        "horizon_hours": horizon_hours,
        "features": FEATURES,
        "weights": [float(x) for x in w.tolist()],
        "rmse_bps": round(rmse, 4),
        "n": len(rows),
        "ridge": ridge,
    }
    model_path.write_text(json.dumps(model, indent=2))
    return model


def load(horizon_hours: int = 24) -> Optional[dict]:
    p = MODEL_DIR / f"ridge_h{horizon_hours}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def predict(score_final, confidence, horizon_hours: int = 24) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    m = load(horizon_hours)
    if not m or not m.get("ok"):
        return None, None, None
    w = m["weights"]
    feats = [_f(score_final), _f(confidence), 1.0]
    exp = sum(feats[i] * w[i] for i in range(len(feats)))
    return float(exp), float(m.get("rmse_bps", 0.0)), f"ridge_h{horizon_hours}"


if __name__ == "__main__":
    print(json.dumps(train(24), indent=2))
