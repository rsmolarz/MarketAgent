
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
from data_sources.binance_funding import get_btc_perp_funding

class CryptoFundingRateAgent(BaseAgent):
    name = "CryptoFundingRateAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Analyze funding rates in perpetual swaps to assess bias."

    def act(self, context=None):
funding_rate = get_btc_perp_funding()
        if funding_rate > 0.15:
            alert = f"🧿 High crypto funding rate: {funding_rate}% on BTC perp"
            finding = {
                "title": "Crypto Funding Alert",
                "description": alert,
                "severity": "medium",
                "agent": self.name,
                "timestamp": "now"
            }
            requests.post(self.api_url, json=finding)
            notify_all(finding)
            return [alert]
        return []

    def reflect(self, result=None):
        return f"{len(result)} funding rate alerts."

    def run(self, mode='realtime'):
        print(f"[{self.name}] {self.plan()}")
        print(self.reflect(self.act()))

AgentRegistry.register(CryptoFundingRateAgent())