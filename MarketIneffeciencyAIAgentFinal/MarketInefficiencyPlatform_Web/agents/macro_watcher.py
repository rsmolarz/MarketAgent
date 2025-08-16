
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all

class MacroWatcherAgent(BaseAgent):
    name = "MacroWatcherAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Monitor macroeconomic indicators for signs of instability."

    def act(self, context=None):
        indicators = {
            'GDP_growth': -2.5,
            'news_sentiment': 'negative'
        }

        alerts = []
        if indicators['GDP_growth'] < -2:
            alerts.append("Warning: GDP contraction detected.")
        if indicators['news_sentiment'] == 'negative':
            alerts.append("Warning: Negative economic sentiment in the news.")

        for alert in alerts:
            finding = {
                "title": "Macroeconomic Alert",
                "description": alert,
                "severity": "medium",
                "agent": self.name,
                "timestamp": "now"
            }
            try:
                requests.post(self.api_url, json=finding)
                notify_all(finding)
            except Exception as post_err:
                print(f"[{self.name}] Failed to post to API: {post_err}")

        return alerts

    def reflect(self, result=None):
        return f"Posted {len(result)} macroeconomic alerts." if result else "No macro alerts triggered."

    def run(self, mode="realtime"):
        print(f"[{self.name}] running in {mode} mode")
        print(self.plan())
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(MacroWatcherAgent())
