
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
from data_sources.news_risk import get_geopolitical_risk_index

class GeopoliticalRiskAgent(BaseAgent):
    name = "GeopoliticalRiskAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Detect global instability via news or simulated conflict data."

    def act(self, context=None):
        risk_level = get_geopolitical_risk_index()
        alerts = []

        if risk_level > 8:
            alert = f"Geopolitical risk spike: index = {risk_level}"
            finding = {
                "title": "Geopolitical Risk Alert",
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
        return f"{len(result)} geopolitical risks flagged."

    def run(self, mode="realtime"):
        print(f"[{self.name}] {self.plan()}")
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(GeopoliticalRiskAgent())
