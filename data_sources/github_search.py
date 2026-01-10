import os
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

def search_github_repos(query: str, max_items: int = 10):
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    r = requests.get(
        "https://api.github.com/search/repositories",
        params={"q": query, "sort": "updated", "order": "desc", "per_page": max_items},
        headers=headers,
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    out = []
    for item in data.get("items", [])[:max_items]:
        out.append({
            "source": "github",
            "title": item.get("full_name",""),
            "url": item.get("html_url",""),
            "summary": item.get("description","") or "",
            "stars": item.get("stargazers_count", 0),
            "updated_at": item.get("updated_at",""),
        })
    return out
