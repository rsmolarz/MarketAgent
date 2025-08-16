
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
data = get_etf_flows()

class ETFFlowShiftAgent(BaseAgent):
    name = "ETFFlowShiftAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Monitor ETF inflow/outflow surges indicating sector shifts."

    def act(self, context=None):
        data = {"SPY": -1.1e9, "ARKK": 450e6}  # USD flow
        alerts = []

        for etf, flow in data.items():
            if abs(flow) > 500e6:
                alert = f"ETF {etf} flow: {'inflow' if flow > 0 else 'outflow'} of ${abs(flow)/1e6:.1f}M"
                finding = {
                    "title": "ETF Flow Shift",
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
        return f"{len(result)} ETF flow alerts."

    def run(self, mode='realtime'):
        print(f"[{self.name}] {self.plan()}")
        print(self.reflect(self.act()))

AgentRegistry.register(ETFFlowShiftAgent())