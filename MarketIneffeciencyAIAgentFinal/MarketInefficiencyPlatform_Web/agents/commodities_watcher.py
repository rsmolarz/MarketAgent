
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all

class CommoditiesWatcherAgent(BaseAgent):
    name = "CommoditiesWatcherAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Monitor key commodity prices (e.g., gold, oil) for volatility or macroeconomic anomalies."

    def act(self, context=None):
        # Simulated commodity prices (real integration could use EIA, FRED, Yahoo Finance APIs)
        commodities = {
            'Gold': 1920.25,
            'Crude Oil': 88.10,
            'Silver': 24.60,
            'Natural Gas': 3.25
        }

        # Simulated thresholds for alerting
        alerts = []
        for name, price in commodities.items():
            if name == 'Crude Oil' and price > 85:
                alert = f"High crude oil price detected: ${price}"
            elif name == 'Gold' and price > 1900:
                alert = f"Gold price spike: ${price}"
            elif name == 'Natural Gas' and price > 3:
                alert = f"Natural gas volatility: ${price}"
            else:
                continue

            alerts.append(alert)

            finding = {
                "title": f"Commodity Alert: {name}",
                "description": alert,
                "severity": "medium",
                "agent": self.name,
                "timestamp": "now"
            }

            try:
                requests.post(self.api_url, json=finding)
                notify_all(finding)
            except Exception as e:
                print(f"[{self.name}] Failed to post or notify: {e}")

        return alerts

    def reflect(self, result=None):
        return f"Posted {len(result)} commodity alerts." if result else "No commodity anomalies found."

    def run(self, mode="realtime"):
        print(f"[{self.name}] running in {mode} mode")
        print(self.plan())
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(CommoditiesWatcherAgent())
