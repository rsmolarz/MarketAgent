class CDSAnalyzer:
    RATING_TO_PD = {"AAA": 0.005, "BBB": 0.05}
    def __init__(self, horizon: int = 5, lgd: float = 0.6):
        self.horizon, self.lgd = horizon, lgd

    def analyze_cds(self, rating: str, annual_spread_bps: float) -> dict:
        pd = self.RATING_TO_PD.get(rating.upper(), 0.05)
        expected_loss = pd * self.lgd
        total_premium = (annual_spread_bps * 1e-4) * self.horizon
        diff = total_premium - expected_loss
        if diff < -0.01: verdict = "underpriced"
        elif diff > 0.01: verdict = "overpriced"
        else: verdict = "fair"
        return {"rating": rating, "spread_bps": annual_spread_bps, "verdict": verdict}
