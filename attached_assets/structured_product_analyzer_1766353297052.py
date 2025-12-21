import math

class StructuredProductAnalyzer:
    def __init__(self, num_assets: int = 100):
        self.num_assets = num_assets

    def _prob_loss_exceeds(self, k: int, pd: float) -> float:
        N = self.num_assets
        return sum(math.comb(N, i) * (pd**i) * ((1-pd)**(N-i)) for i in range(k, N+1))

    def analyze_tranches(self, pd: float, tranches: list) -> list:
        results = []
        for t in tranches:
            attach_count = math.ceil((t['attach_pct']/100) * self.num_assets)
            prob_loss_ind = self._prob_loss_exceeds(attach_count, pd)
            prob_loss_corr = pd if attach_count < self.num_assets else 0.0
            results.append({**t, "loss_prob_ind": prob_loss_ind, "loss_prob_corr": prob_loss_corr})
        return results
