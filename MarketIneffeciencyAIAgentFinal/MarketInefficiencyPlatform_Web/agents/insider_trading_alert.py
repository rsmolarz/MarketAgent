
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
from data_sources.openinsider import get_insider_buy_counts

class InsiderTradingAlertAgent(BaseAgent):
    name = "InsiderTradingAlertAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
trades = get_insider_buy_counts()

    def act(self, context=None):
        trades = {"MSFT": 8, "AMZN": 2, "NFLX": 12}  # # of insider buys this week
        alerts = []

        for stock, count in trades.items():
            if count >= 10:
                alert = f"{stock}: {count} insider buys this week"
                finding = {
                    "title": "Insider Trading Spike",
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
        return f"{len(result)} insider alerts posted."

    def run(self, mode="realtime"):
        print(f"[{self.name}] {self.plan()}")
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(InsiderTradingAlertAgent())
