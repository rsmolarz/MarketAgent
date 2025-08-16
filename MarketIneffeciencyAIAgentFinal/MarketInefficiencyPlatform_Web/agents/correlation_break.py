
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
corr = get_asset_correlation()

class CorrelationBreakAgent(BaseAgent):
    name = "CorrelationBreakAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Monitor correlation breakdown between assets (e.g. SPY vs TLT)."

    def act(self, context=None):
        corr = 0.05
        alerts = []

        if corr < 0.1:
            alert = "📉 Correlation breakdown: SPY vs TLT = 0.05"
            finding = {
                "title": "Correlation Breakdown",
                "description": alert,
                "severity": "medium",
                "agent": self.name,
                "timestamp": "now"
            }
            requests.post(self.api_url, json=finding)
            notify_all(finding)
            alerts.append(alert)

        return alerts

    def reflect(self, result=None):
        return f"{len(result)} correlation breaks."

    def run(self, mode='realtime'):
        print(f"[{self.name}] {self.plan()}")
        print(self.reflect(self.act()))

AgentRegistry.register(CorrelationBreakAgent())