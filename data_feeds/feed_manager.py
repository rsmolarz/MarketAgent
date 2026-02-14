"""
Distressed Asset Data Feed Manager
==================================
Unified interface for multiple distressed investing data sources.

Supported Sources:
- Debtwire/Reorg Research (deal flow)
- Bloomberg/Refinitiv (market data)
- PACER (court filings)
- SEC EDGAR (company filings)
- News/Sentiment feeds
- Trade claim platforms
"""

import os
import json
import logging
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
import time

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    DEAL_FLOW = "deal_flow"           # Debtwire, Reorg Research
    MARKET_DATA = "market_data"       # Bloomberg, Refinitiv
    COURT_FILINGS = "court_filings"   # PACER
    SEC_FILINGS = "sec_filings"       # EDGAR
    NEWS = "news"                      # News/sentiment
    TRADE_CLAIMS = "trade_claims"     # Claim trading platforms


@dataclass
class DataFeedConfig:
    """Configuration for a data feed."""
    name: str
    source_type: DataSourceType
    base_url: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    rate_limit: int = 60  # requests per minute
    timeout: int = 30
    retry_count: int = 3
    enabled: bool = True
    custom_headers: Dict[str, str] = field(default_factory=dict)
    field_mapping: Dict[str, str] = field(default_factory=dict)


@dataclass
class FeedItem:
    """Normalized data item from any feed."""
    id: str
    source: str
    source_type: str
    timestamp: str
    company_name: Optional[str] = None
    ticker: Optional[str] = None
    cusip: Optional[str] = None
    isin: Optional[str] = None
    data_type: str = "unknown"  # deal, filing, price, news, claim
    raw_data: Dict[str, Any] = field(default_factory=dict)
    normalized_data: Dict[str, Any] = field(default_factory=dict)


