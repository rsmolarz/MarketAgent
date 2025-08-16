
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all

class ForexAnomalyAgent(BaseAgent):
    name = "ForexAnomalyAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Scan for abnormal moves in FX pairs (e.g., USD/EUR, JPY/USD)."

    def act(self, context=None):
        # Simulated forex rates
        fx = {
            'USD/EUR': 0.91,
            'JPY/USD': 0.0068,
            'GBP/USD': 1.31
        }
        alerts = []

        if fx['JPY/USD'] < 0.0065:
            alert = "Yen weakening anomaly detected."
        elif fx['GBP/USD'] > 1.35:
            alert = "Pound spike detected."
        else:
            alert = None

        if alert:
            finding = {
                "title": "Forex Market Alert",
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
        return f"Posted {len(result)} forex alerts." if result else "No FX issues."

    def run(self, mode="realtime"):
        print(f"[{self.name}] running...")
        print(self.plan())
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(ForexAnomalyAgent())
