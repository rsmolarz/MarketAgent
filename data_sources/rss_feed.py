import feedparser

def fetch_rss(url: str, max_items: int = 10):
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:max_items]:
        items.append({
            "source": "rss",
            "title": (e.get("title","") or "").strip(),
            "url": e.get("link",""),
            "summary": (e.get("summary","") or "").strip(),
            "published": e.get("published","") or e.get("updated",""),
        })
    return items
