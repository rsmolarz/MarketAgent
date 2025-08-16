
from sklearn.ensemble import IsolationForest
import numpy as np
import requests
from agents import BaseAgent, AgentRegistry
from notifiers import notify_all

class MLAnomalyMacroAgent(BaseAgent):
    name = "MLAnomalyMacroAgent"
    api_url = "http://localhost:5000/findings"

    def plan(self):
        return "Analyze macro indicators using ML anomaly detection (IsolationForest)."

    def act(self, context=None):
        # Simulated historical GDP growth + latest value
        # (in real use case, pull from actual economic data APIs)
        historical_data = np.array([
            2.5, 2.7, 2.6, 2.9, 3.1, 3.0, 2.8, 3.0, 2.9, 2.7,
            2.8, 3.1, 2.9, 3.0, 3.2, 3.3, 3.0, 2.9, 2.7, 3.0,
            3.1, 2.8, 3.0, 3.2, 2.6, 2.7, 2.9, 3.0, 3.1, -2.5  # Anomalous last entry
        ]).reshape(-1, 1)

        model = IsolationForest(contamination=0.05, random_state=42)
        model.fit(historical_data)

        predictions = model.predict(historical_data)
        anomaly_index = np.where(predictions == -1)[0]

        alerts = []
        for i in anomaly_index:
            severity = "high" if i == len(historical_data) - 1 else "medium"
            message = f"Anomalous GDP growth detected at index {i}: {historical_data[i][0]}%"
            alerts.append(message)

            finding = {
                "title": "ML Macro Anomaly",
                "description": message,
                "severity": severity,
                "agent": self.name,
                "timestamp": "now"
            }

            try:
                requests.post(self.api_url, json=finding)
                notify_all(finding)
            except Exception as e:
                print(f"[{self.name}] Failed to post finding: {e}")

        return alerts

    def reflect(self, result=None):
        return f"Posted {len(result)} ML-detected macro anomalies." if result else "No anomalies detected."

    def run(self, mode="realtime"):
        print(f"[{self.name}] running in {mode} mode")
        print(self.plan())
        result = self.act()
        print(self.reflect(result))

AgentRegistry.register(MLAnomalyMacroAgent())
