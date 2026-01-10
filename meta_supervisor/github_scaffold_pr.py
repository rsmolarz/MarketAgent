import os
import subprocess
from datetime import datetime
import json
import urllib.request

def create_scaffold_pr(agent_name: str, title: str, body: str):
    repo = os.environ.get("GITHUB_REPO")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        raise RuntimeError("GitHub repo/token not configured")

    branch = f"agent/scaffold/{agent_name}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    subprocess.run(["git", "checkout", "-b", branch], check=True)
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", f"Scaffold agent: {agent_name}"], check=True)
    subprocess.run(["git", "push", "origin", branch], check=True)

    payload = json.dumps({
        "title": title,
        "head": branch,
        "base": "main",
        "body": body
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/pulls",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "MarketAgent-Scaffold",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())
