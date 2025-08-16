
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
from data_sources.regulatory_news import get_regulatory_headlines

class RegulatoryAlertAgent(BaseAgent):
    name = "RegulatoryAlertAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Check for SEC/CFTC/FED filings or regulatory fines/news."

    def act(self, context=None):
items = get_regulatory_headlines()
        alerts = []

        for headline in items:
            alert = f"⚖️ Regulatory Alert: {headline}"
            finding = {
                "title": "Regulatory Risk",
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
        return f"{len(result)} regulatory findings."

    def run(self, mode='realtime'):
        print(f"[{self.name}] {self.plan()}")
        print(self.reflect(self.act()))

AgentRegistry.register(RegulatoryAlertAgent())