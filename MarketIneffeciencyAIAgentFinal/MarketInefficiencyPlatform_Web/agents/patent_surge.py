
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
from data_sources.uspto_api import get_recent_ai_patent_count

class PatentSurgeAgent(BaseAgent):
    name = "PatentSurgeAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Track new tech patent filings to detect sudden innovation surges."

    def act(self, context=None):
        ai_patents = get_recent_ai_patent_count()
        alerts = []

        if ai_patents > 40:
            alert = f"AI-related patent surge: {ai_patents} filings this month"
            finding = {
                "title": "Patent Filing Spike",
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
        return f"{len(result)} patent surges."

    def run(self, mode="realtime"):
        print(f"[{self.name}] {self.plan()}")
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(PatentSurgeAgent())