class BaseDataFeed(ABC):
    """Abstract base class for all data feeds."""
    
    def __init__(self, config: DataFeedConfig):
        self.config = config
        self.last_request_time = 0
        self._request_count = 0
        self._cache: Dict[str, Any] = {}
    
    @abstractmethod
    def fetch(self, **kwargs) -> List[FeedItem]:
        """Fetch data from the source."""
        pass
    
    @abstractmethod
    def normalize(self, raw_data: Dict[str, Any]) -> FeedItem:
        """Normalize raw data to standard format."""
        pass
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        min_interval = 60.0 / self.config.rate_limit
        elapsed = time.time() - self.last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
    
    def _cache_key(self, **kwargs) -> str:
        """Generate cache key from parameters."""
        return hashlib.md5(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()
    
    def _get_cached(self, key: str, max_age: int = 300) -> Optional[Any]:
        """Get cached result if not expired."""
        if key in self._cache:
            cached_time, data = self._cache[key]
            if time.time() - cached_time < max_age:
                return data
        return None
    
    def _set_cached(self, key: str, data: Any):
        """Cache result with timestamp."""
        self._cache[key] = (time.time(), data)


class DebtwireFeed(BaseDataFeed):
    """
    Debtwire/Reorg Research style deal flow feed.
    Provides distressed deal intelligence, restructuring news.
    """
    
    def fetch(self, **kwargs) -> List[FeedItem]:
        """Fetch distressed deals."""
        self._rate_limit()
        
        # Check cache
        cache_key = self._cache_key(**kwargs)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                **self.config.custom_headers
            }
            
            params = {
                "status": kwargs.get("status", "active"),
                "sector": kwargs.get("sector"),
                "min_debt": kwargs.get("min_debt"),
                "date_from": kwargs.get("date_from"),
            }
            params = {k: v for k, v in params.items() if v is not None}
            
            response = requests.get(
                f"{self.config.base_url}/deals",
                headers=headers,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            raw_deals = response.json()
            if isinstance(raw_deals, dict):
                raw_deals = raw_deals.get("deals", raw_deals.get("data", []))
            
            items = [self.normalize(deal) for deal in raw_deals]
            self._set_cached(cache_key, items)
            return items
            
        except Exception as e:
            logger.error(f"[DebtwireFeed] Fetch error: {e}")
            return []
    
    def normalize(self, raw_data: Dict[str, Any]) -> FeedItem:
        """Normalize deal data."""
        mapping = self.config.field_mapping or {}
        
        return FeedItem(
            id=str(raw_data.get(mapping.get("id", "deal_id"), raw_data.get("id", ""))),
            source=self.config.name,
            source_type=self.config.source_type.value,
            timestamp=raw_data.get(mapping.get("timestamp", "updated_at"), datetime.utcnow().isoformat()),
            company_name=raw_data.get(mapping.get("company", "company_name")),
            ticker=raw_data.get(mapping.get("ticker", "ticker")),
            cusip=raw_data.get(mapping.get("cusip", "cusip")),
            data_type="deal",
            raw_data=raw_data,
            normalized_data={
                "deal_type": raw_data.get("deal_type", "restructuring"),
                "status": raw_data.get("status"),
                "total_debt": raw_data.get("total_debt"),
                "industry": raw_data.get("industry", raw_data.get("sector")),
                "chapter": raw_data.get("chapter"),  # 7, 11, etc.
                "filing_date": raw_data.get("filing_date"),
                "advisors": raw_data.get("advisors", {}),
                "key_dates": raw_data.get("key_dates", []),
            }
        )


class BloombergFeed(BaseDataFeed):
    """
    Bloomberg/Refinitiv style market data feed.
    Provides bond prices, spreads, ratings.
    """
    
    def fetch(self, **kwargs) -> List[FeedItem]:
        """Fetch market data for securities."""
        self._rate_limit()
        
        securities = kwargs.get("securities", [])  # List of CUSIPs/ISINs
        fields = kwargs.get("fields", ["PX_LAST", "YLD_YTM_MID", "RTG_SP", "RTG_MOODY"])
        
        cache_key = self._cache_key(securities=securities, fields=fields)
        cached = self._get_cached(cache_key, max_age=60)  # 1 minute cache for prices
        if cached:
            return cached
        
        try:
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                **self.config.custom_headers
            }
            
            payload = {
                "securities": securities,
                "fields": fields,
            }
            
            response = requests.post(
                f"{self.config.base_url}/data",
                headers=headers,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            raw_data = response.json()
            items = []
            
            for security_data in raw_data.get("securities", []):
                items.append(self.normalize(security_data))
            
            self._set_cached(cache_key, items)
            return items
            
        except Exception as e:
            logger.error(f"[BloombergFeed] Fetch error: {e}")
            return []
    
    def normalize(self, raw_data: Dict[str, Any]) -> FeedItem:
        """Normalize market data."""
        security_id = raw_data.get("security", raw_data.get("cusip", raw_data.get("isin", "")))
        
        return FeedItem(
            id=security_id,
            source=self.config.name,
            source_type=self.config.source_type.value,
            timestamp=datetime.utcnow().isoformat(),
            cusip=raw_data.get("cusip"),
            isin=raw_data.get("isin"),
            ticker=raw_data.get("ticker"),
            data_type="price",
            raw_data=raw_data,
            normalized_data={
                "price": raw_data.get("PX_LAST", raw_data.get("price")),
                "yield_to_maturity": raw_data.get("YLD_YTM_MID", raw_data.get("ytm")),
                "spread": raw_data.get("SPREAD", raw_data.get("oas_spread")),
                "rating_sp": raw_data.get("RTG_SP", raw_data.get("sp_rating")),
                "rating_moody": raw_data.get("RTG_MOODY", raw_data.get("moody_rating")),
                "bid": raw_data.get("PX_BID", raw_data.get("bid")),
                "ask": raw_data.get("PX_ASK", raw_data.get("ask")),
                "volume": raw_data.get("VOLUME", raw_data.get("volume")),
            }
        )


class PACERFeed(BaseDataFeed):
    """
    PACER court filings feed.
    Monitors bankruptcy court dockets.
    """
    
    BANKRUPTCY_COURTS = [
        "deb",   # Delaware
        "nysb",  # Southern District of New York
        "txsb",  # Southern District of Texas
        "casb",  # Central District of California
    ]
    
    def fetch(self, **kwargs) -> List[FeedItem]:
        """Fetch court filings."""
        self._rate_limit()
        
        case_number = kwargs.get("case_number")
        court = kwargs.get("court", "deb")
        date_from = kwargs.get("date_from")
        filing_types = kwargs.get("filing_types", ["plan", "disclosure", "motion"])
        
        cache_key = self._cache_key(**kwargs)
        cached = self._get_cached(cache_key, max_age=900)  # 15 min cache
        if cached:
            return cached
        
        try:
            import requests
            
            headers = {
                "Authorization": f"Basic {self.config.api_key}",
                **self.config.custom_headers
            }
            
            params = {
                "case_number": case_number,
                "court": court,
                "date_filed_from": date_from,
                "type": ",".join(filing_types),
            }
            params = {k: v for k, v in params.items() if v is not None}
            
            response = requests.get(
                f"{self.config.base_url}/filings",
                headers=headers,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            raw_filings = response.json()
            if isinstance(raw_filings, dict):
                raw_filings = raw_filings.get("filings", raw_filings.get("documents", []))
            
            items = [self.normalize(filing) for filing in raw_filings]
            self._set_cached(cache_key, items)
            return items
            
        except Exception as e:
            logger.error(f"[PACERFeed] Fetch error: {e}")
            return []
    
    def normalize(self, raw_data: Dict[str, Any]) -> FeedItem:
        """Normalize court filing data."""
        return FeedItem(
            id=str(raw_data.get("document_id", raw_data.get("docket_number", ""))),
            source=self.config.name,
            source_type=self.config.source_type.value,
            timestamp=raw_data.get("date_filed", datetime.utcnow().isoformat()),
            company_name=raw_data.get("debtor_name", raw_data.get("case_title")),
            data_type="filing",
            raw_data=raw_data,
            normalized_data={
                "case_number": raw_data.get("case_number"),
                "court": raw_data.get("court"),
                "filing_type": raw_data.get("type", raw_data.get("filing_type")),
                "title": raw_data.get("title", raw_data.get("description")),
                "date_filed": raw_data.get("date_filed"),
                "docket_number": raw_data.get("docket_number"),
                "document_url": raw_data.get("document_url", raw_data.get("pdf_url")),
                "is_plan": "plan" in raw_data.get("type", "").lower(),
                "is_disclosure": "disclosure" in raw_data.get("type", "").lower(),
                "key_deadlines": raw_data.get("deadlines", []),
            }
        )


class SECEdgarFeed(BaseDataFeed):
    """
    SEC EDGAR filings feed.
    Monitors 8-K, 10-K, 10-Q, proxy statements.
    """
    
    DISTRESSED_FORM_TYPES = ["8-K", "10-K", "10-Q", "NT 10-K", "NT 10-Q", "13D", "13G"]
    
    def fetch(self, **kwargs) -> List[FeedItem]:
        """Fetch SEC filings."""
        self._rate_limit()
        
        cik = kwargs.get("cik")
        ticker = kwargs.get("ticker")
        form_types = kwargs.get("form_types", self.DISTRESSED_FORM_TYPES)
        date_from = kwargs.get("date_from")
        
        cache_key = self._cache_key(**kwargs)
        cached = self._get_cached(cache_key, max_age=1800)  # 30 min cache
        if cached:
            return cached
        
        try:
            import requests
            
            # SEC EDGAR API (no auth required, but rate limited)
            headers = {
                "User-Agent": self.config.custom_headers.get("User-Agent", "DistressedInvestor/1.0"),
                **self.config.custom_headers
            }
            
            # Build query
            if cik:
                url = f"{self.config.base_url}/cik/{cik}/filings"
            elif ticker:
                url = f"{self.config.base_url}/ticker/{ticker}/filings"
            else:
                url = f"{self.config.base_url}/filings/recent"
            
            params = {
                "type": ",".join(form_types),
                "dateb": date_from,
            }
            params = {k: v for k, v in params.items() if v is not None}
            
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            raw_filings = response.json()
            if isinstance(raw_filings, dict):
                raw_filings = raw_filings.get("filings", raw_filings.get("results", []))
            
            items = [self.normalize(filing) for filing in raw_filings]
            self._set_cached(cache_key, items)
            return items
            
        except Exception as e:
            logger.error(f"[SECEdgarFeed] Fetch error: {e}")
            return []
    
    def normalize(self, raw_data: Dict[str, Any]) -> FeedItem:
        """Normalize SEC filing data."""
        return FeedItem(
            id=raw_data.get("accession_number", raw_data.get("accessionNumber", "")),
            source=self.config.name,
            source_type=self.config.source_type.value,
            timestamp=raw_data.get("filedAt", raw_data.get("filing_date", datetime.utcnow().isoformat())),
            company_name=raw_data.get("companyName", raw_data.get("company_name")),
            ticker=raw_data.get("ticker"),
            data_type="sec_filing",
            raw_data=raw_data,
            normalized_data={
                "form_type": raw_data.get("formType", raw_data.get("form_type")),
                "cik": raw_data.get("cik"),
                "filing_date": raw_data.get("filedAt", raw_data.get("filing_date")),
                "document_url": raw_data.get("documentUrl", raw_data.get("url")),
                "description": raw_data.get("description"),
                "items": raw_data.get("items", []),  # 8-K items
                "is_nt": raw_data.get("formType", "").startswith("NT"),  # Late filing
                "is_restatement": "restat" in raw_data.get("description", "").lower(),
            }
        )


class NewsFeed(BaseDataFeed):
    """
    News and sentiment feed.
    Monitors distressed/restructuring news.
    """
    
    DISTRESS_KEYWORDS = [
        "bankruptcy", "chapter 11", "chapter 7", "restructuring",
        "default", "distressed", "creditor", "bondholder",
        "covenant breach", "liquidity crisis", "debt exchange"
    ]
    
    def fetch(self, **kwargs) -> List[FeedItem]:
        """Fetch news articles."""
        self._rate_limit()
        
        query = kwargs.get("query")
        company = kwargs.get("company")
        keywords = kwargs.get("keywords", self.DISTRESS_KEYWORDS)
        date_from = kwargs.get("date_from")
        
        cache_key = self._cache_key(**kwargs)
        cached = self._get_cached(cache_key, max_age=300)  # 5 min cache
        if cached:
            return cached
        
        try:
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                **self.config.custom_headers
            }
            
            # Build query
            search_query = query or company
            if not search_query and keywords:
                search_query = " OR ".join(keywords[:5])
            
            params = {
                "q": search_query,
                "from": date_from,
                "sortBy": "publishedAt",
                "language": "en",
            }
            params = {k: v for k, v in params.items() if v is not None}
            
            response = requests.get(
                f"{self.config.base_url}/everything",
                headers=headers,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            raw_articles = response.json()
            if isinstance(raw_articles, dict):
                raw_articles = raw_articles.get("articles", [])
            
            items = [self.normalize(article) for article in raw_articles]
            self._set_cached(cache_key, items)
            return items
            
        except Exception as e:
            logger.error(f"[NewsFeed] Fetch error: {e}")
            return []
    
    def normalize(self, raw_data: Dict[str, Any]) -> FeedItem:
        """Normalize news article."""
        # Simple sentiment scoring
        title = raw_data.get("title", "").lower()
        description = raw_data.get("description", "").lower()
        content = f"{title} {description}"
        
        negative_words = ["bankruptcy", "default", "crisis", "collapse", "fraud", "layoff"]
        positive_words = ["recovery", "turnaround", "settlement", "emergence", "approval"]
        
        neg_score = sum(1 for w in negative_words if w in content)
        pos_score = sum(1 for w in positive_words if w in content)
        sentiment = (pos_score - neg_score) / max(pos_score + neg_score, 1)
        
        return FeedItem(
            id=raw_data.get("url", raw_data.get("id", "")),
            source=self.config.name,
            source_type=self.config.source_type.value,
            timestamp=raw_data.get("publishedAt", datetime.utcnow().isoformat()),
            company_name=raw_data.get("company"),
            data_type="news",
            raw_data=raw_data,
            normalized_data={
                "title": raw_data.get("title"),
                "description": raw_data.get("description"),
                "source_name": raw_data.get("source", {}).get("name"),
                "url": raw_data.get("url"),
                "published_at": raw_data.get("publishedAt"),
                "sentiment_score": round(sentiment, 2),
                "relevance_keywords": [k for k in self.DISTRESS_KEYWORDS if k in content],
            }
        )


class TradeClaimFeed(BaseDataFeed):
    """
    Trade claim platform feed.
    Monitors vendor/supplier claims available for purchase.
    """
    
    def fetch(self, **kwargs) -> List[FeedItem]:
        """Fetch available trade claims."""
        self._rate_limit()
        
        debtor = kwargs.get("debtor")
        min_amount = kwargs.get("min_amount")
        claim_type = kwargs.get("claim_type")  # trade, admin, priority
        
        cache_key = self._cache_key(**kwargs)
        cached = self._get_cached(cache_key, max_age=1800)
        if cached:
            return cached
        
        try:
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                **self.config.custom_headers
            }
            
            params = {
                "debtor": debtor,
                "min_amount": min_amount,
                "type": claim_type,
                "status": "available",
            }
            params = {k: v for k, v in params.items() if v is not None}
            
            response = requests.get(
                f"{self.config.base_url}/claims",
                headers=headers,
                params=params,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            raw_claims = response.json()
            if isinstance(raw_claims, dict):
                raw_claims = raw_claims.get("claims", [])
            
            items = [self.normalize(claim) for claim in raw_claims]
            self._set_cached(cache_key, items)
            return items
            
        except Exception as e:
            logger.error(f"[TradeClaimFeed] Fetch error: {e}")
            return []
    
    def normalize(self, raw_data: Dict[str, Any]) -> FeedItem:
        """Normalize trade claim data."""
        face_amount = raw_data.get("face_amount", 0)
        ask_price = raw_data.get("ask_price", 100)
        implied_recovery = (ask_price / 100) if face_amount > 0 else 0
        
        return FeedItem(
            id=raw_data.get("claim_id", raw_data.get("id", "")),
            source=self.config.name,
            source_type=self.config.source_type.value,
            timestamp=raw_data.get("listed_at", datetime.utcnow().isoformat()),
            company_name=raw_data.get("debtor_name"),
            data_type="trade_claim",
            raw_data=raw_data,
            normalized_data={
                "debtor_name": raw_data.get("debtor_name"),
                "case_number": raw_data.get("case_number"),
                "claim_type": raw_data.get("claim_type", "trade"),
                "face_amount": face_amount,
                "ask_price": ask_price,
                "bid_price": raw_data.get("bid_price"),
                "implied_recovery": implied_recovery,
                "claimant_name": raw_data.get("claimant_name"),
                "claim_number": raw_data.get("claim_number"),
                "priority": raw_data.get("priority", "general_unsecured"),
                "objection_deadline": raw_data.get("objection_deadline"),
            }
        )


class FeedManager:
    """
    Central manager for all data feeds.
    Handles registration, fetching, aggregation.
    """
    
    FEED_CLASSES = {
        DataSourceType.DEAL_FLOW: DebtwireFeed,
        DataSourceType.MARKET_DATA: BloombergFeed,
        DataSourceType.COURT_FILINGS: PACERFeed,
        DataSourceType.SEC_FILINGS: SECEdgarFeed,
        DataSourceType.NEWS: NewsFeed,
        DataSourceType.TRADE_CLAIMS: TradeClaimFeed,
    }
    
    def __init__(self):
        self.feeds: Dict[str, BaseDataFeed] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
        self._load_feeds_from_env()
    
    def _load_feeds_from_env(self):
        """Load feed configurations from environment variables."""
        # Load Debtwire/Deal Flow
        if os.getenv("DEBTWIRE_API_URL"):
            self.register_feed(DataFeedConfig(
                name="debtwire",
                source_type=DataSourceType.DEAL_FLOW,
                base_url=os.getenv("DEBTWIRE_API_URL"),
                api_key=os.getenv("DEBTWIRE_API_KEY"),
            ))
        
        # Load Bloomberg/Market Data
        if os.getenv("BLOOMBERG_API_URL"):
            self.register_feed(DataFeedConfig(
                name="bloomberg",
                source_type=DataSourceType.MARKET_DATA,
                base_url=os.getenv("BLOOMBERG_API_URL"),
                api_key=os.getenv("BLOOMBERG_API_KEY"),
            ))
        
        # Load PACER
        if os.getenv("PACER_API_URL"):
            self.register_feed(DataFeedConfig(
                name="pacer",
                source_type=DataSourceType.COURT_FILINGS,
                base_url=os.getenv("PACER_API_URL"),
                api_key=os.getenv("PACER_API_KEY"),
            ))
        
        # Load SEC EDGAR (free, always available)
        self.register_feed(DataFeedConfig(
            name="sec_edgar",
            source_type=DataSourceType.SEC_FILINGS,
            base_url=os.getenv("SEC_EDGAR_URL", "https://data.sec.gov"),
            rate_limit=10,  # SEC rate limits
            custom_headers={"User-Agent": os.getenv("SEC_USER_AGENT", "DistressedInvestor/1.0")},
        ))
        
        # Load News API
        if os.getenv("NEWS_API_KEY"):
            self.register_feed(DataFeedConfig(
                name="news",
                source_type=DataSourceType.NEWS,
                base_url=os.getenv("NEWS_API_URL", "https://newsapi.org/v2"),
                api_key=os.getenv("NEWS_API_KEY"),
            ))
        
        # Load Trade Claims
        if os.getenv("TRADE_CLAIMS_API_URL"):
            self.register_feed(DataFeedConfig(
                name="trade_claims",
                source_type=DataSourceType.TRADE_CLAIMS,
                base_url=os.getenv("TRADE_CLAIMS_API_URL"),
                api_key=os.getenv("TRADE_CLAIMS_API_KEY"),
            ))
    
    def register_feed(self, config: DataFeedConfig):
        """Register a new data feed."""
        feed_class = self.FEED_CLASSES.get(config.source_type)
        if feed_class:
            self.feeds[config.name] = feed_class(config)
            logger.info(f"[FeedManager] Registered feed: {config.name}")
    
    def unregister_feed(self, name: str):
        """Remove a data feed."""
        if name in self.feeds:
            del self.feeds[name]
            logger.info(f"[FeedManager] Unregistered feed: {name}")
    
    def get_feed(self, name: str) -> Optional[BaseDataFeed]:
        """Get a specific feed by name."""
        return self.feeds.get(name)
    
    def list_feeds(self) -> List[Dict[str, Any]]:
        """List all registered feeds."""
        return [
            {
                "name": name,
                "source_type": feed.config.source_type.value,
                "enabled": feed.config.enabled,
                "base_url": feed.config.base_url,
            }
            for name, feed in self.feeds.items()
        ]
    
    def fetch_all(self, source_type: Optional[DataSourceType] = None, **kwargs) -> List[FeedItem]:
        """
        Fetch from all feeds (optionally filtered by type).
        """
        results = []
        
        for name, feed in self.feeds.items():
            if not feed.config.enabled:
                continue
            if source_type and feed.config.source_type != source_type:
                continue
            
            try:
                items = feed.fetch(**kwargs)
                results.extend(items)
                logger.info(f"[FeedManager] Fetched {len(items)} items from {name}")
            except Exception as e:
                logger.error(f"[FeedManager] Error fetching from {name}: {e}")
        
        return results
    
    def fetch_deals(self, **kwargs) -> List[FeedItem]:
        """Fetch distressed deals from all deal flow sources."""
        return self.fetch_all(DataSourceType.DEAL_FLOW, **kwargs)
    
    def fetch_prices(self, securities: List[str], **kwargs) -> List[FeedItem]:
        """Fetch market prices for securities."""
        return self.fetch_all(DataSourceType.MARKET_DATA, securities=securities, **kwargs)
    
    def fetch_filings(self, case_number: Optional[str] = None, **kwargs) -> List[FeedItem]:
        """Fetch court and SEC filings."""
        court_filings = self.fetch_all(DataSourceType.COURT_FILINGS, case_number=case_number, **kwargs)
        sec_filings = self.fetch_all(DataSourceType.SEC_FILINGS, **kwargs)
        return court_filings + sec_filings
    
    def fetch_news(self, company: str, **kwargs) -> List[FeedItem]:
        """Fetch news for a company."""
        return self.fetch_all(DataSourceType.NEWS, company=company, **kwargs)
    
    def fetch_claims(self, debtor: Optional[str] = None, **kwargs) -> List[FeedItem]:
        """Fetch available trade claims."""
        return self.fetch_all(DataSourceType.TRADE_CLAIMS, debtor=debtor, **kwargs)
    
    def subscribe(self, source_type: DataSourceType, callback: Callable[[FeedItem], None]):
        """Subscribe to updates from a source type."""
        key = source_type.value
        if key not in self.callbacks:
            self.callbacks[key] = []
        self.callbacks[key].append(callback)
    
    def aggregate_company_data(self, company_name: str, ticker: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate all data for a company across feeds.
        Returns unified view for analysis.
        """
        result = {
            "company_name": company_name,
            "ticker": ticker,
            "deals": [],
            "prices": [],
            "court_filings": [],
            "sec_filings": [],
            "news": [],
            "claims": [],
            "last_updated": datetime.utcnow().isoformat(),
        }
        
        # Fetch from all sources
        for name, feed in self.feeds.items():
            try:
                if feed.config.source_type == DataSourceType.DEAL_FLOW:
                    items = feed.fetch(company=company_name)
                    result["deals"].extend([asdict(i) for i in items])
                    
                elif feed.config.source_type == DataSourceType.MARKET_DATA and ticker:
                    items = feed.fetch(securities=[ticker])
                    result["prices"].extend([asdict(i) for i in items])
                    
                elif feed.config.source_type == DataSourceType.COURT_FILINGS:
                    items = feed.fetch(debtor=company_name)
                    result["court_filings"].extend([asdict(i) for i in items])
                    
                elif feed.config.source_type == DataSourceType.SEC_FILINGS and ticker:
                    items = feed.fetch(ticker=ticker)
                    result["sec_filings"].extend([asdict(i) for i in items])
                    
                elif feed.config.source_type == DataSourceType.NEWS:
                    items = feed.fetch(company=company_name)
                    result["news"].extend([asdict(i) for i in items])
                    
                elif feed.config.source_type == DataSourceType.TRADE_CLAIMS:
                    items = feed.fetch(debtor=company_name)
                    result["claims"].extend([asdict(i) for i in items])
                    
            except Exception as e:
                logger.warning(f"[FeedManager] Error aggregating from {name}: {e}")
        
        return result

    def get_status(self) -> Dict[str, Any]:
                """Get status of all registered data feeds."""""
                status = {
                                "timestamp": datetime.utcnow().isoformat(),
                                "total_feeds": len(self.feeds),
                                "feeds": {}
                }

                for name, feed in self.feeds.items():
                                try:
                                                    feed_status = {
                                                                            "name": feed.config.name,
                                                                            "enabled": feed.config.enabled,
                                                                            "source_type": feed.config.source_type.value,
                                                                            "status": "healthy" if feed.config.enabled else "disabled",
                                                                            "last_request": feed.last_request_time,
                                                    }
                                                    status["feeds"][name] = feed_status
                                except Exception as e:
                                                    logger.error(f"[FeedManager] Error getting status for {name}: {e}")
                                                    status["feeds"][name] = {
                                                                            "name": name,
                                                                            "status": "error",
                                                                            "error": str(e)
                                                    }

                                            return status
                                                    }
                                                    }
                }


# Convenience function
def create_feed_manager() -> FeedManager:
    """Create and return a configured FeedManager."""
    return FeedManager()
