
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
from data_sources.energy_grid import get_grid_utilization

class EnergyDisruptionAgent(BaseAgent):
    name = "EnergyDisruptionAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Watch energy grid loads or outages for systemic disruption signs."

    def act(self, context=None):
        grid_load = get_grid_utilization()
        alerts = []

        if grid_load > 90:
            alert = f"⚡ High grid load: {grid_load}% — possible regional stress"
            finding = {
                "title": "Energy Grid Stress",
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
        return f"{len(result)} energy alerts."

    def run(self, mode="realtime"):
        print(f"[{self.name}] {self.plan()}")
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(EnergyDisruptionAgent())
