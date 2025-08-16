
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all
from data_sources.github_api import get_github_stars

class AltDataSignalAgent(BaseAgent):
    name = "AltDataSignalAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Monitor GitHub stars for tech signal momentum."

    def act(self, context=None):
        watched_repos = ["openai/gpt-4", "solana-labs/solana"]
        alerts = []

        for repo in watched_repos:
            stars = get_github_stars(repo)
            if stars and stars > 150000:
                alert = f"⭐ {repo} reached {stars} stars!"
                finding = {
                    "title": "GitHub Repo Spike",
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
        return f"{len(result)} GitHub signals posted."

    def run(self, mode="realtime"):
        print(f"[{self.name}] {self.plan()}")
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(AltDataSignalAgent())
