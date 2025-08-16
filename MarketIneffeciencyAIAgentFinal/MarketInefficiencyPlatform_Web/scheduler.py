
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import importlib
import threading

scheduler = BackgroundScheduler()
scheduler.start()

scheduled_jobs = {}

def run_agent_by_name(agent_name):
    try:
        mod = importlib.import_module(f"agents.{agent_name}")
        cls_name = [c for c in dir(mod) if c.endswith("Agent")][0]
        agent_class = getattr(mod, cls_name)
        agent_instance = agent_class()
        threading.Thread(target=agent_instance.run, kwargs={"mode": "scheduled"}).start()
        print(f"[{datetime.now()}] Scheduled run: {agent_name}")
    except Exception as e:
        print(f"[Scheduler] Failed to run {agent_name}: {e}")

def schedule_agent(agent_name, interval_minutes):
    if agent_name in scheduled_jobs:
        remove_agent(agent_name)
    job = scheduler.add_job(run_agent_by_name, 'interval', [agent_name], minutes=interval_minutes, id=agent_name)
    scheduled_jobs[agent_name] = job
    print(f"⏰ Scheduled {agent_name} every {interval_minutes} minutes.")

def remove_agent(agent_name):
    if agent_name in scheduled_jobs:
        scheduled_jobs[agent_name].remove()
        del scheduled_jobs[agent_name]
        print(f"❌ Removed schedule for {agent_name}")

def get_schedules():
    return list(scheduled_jobs.keys())
