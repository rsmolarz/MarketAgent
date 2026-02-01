import json
import logging
from pathlib import Path
from datetime import datetime

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def load_events(path="telemetry/events.jsonl", last_n=5000):
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text().splitlines()[-last_n:]
    events = []
    for line in lines:
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            logging.debug(f"Skipping malformed JSON line in events file")
            pass
    return events


def generate_plots(events_path="telemetry/events.jsonl", out_dir="telemetry/charts"):
    if not HAS_MATPLOTLIB:
        print("matplotlib not available, skipping plots")
        return
    
    events = load_events(events_path)
    if not events:
        print("No events found")
        return
    
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    
    rewards = [e.get("reward") or 0 for e in events]
    costs = [e.get("cost_usd") or 0 for e in events]
    latencies = [e.get("latency_ms") or 0 for e in events]
    
    plt.figure(figsize=(10, 6))
    plt.scatter(costs, rewards, alpha=0.5, s=10)
    plt.xlabel("Cost (USD)")
    plt.ylabel("Reward")
    plt.title("Reward vs Cost")
    plt.savefig(out / "reward_vs_cost_scatter.png", dpi=100)
    plt.close()
    
    plt.figure(figsize=(12, 4))
    plt.plot(rewards[-500:], alpha=0.7, linewidth=0.8)
    plt.xlabel("Event Index")
    plt.ylabel("Reward")
    plt.title("Reward Over Time (last 500)")
    plt.savefig(out / "reward_over_time.png", dpi=100)
    plt.close()
    
    plt.figure(figsize=(12, 4))
    non_zero_costs = [c for c in costs if c > 0]
    if non_zero_costs:
        plt.plot(non_zero_costs[-500:], alpha=0.7, linewidth=0.8)
        plt.xlabel("Event Index")
        plt.ylabel("Cost (USD)")
        plt.title("Cost Over Time (last 500)")
    else:
        plt.text(0.5, 0.5, "No cost data", ha='center', va='center')
    plt.savefig(out / "cost_over_time.png", dpi=100)
    plt.close()
    
    print(f"Charts saved to {out_dir}")


if __name__ == "__main__":
    generate_plots()
