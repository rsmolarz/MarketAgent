
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
put_call_skew = get_put_call_skew()

class OptionsSkewAgent(BaseAgent):
    name = "OptionsSkewAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Analyze option volatility skew for extremes in put-call pricing."

    def act(self, context=None):
        put_call_skew = 1.45  # Simulated skew > 1.4 = overhedging
        alerts = []

        if put_call_skew > 1.4:
            alert = f"High options skew: {put_call_skew} — market is over-hedged"
            finding = {
                "title": "Options Skew Alert",
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
        return f"{len(result)} option skew alerts."

    def run(self, mode="realtime"):
        print(f"[{self.name}] {self.plan()}")
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(OptionsSkewAgent())
