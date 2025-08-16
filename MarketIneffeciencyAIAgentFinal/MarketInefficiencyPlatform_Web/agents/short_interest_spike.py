
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
data = get_short_interest()

class ShortInterestSpikeAgent(BaseAgent):
    name = "ShortInterestSpikeAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Detect stocks with rapidly rising short interest (squeeze risk)."

    def act(self, context=None):
        data = {"GME": 24.2, "AMC": 19.5, "TSLA": 2.5}  # short % of float
        alerts = []

        for ticker, percent in data.items():
            if percent > 20:
                alert = f"{ticker} short interest spike: {percent}% of float"
                finding = {
                    "title": "Short Interest Spike",
                    "description": alert,
                    "severity": "high",
                    "agent": self.name,
                    "timestamp": "now"
                }
                requests.post(self.api_url, json=finding)
                notify_all(finding)
                alerts.append(alert)

        return alerts

    def reflect(self, result=None):
        return f"{len(result)} short interest alerts."

    def run(self, mode='realtime'):
        print(f"[{self.name}] {self.plan()}")
        print(self.reflect(self.act()))

AgentRegistry.register(ShortInterestSpikeAgent())