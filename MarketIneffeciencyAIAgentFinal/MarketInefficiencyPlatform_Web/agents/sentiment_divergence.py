
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
from data_sources.social_sentiment import get_sentiment_and_price

class SentimentDivergenceAgent(BaseAgent):
    name = "SentimentDivergenceAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Detect when social sentiment diverges from price movement."

    def act(self, context=None):
        sentiment = 4.5  # out of 5
        price_change = -3.5  # %

        if sentiment > 4 and price_change < -2:
            alert = f"🧪 Sentiment/price mismatch: High sentiment but price dropped {price_change}%"
            finding = {
                "title": "Sentiment Divergence",
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
        return f"{len(result)} sentiment divergence alerts."

    def run(self, mode='realtime'):
        print(f"[{self.name}] {self.plan()}")
        print(self.reflect(self.act()))

AgentRegistry.register(SentimentDivergenceAgent())