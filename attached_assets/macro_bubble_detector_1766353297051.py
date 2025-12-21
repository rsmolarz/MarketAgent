from typing import Dict, Optional

class MacroBubbleDetector:
    def __init__(self, price_to_income_threshold: float = 1.3, credit_growth_threshold: float = 0.2):
        self.price_to_income_threshold = price_to_income_threshold
        self.credit_growth_threshold = credit_growth_threshold

    def fetch_data(self) -> Dict[str, list]:
        return {
            "house_price_index": [100, 110, 120, 140],
            "income_index": [100, 103, 105, 108],
            "debt_to_gdp": [0.60, 0.75, 0.90, 0.99]
        }

    def analyze(self, data: Optional[Dict[str, list]] = None) -> Dict:
        if data is None:
            data = self.fetch_data()
        prices, incomes = data["house_price_index"], data["income_index"]
        ratio = prices[-1] / incomes[-1]
        avg_ratio = sum(p/i for p, i in zip(prices[:-1], incomes[:-1])) / (len(prices)-1)
        bubble_flag = ratio > self.price_to_income_threshold * avg_ratio
        return {"current_ratio": ratio, "avg_ratio": avg_ratio, "bubble_flag": bubble_flag}
