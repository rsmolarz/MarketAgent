def score_proposal(p: dict) -> float:
    score = 0.0

    score += p.get("confidence", 0) * 40
    score += 10 if "distressed" in p.get("inefficiency_type","").lower() else 0
    score += 10 if "derivatives" in p.get("inefficiency_type","").lower() else 0

    score -= len(p.get("data_required", [])) * 2

    return round(min(score, 100), 1)
