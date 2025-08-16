
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
data = get_large_eth_transfers(min_eth=100)

class WhaleWalletWatcherAgent(BaseAgent):
    name = "WhaleWalletWatcherAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Track large crypto wallet transfers for whale activity."

    def act(self, context=None):
        data = [{"wallet": "0xabc...", "amount": 15000, "asset": "ETH"}]
        alerts = []

        for tx in data:
            if tx["amount"] > 10000:
                alert = f"Whale moved {tx['amount']} {tx['asset']} from {tx['wallet']}"
                finding = {
                    "title": "Whale Wallet Alert",
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
        return f"{len(result)} whale alerts."

    def run(self, mode='realtime'):
        print(f"[{self.name}] {self.plan()}")
        print(self.reflect(self.act()))

AgentRegistry.register(WhaleWalletWatcherAgent())