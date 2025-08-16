
import json
import threading
import time
import importlib
from datetime import datetime

SCHEDULE_FILE = "agent_schedule.json"

def load_schedule():
    try:
        with open(SCHEDULE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def run_agent(agent_name):
    try:
        mod = importlib.import_module(f"agents.{agent_name}")
        cls_name = [c for c in dir(mod) if c.endswith("Agent")][0]
        agent_class = getattr(mod, cls_name)
        agent_instance = agent_class()
        print(f"[{datetime.now()}] Running agent: {agent_name}")
        agent_instance.run(mode="scheduled")
    except Exception as e:
        print(f"[Scheduler Error] {agent_name}: {e}")

def start_scheduler():
    def loop():
        schedule = load_schedule()
        last_run = {}
        while True:
            now = time.time()
            for agent, freq in schedule.items():
                if agent not in last_run or (now - last_run[agent]) >= freq * 60:
                    threading.Thread(target=run_agent, args=(agent,)).start()
                    last_run[agent] = now
            time.sleep(30)
    threading.Thread(target=loop, daemon=True).start()
