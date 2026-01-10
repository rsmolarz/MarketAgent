from .definitions import REGIMES


def score_regimes(features):
    scores = {}

    for regime, rules in REGIMES.items():
        score = 0
        for k, v in rules.items():
            if features.get(k) == v:
                score += 1
        scores[regime] = score

    return scores
