
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all

class EquityMomentumAgent(BaseAgent):
    name = "EquityMomentumAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Identify high-momentum stocks with large recent gains."

    def act(self, context=None):
        stocks = {
            'NVDA': 6.8,  # daily % change
            'TSLA': -0.5,
            'AAPL': 1.3,
            'PLTR': 10.2
        }
        alerts = []

        for symbol, change in stocks.items():
            if change > 5:
                alert = f"{symbol} surged {change:.1f}% today!"
                finding = {
                    "title": "Equity Momentum Signal",
                    "description": alert,
                    "severity": "medium",
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
        return f"{len(result)} stocks showed momentum."

    def run(self, mode="realtime"):
        print(f"[{self.name}] running...")
        print(self.plan())
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(EquityMomentumAgent())
