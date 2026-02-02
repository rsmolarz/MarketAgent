#!/usr/bin/env python3
"""
Backfill script to run existing findings through LLM Trade Council
and populate ta_council, fund_council, real_estate_council fields.
"""
import os
import sys
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Finding

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def call_trade_council(finding: Finding) -> dict:
    """Call LLM to analyze a finding and return ta/fund/real_estate verdicts."""
    from openai import OpenAI
    
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
    base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    
    if not api_key:
        return {"ta_council": None, "fund_council": None, "real_estate_council": None}
    
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    
    asset_type = "crypto" if any(c in (finding.symbol or "").upper() for c in ["BTC", "ETH", "SOL", "USDT", "USDC"]) else \
                 "real_estate" if "property" in (finding.agent_name or "").lower() or "distress" in (finding.agent_name or "").lower() else \
                 "equity"
    
    prompt = f"""You are a trading analyst reviewing market intelligence findings.

Finding Details:
- Agent: {finding.agent_name}
- Symbol: {finding.symbol}
- Title: {finding.title}
- Description: {finding.description[:500] if finding.description else 'N/A'}
- Severity: {finding.severity}
- Confidence: {finding.confidence}
- Asset Type: {asset_type}

Analyze this finding and provide two verdicts:

1. TECHNICAL ANALYSIS COUNCIL (ta_council): Based purely on price action, momentum, volume, and chart patterns implied by this finding, should we ACT (trade now), WATCH (monitor closely), or HOLD (no action)?

2. FUNDAMENTAL ANALYSIS COUNCIL (fund_council): Based on the underlying value proposition, market conditions, macro factors, and risk/reward implied by this finding, should we ACT, WATCH, or HOLD?

3. REAL ESTATE COUNCIL (real_estate_council): If this is a real estate finding, should we ACT, WATCH, or HOLD based on valuation, market conditions, and distress level? If not real estate, respond N/A.

Consider:
- High severity + high confidence findings lean toward ACT
- Medium findings lean toward WATCH
- Low priority or speculative findings lean toward HOLD
- Both councils agreeing on ACT = Action Required trigger

Respond ONLY in this exact format (no other text):
ta_council=ACT|WATCH|HOLD
fund_council=ACT|WATCH|HOLD
real_estate_council=ACT|WATCH|HOLD|N/A"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.2
        )
        
        text = response.choices[0].message.content or ""
        lines = text.strip().split("\n")
        
        result = {"ta_council": None, "fund_council": None, "real_estate_council": None}
        
        for line in lines:
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip().lower()
                val = val.strip().lower()
                
                if val in ["act", "watch", "hold"]:
                    if "ta" in key:
                        result["ta_council"] = val
                    elif "fund" in key:
                        result["fund_council"] = val
                    elif "real" in key:
                        result["real_estate_council"] = val
                elif val == "n/a" and "real" in key:
                    result["real_estate_council"] = None
        
        return result
        
    except Exception as e:
        logger.warning(f"Trade council call failed: {e}")
        return {"ta_council": None, "fund_council": None, "real_estate_council": None}


def backfill_findings(limit: int = 500, batch_size: int = 10):
    """Backfill recent findings with trade council verdicts."""
    
    with app.app_context():
        findings = Finding.query.filter(
            Finding.ta_council.is_(None),
            Finding.fund_council.is_(None)
        ).order_by(Finding.timestamp.desc()).limit(limit).all()
        
        logger.info(f"Found {len(findings)} findings to backfill")
        
        processed = 0
        act_count = 0
        
        for i, finding in enumerate(findings):
            try:
                verdicts = call_trade_council(finding)
                
                if verdicts["ta_council"]:
                    finding.ta_council = verdicts["ta_council"]
                if verdicts["fund_council"]:
                    finding.fund_council = verdicts["fund_council"]
                if verdicts["real_estate_council"]:
                    finding.real_estate_council = verdicts["real_estate_council"]
                
                if verdicts["ta_council"] == "act" and verdicts["fund_council"] == "act":
                    act_count += 1
                    logger.info(f"ACTION REQUIRED: {finding.agent_name} - {finding.title[:50]}")
                
                processed += 1
                
                if processed % batch_size == 0:
                    db.session.commit()
                    logger.info(f"Processed {processed}/{len(findings)} findings ({act_count} action required)")
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Error processing finding {finding.id}: {e}")
                continue
        
        db.session.commit()
        logger.info(f"Backfill complete: {processed} findings processed, {act_count} action required triggers")
        
        return processed, act_count


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    logger.info(f"Starting backfill of up to {limit} findings...")
    processed, act_count = backfill_findings(limit=limit)
    print(f"\nBackfill Summary:")
    print(f"  Findings processed: {processed}")
    print(f"  Action Required triggers: {act_count}")
