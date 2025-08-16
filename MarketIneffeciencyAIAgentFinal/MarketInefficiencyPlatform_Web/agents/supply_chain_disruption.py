
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
shipping_index = get_shipping_index()

class SupplyChainDisruptionAgent(BaseAgent):
    name = "SupplyChainDisruptionAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Detect disruptions in global supply chains via shipping costs or port delays."

    def act(self, context=None):
        # Simulated shipping index value (e.g., Freightos)
        shipping_index = 7500  # anything >7000 is an alert
        alerts = []

        if shipping_index > 7000:
            alert = f"Shipping cost spike: {shipping_index}"
            finding = {
                "title": "Supply Chain Disruption",
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
        return f"{len(result)} supply chain alerts."

    def run(self, mode="realtime"):
        print(f"[{self.name}] {self.plan()}")
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(SupplyChainDisruptionAgent())
