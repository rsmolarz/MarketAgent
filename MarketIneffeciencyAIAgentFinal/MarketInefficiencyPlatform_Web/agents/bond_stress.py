
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all

class BondStressAgent(BaseAgent):
    name = "BondStressAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Detect bond market stress like yield curve inversions."

    def act(self, context=None):
        yields = {
            '10Y': 4.1,
            '2Y': 4.5
        }
        alerts = []

        if yields['2Y'] > yields['10Y']:
            alert = "Yield curve inversion detected! (2Y > 10Y)"
            finding = {
                "title": "Bond Market Stress",
                "description": alert,
                "severity": "high",
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
        return f"{len(result)} bond alerts posted."

    def run(self, mode="realtime"):
        print(f"[{self.name}] running...")
        print(self.plan())
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(BondStressAgent())
