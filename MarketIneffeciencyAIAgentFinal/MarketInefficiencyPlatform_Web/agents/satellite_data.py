
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
from data_sources.satellite_metrics import get_tanker_count

class SatelliteDataAgent(BaseAgent):
    name = "SatelliteDataAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Use satellite metrics to detect physical asset movement anomalies."

    def act(self, context=None):
tankers_at_sea = get_tanker_count()
        alerts = []

        if tankers_at_sea > 120:
            alert = f"🛰️ Tanker activity surge: {tankers_at_sea} visible oil tankers"
            finding = {
                "title": "Satellite Oil Alert",
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
        return f"{len(result)} satellite-based alerts."

    def run(self, mode='realtime'):
        print(f"[{self.name}] {self.plan()}")
        print(self.reflect(self.act()))

AgentRegistry.register(SatelliteDataAgent())