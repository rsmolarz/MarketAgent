import json
from pathlib import Path
from collections import defaultdict, deque
import yaml

def load_events(path="telemetry/events.jsonl", last_n=5000):
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text().splitlines()[-last_n:]
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except:
            pass
    return out

def rolling_metrics(events, window=200):
    by = defaultdict(lambda: deque(maxlen=window))
    for e in events:
        a = e.get("agent")
        if not a:
            continue
        r = e.get("reward")
        if r is None:
            continue
        by[a].append(float(r))
    metrics = {}
    for a, dq in by.items():
        if not dq:
            continue
        avg = sum(dq) / len(dq)
        metrics[a] = {"rolling_avg_reward": avg, "n": len(dq)}
    return metrics

def retire_candidates(manifest_path="agents/manifest.yaml", min_n=100, reward_floor=0.05):
    manifest = yaml.safe_load(Path(manifest_path).read_text())
    events = load_events()
    m = rolling_metrics(events)

    candidates = []
    for a in manifest["agents"]:
        tag = a.get("module")
        if tag in m and m[tag]["n"] >= min_n and m[tag]["rolling_avg_reward"] < reward_floor:
            candidates.append({"agent": a["name"], "module": tag, **m[tag]})
    return candidates

def write_report(candidates):
    Path("meta/reports").mkdir(parents=True, exist_ok=True)
    Path("meta/reports/retirement_report.json").write_text(json.dumps({"candidates": candidates}, indent=2))

if __name__ == "__main__":
    c = retire_candidates()
    write_report(c)
