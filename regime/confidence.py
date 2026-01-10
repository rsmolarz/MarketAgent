import numpy as np

_cached_regime = None


def get_cached_regime():
    global _cached_regime
    return _cached_regime


def cache_regime(regime):
    global _cached_regime
    _cached_regime = regime


def regime_confidence(features: dict, scores: dict, prev_regime=None):
    vals = np.array(list(scores.values()), dtype=float)
    if vals.max() == 0:
        vals = np.ones_like(vals)
    probs = np.exp(vals) / np.exp(vals).sum()

    regime_probs = dict(zip(scores.keys(), probs))

    active = max(regime_probs, key=regime_probs.get)
    confidence = regime_probs[active]

    if prev_regime and regime_probs.get(prev_regime, 0) > 0.35:
        active = prev_regime
        confidence = regime_probs[prev_regime]

    transition = bool(confidence < 0.6)

    return {
        "active_regime": active,
        "confidence": float(confidence),
        "transition": transition,
        "distribution": {k: float(v) for k, v in regime_probs.items()}
    }
