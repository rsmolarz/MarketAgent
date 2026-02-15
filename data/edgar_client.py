"""
SEC EDGAR API client for distressed debt analysis.

Fetches 10-K, 10-Q, and 8-K filings using SEC EDGAR's RESTful APIs.
No authentication required; real-time updates with <1 second delay.

Uses the Extract-Contextualize-Load (ECL) paradigm with LLM-powered
parsing and Pydantic schema constraints for structured outputs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# SEC requires a User-Agent header with company/contact info
SEC_HEADERS = {
    "User-Agent": "MarketAgent/1.0 (market-agent@example.com)",
    "Accept": "application/json",
}

EDGAR_BASE = "https://data.sec.gov"
EDGAR_EFTS = "https://efts.sec.gov/LATEST"
EDGAR_COMPANY = f"{EDGAR_BASE}/submissions"


@dataclass
class SECFiling:
    """Parsed SEC filing."""
    accession_number: str
    form_type: str  # 10-K, 10-Q, 8-K, etc.
    filing_date: str
    company_name: str
    cik: str
    ticker: Optional[str] = None
    primary_document_url: Optional[str] = None
    description: str = ""
    extracted_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompanyFinancials:
    """Structured financial data extracted from filings."""
    cik: str
    company_name: str
    ticker: Optional[str] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_debt: Optional[float] = None
    cash_equivalents: Optional[float] = None
    ebitda: Optional[float] = None
    interest_expense: Optional[float] = None
    working_capital: Optional[float] = None
    shares_outstanding: Optional[float] = None
    filing_date: Optional[str] = None
    period_end: Optional[str] = None


class EdgarClient:
    """
    Client for SEC EDGAR API.

    Provides:
    - Company lookup by ticker or CIK
    - Filing retrieval (10-K, 10-Q, 8-K)
    - Full-text search across filings
    - LLM-powered financial data extraction (ECL paradigm)
    """

    # Rate limiting: SEC allows 10 requests/second
    _last_request_time: float = 0
    _min_interval: float = 0.12  # ~8 requests/second to stay safe

    def __init__(
        self,
        llm_extractor: Optional[Callable[..., Coroutine]] = None,
    ):
        """
        Args:
            llm_extractor: Async callable for LLM-powered data extraction.
                          Takes (text: str, schema: dict) -> dict.
        """
        self.llm_extractor = llm_extractor

    def _rate_limit(self) -> None:
        """Enforce SEC rate limits."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.monotonic()

    def _get(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a rate-limited GET request to SEC EDGAR."""
        self._rate_limit()
        try:
            resp = requests.get(url, headers=SEC_HEADERS, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"EDGAR request failed: {url} - {e}")
            return {}

    def lookup_company(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Look up a company by ticker symbol.
        Returns CIK, company name, and basic info.
        """
        # Use the company tickers endpoint
        url = f"{EDGAR_BASE}/files/company_tickers.json"
        try:
            data = self._get(url)
            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    cik = str(entry["cik_str"]).zfill(10)
                    return {
                        "cik": cik,
                        "ticker": entry["ticker"],
                        "company_name": entry["title"],
                    }
        except Exception as e:
            logger.error(f"Company lookup failed for {ticker}: {e}")
        return None

    def get_filings(
        self,
        cik: str,
        form_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[SECFiling]:
        """
        Get recent filings for a company.

        Args:
            cik: 10-digit CIK number (zero-padded).
            form_types: Filter by form type (e.g., ["10-K", "10-Q", "8-K"]).
            limit: Maximum number of filings to return.
        """
        url = f"{EDGAR_COMPANY}/CIK{cik.zfill(10)}.json"
        data = self._get(url)

        if not data:
            return []

        company_name = data.get("name", "")
        ticker = data.get("tickers", [""])[0] if data.get("tickers") else ""
        recent = data.get("filings", {}).get("recent", {})

        filings = []
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        descriptions = recent.get("primaryDocDescription", [])

        for i in range(min(len(forms), limit * 3)):  # Over-fetch to filter
            if form_types and forms[i] not in form_types:
                continue

            accession = accessions[i].replace("-", "")
            doc_url = f"{EDGAR_BASE}/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{primary_docs[i]}" if i < len(primary_docs) else None

            filings.append(SECFiling(
                accession_number=accessions[i],
                form_type=forms[i],
                filing_date=dates[i] if i < len(dates) else "",
                company_name=company_name,
                cik=cik,
                ticker=ticker,
                primary_document_url=doc_url,
                description=descriptions[i] if i < len(descriptions) else "",
            ))

            if len(filings) >= limit:
                break

        return filings

    def search_filings(
        self,
        query: str,
        form_types: Optional[List[str]] = None,
        date_range: Optional[tuple] = None,
        limit: int = 20,
    ) -> List[SECFiling]:
        """
        Full-text search across SEC filings.

        Args:
            query: Search query (e.g., "chapter 11 bankruptcy").
            form_types: Filter by form type.
            date_range: Tuple of (start_date, end_date) as strings "YYYY-MM-DD".
            limit: Maximum results.
        """
        url = f"{EDGAR_EFTS}/search-index"
        params: Dict[str, Any] = {
            "q": query,
            "dateRange": "custom",
            "startdt": date_range[0] if date_range else "2020-01-01",
            "enddt": date_range[1] if date_range else datetime.now().strftime("%Y-%m-%d"),
        }
        if form_types:
            params["forms"] = ",".join(form_types)

        data = self._get(url, params)
        hits = data.get("hits", {}).get("hits", [])

        filings = []
        for hit in hits[:limit]:
            source = hit.get("_source", {})
            filings.append(SECFiling(
                accession_number=source.get("file_num", ""),
                form_type=source.get("form_type", ""),
                filing_date=source.get("file_date", ""),
                company_name=source.get("display_names", [""])[0] if source.get("display_names") else "",
                cik=source.get("entity_id", ""),
                description=source.get("display_date_filed", ""),
            ))

        return filings

    def get_company_facts(self, cik: str) -> Dict[str, Any]:
        """
        Get XBRL company facts (structured financial data).

        Returns standardized financial line items from filings.
        """
        url = f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
        return self._get(url)

    def extract_financials(self, cik: str) -> Optional[CompanyFinancials]:
        """
        Extract key financial metrics from XBRL company facts.

        Pulls the most recent annual filing data.
        """
        facts = self.get_company_facts(cik)
        if not facts:
            return None

        company_name = facts.get("entityName", "")
        us_gaap = facts.get("facts", {}).get("us-gaap", {})

        def _get_recent_value(concept: str) -> Optional[float]:
            """Get most recent annual value for a concept."""
            concept_data = us_gaap.get(concept, {})
            units = concept_data.get("units", {})
            usd_values = units.get("USD", [])
            if not usd_values:
                return None
            # Filter for annual (10-K) and get most recent
            annual = [v for v in usd_values if v.get("form") == "10-K"]
            if not annual:
                annual = usd_values
            annual.sort(key=lambda x: x.get("end", ""), reverse=True)
            return annual[0]["val"] if annual else None

        return CompanyFinancials(
            cik=cik,
            company_name=company_name,
            revenue=_get_recent_value("Revenues") or _get_recent_value("RevenueFromContractWithCustomerExcludingAssessedTax"),
            net_income=_get_recent_value("NetIncomeLoss"),
            total_assets=_get_recent_value("Assets"),
            total_liabilities=_get_recent_value("Liabilities"),
            total_debt=_get_recent_value("LongTermDebt") or _get_recent_value("LongTermDebtNoncurrent"),
            cash_equivalents=_get_recent_value("CashAndCashEquivalentsAtCarryingValue"),
            interest_expense=_get_recent_value("InterestExpense"),
            shares_outstanding=_get_recent_value("CommonStockSharesOutstanding"),
        )

    async def extract_with_llm(
        self,
        filing: SECFiling,
        extraction_schema: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Use LLM to extract structured data from filing text (ECL paradigm).

        Args:
            filing: The filing to extract from.
            extraction_schema: Dict mapping field names to descriptions.
        """
        if not self.llm_extractor:
            logger.warning("No LLM extractor configured")
            return {}

        if not filing.primary_document_url:
            return {}

        # Fetch filing text
        self._rate_limit()
        try:
            resp = requests.get(
                filing.primary_document_url,
                headers=SEC_HEADERS,
                timeout=60,
            )
            text = resp.text[:50000]  # Limit to first 50K chars
        except Exception as e:
            logger.error(f"Failed to fetch filing document: {e}")
            return {}

        # LLM extraction
        try:
            result = await self.llm_extractor(text, extraction_schema)
            filing.extracted_data = result
            return result
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {}
