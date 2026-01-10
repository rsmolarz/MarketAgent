import json
import os
from pathlib import Path
from datetime import datetime, timezone

from data_sources.arxiv_feed import fetch_arxiv
from data_sources.rss_feed import fetch_rss
from data_sources.github_search import search_github_repos

OUT = Path("meta_supervisor/research/literature_scan.json")

def llm_extract_insights(items: list[dict]) -> dict:
    from openai import OpenAI
    
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    prompt = {
        "task": "Extract new agent ideas for trades/inefficiencies/distress based on research items.",
        "items": items[:30],
        "output_schema": {
            "high_signal_items": [{"title":"","url":"","why_it_matters":""}],
            "new_agent_ideas": [{
                "agent_name":"",
                "strategy_class":"",
                "edge_hypothesis":"",
                "markets":[],
                "horizon":"",
                "data_required":[],
                "test_plan":"",
                "confidence":0.0
            }],
            "new_data_sources": [{"name":"","url":"","use_case":""}]
        }
    }

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role":"system","content":"You are a quant research engineer. Output strict JSON only."},
            {"role":"user","content":json.dumps(prompt)}
        ],
        response_format={"type":"json_object"},
        temperature=0.2,
        max_tokens=1800,
    )
    return json.loads(resp.choices[0].message.content)

def run():
    arxiv_queries = [
        "cat:q-fin.ST OR cat:q-fin.TR AND (arbitrage OR microstructure OR liquidity OR funding)",
        "cat:cs.LG AND (market OR trading) AND (forecast OR regime OR volatility)",
    ]
    rss_urls = []
    github_queries = [
        "market microstructure python",
        "crypto funding rate backtest",
        "orderbook imbalance research",
    ]

    items = []
    for q in arxiv_queries:
        try:
            items.extend(fetch_arxiv(q, max_results=8))
        except Exception:
            pass
    for url in rss_urls:
        try:
            items.extend(fetch_rss(url, max_items=8))
        except Exception:
            pass
    for q in github_queries:
        try:
            items.extend(search_github_repos(q, max_items=6))
        except Exception:
            pass

    insights = {}
    if items:
        try:
            insights = llm_extract_insights(items)
        except Exception as e:
            insights = {"error": str(e)}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "items_count": len(items),
        "insights": insights
    }, indent=2))

    return insights

if __name__ == "__main__":
    run()
