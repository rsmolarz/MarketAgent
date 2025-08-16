
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all

class RetailSentimentAgent(BaseAgent):
    name = "RetailSentimentAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Scan consumer products for unusual sentiment drops."

    def act(self, context=None):
        sentiments = {
            'iPhone': 4.5,
            'Nike Shoes': 3.2,
            'Coca-Cola': 4.0,
            'Tesla Model Y': 2.1
        }
        alerts = []

        for product, score in sentiments.items():
            if score < 3:
                alert = f"Negative sentiment on {product}: {score}/5"
                finding = {
                    "title": "Retail Sentiment Alert",
                    "description": alert,
                    "severity": "low",
                    "agent": self.name,
                    "timestamp": "now"
                }
                try:
                    requests.post(self.api_url, json=finding)
                    notify_all(finding)
                except Exception as e:
                    print(f"[{self.name}] Failed: {e}")
                alerts.append(alert)

        return alerts

    def reflect(self, result=None):
        return f"{len(result)} sentiment alerts triggered."

    def run(self, mode="realtime"):
        print(f"[{self.name}] running...")
        print(self.plan())
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(RetailSentimentAgent())
