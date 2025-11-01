"""
Geopolitical Risk Agent

Monitors global geopolitical risks via news analysis with NLP-based 
risk scoring for hotspot regions.
"""

import os
import requests
import feedparser
import urllib.parse
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime
from .base_agent import BaseAgent

try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    _sia = SentimentIntensityAnalyzer()
except Exception:
    _sia = None


class GeopoliticalRiskAgent(BaseAgent):
    """
    Monitors geopolitical risks through news analysis
    """
    
    RISK_KEYWORDS = [
        "war", "conflict", "attack", "military", "forces", "troops", "invasion",
        "sanction", "missile", "nuclear", "crisis", "tension", "clash", "protest",
        "escalation", "strike", "violence", "ceasefire", "hostility", "terror",
        "bomb", "airstrike", "shelling", "cyberattack"
    ]
    
    HOTSPOTS = {
        "Taiwan": "Taiwan China",
        "Ukraine": "Ukraine Russia",
        "Middle East": "Israel Gaza",
        "China-US": "China US conflict",
        "North Korea": "North Korea missile",
        "South China Sea": "South China Sea dispute"
    }
    
    def __init__(self):
        super().__init__()
        self.news_api_key = os.getenv("NEWS_API_KEY", "")
        self.seen_titles = {region: [] for region in self.HOTSPOTS}
        self.risk_threshold = 50
        self.max_articles_per_region = 5
        self.cache_size = 100
        
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze geopolitical risks across hotspot regions
        """
        findings = []
        
        for region, query in self.HOTSPOTS.items():
            try:
                # Fetch news articles
                articles = self._fetch_news_articles(query, self.max_articles_per_region)
                if not articles:
                    continue
                
                # Filter out seen articles
                new_articles = [
                    a for a in articles 
                    if a.get("title") and a["title"] not in self.seen_titles[region]
                ]
                
                # Update seen cache
                for article in new_articles:
                    title = article.get("title", "")
                    if title:
                        self.seen_titles[region].append(title)
                        if len(self.seen_titles[region]) > self.cache_size:
                            self.seen_titles[region] = self.seen_titles[region][-self.cache_size:]
                
                if not new_articles:
                    continue
                
                # Analyze articles for risk
                risk_score, keywords, summary = self._analyze_articles(new_articles)
                
                self.logger.info(f"{region} risk score: {risk_score}")
                
                # Create finding if risk threshold exceeded
                if risk_score >= self.risk_threshold:
                    severity = self._determine_severity(risk_score)
                    
                    findings.append({
                        'title': f'Geopolitical Risk Alert: {region}',
                        'description': f'{summary} Risk keywords: {", ".join(keywords)}',
                        'severity': severity,
                        'category': 'geopolitical_risk',
                        'metadata': {
                            'region': region,
                            'risk_score': risk_score,
                            'keywords': keywords,
                            'article_count': len(new_articles),
                            'query': query
                        }
                    })
                    
                    self.logger.warning(f"Geopolitical risk alert for {region}: {risk_score}/100")
                    
            except Exception as e:
                self.logger.error(f"Error analyzing region {region}: {e}")
        
        return findings
    
    def _fetch_news_articles(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Fetch recent news articles for a query via NewsAPI or Google News RSS
        """
        articles = []
        
        try:
            if self.news_api_key:
                # Use NewsAPI if available
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": max_results
                }
                headers = {"Authorization": f"Bearer {self.news_api_key}"}
                
                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                for article in data.get("articles", [])[:max_results]:
                    title = (article.get("title") or "").strip()
                    desc = (article.get("description") or article.get("content") or title or "").strip()
                    combined = f"{title}. {desc}".strip()
                    articles.append({"title": title, "text": combined})
                    
            else:
                # Fallback to Google News RSS
                rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
                feed = feedparser.parse(rss_url)
                
                for entry in feed.entries[:max_results]:
                    title = getattr(entry, "title", "") or ""
                    summary = getattr(entry, "summary", "") or ""
                    summary = re.sub('<[^<]+?>', '', summary)
                    text = (summary or title).strip()
                    articles.append({"title": title.strip(), "text": text})
                    
        except Exception as e:
            self.logger.error(f"Error fetching news articles for '{query}': {e}")
        
        return articles
    
    def _analyze_articles(self, articles: List[Dict]) -> Tuple[int, List[str], str]:
        """
        Analyze articles for geopolitical risk using sentiment and keywords
        
        Returns:
            Tuple of (risk_score, keywords, summary)
        """
        if not articles:
            return 0, [], ""
        
        total_risk = 0
        keyword_freq = {}
        top_articles = []
        
        for article in articles:
            text = (article.get("text") or "").lower()
            title = article.get("title") or ""
            
            # Sentiment analysis
            compound_score = 0.0
            if _sia:
                try:
                    compound_score = _sia.polarity_scores(text).get("compound", 0.0)
                except Exception:
                    compound_score = 0.0
            
            # Calculate risk from sentiment
            article_risk = 0
            if compound_score < -0.5:
                article_risk += 2
            elif compound_score < -0.2:
                article_risk += 1
            
            # Check for risk keywords
            found_keywords = {kw for kw in self.RISK_KEYWORDS if kw in text}
            for keyword in found_keywords:
                article_risk += 1
                keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1
            
            if article_risk > 0:
                top_articles.append((article_risk, title))
            
            total_risk += article_risk
        
        # Normalize risk score to 0-100
        total_risk = min(total_risk, 10)
        risk_score = int((total_risk / 10) * 100)
        
        # Generate summary from top articles
        summary = ""
        if top_articles:
            top_articles.sort(key=lambda x: x[0], reverse=True)
            top_titles = [title for _, title in top_articles][:2]
            
            if top_titles:
                summary = top_titles[0].strip()
                if summary and summary[-1] not in ".!?":
                    summary += "."
                
                if len(top_titles) > 1:
                    summary += " " + top_titles[1].strip()
                    if summary and summary[-1] not in ".!?":
                        summary += "."
        
        # Extract top keywords
        top_keywords = []
        if keyword_freq:
            sorted_keywords = sorted(keyword_freq.items(), key=lambda x: (-x[1], x[0]))
            top_keywords = [kw.capitalize() for kw, _ in sorted_keywords[:5]]
        
        return risk_score, top_keywords, summary
    
    def _determine_severity(self, risk_score: int) -> str:
        """
        Determine severity level based on risk score
        """
        if risk_score >= 80:
            return 'critical'
        elif risk_score >= 65:
            return 'high'
        elif risk_score >= 50:
            return 'medium'
        else:
            return 'low'
