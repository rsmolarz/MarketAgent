import requests
import feedparser

ARXIV_API = "http://export.arxiv.org/api/query"

def fetch_arxiv(query: str, max_results: int = 10):
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    r = requests.get(ARXIV_API, params=params, timeout=20)
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    items = []
    for e in feed.entries:
        items.append({
            "source": "arxiv",
            "title": e.get("title","").strip(),
            "url": e.get("link",""),
            "summary": (e.get("summary","") or "").strip(),
            "published": e.get("published",""),
            "authors": [a.name for a in e.get("authors", [])] if e.get("authors") else [],
        })
    return items
