"""
Distressed Asset IC Memo Service

Generates investment committee memos for distressed property deals.
Includes underwriting analysis, risk assessment, and deal thesis.
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

IC_MEMO_PROMPT = """You are an investment analyst specializing in distressed real estate.
Generate a concise IC (Investment Committee) memo for the following property deal.

PROPERTY DETAILS:
Address: {address}
City/State: {city}, {state}
Property Type: {property_type}
Distress Type: {distress_type}

FINANCIALS:
Asking Price: ${asking_price:,.0f}
Estimated Market Value: ${estimated_value:,.0f}
Discount to Market: {discount_pct:.1f}%
{offer_section}

AGENT ANALYSIS:
Source: {source_agent}
Confidence: {confidence:.0%}
Signal Type: {signal_type}

ADDITIONAL CONTEXT:
{metadata_summary}

---

Generate a structured IC memo with these sections:

## DEAL SUMMARY
One paragraph executive summary of the opportunity.

## INVESTMENT THESIS
Why this deal is attractive. Focus on:
- Discount to market value
- Exit strategy options
- Timeline to value realization

## RISK FACTORS
Key risks to underwrite:
- Property condition unknowns
- Title/lien issues
- Market risk
- Execution risk

## UNDERWRITING ASSUMPTIONS
- Renovation budget estimate
- Hold period
- Exit cap rate / sale price
- Target IRR

## RECOMMENDATION
ACT / WATCH / PASS with brief rationale.

## NEXT STEPS
If ACT: specific action items (site visit, title search, LOI terms)

Keep the memo under 500 words. Be direct and institutional in tone.
"""


def build_distressed_ic_memo(
    deal_data: Dict[str, Any],
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Build IC memo for a distressed property deal.
    
    Args:
        deal_data: Deal information dict
        use_llm: Whether to use LLM for generation (vs template)
    
    Returns:
        Memo dict with content and metadata
    """
    address = deal_data.get("property_address", "Unknown")
    city = deal_data.get("city", "Unknown")
    state = deal_data.get("state", "")
    property_type = deal_data.get("property_type", "Unknown")
    distress_type = deal_data.get("distress_type", "Unknown")
    
    asking_price = deal_data.get("asking_price") or 0
    estimated_value = deal_data.get("estimated_value") or asking_price
    
    if estimated_value > 0 and asking_price > 0:
        discount_pct = (estimated_value - asking_price) / estimated_value * 100
    else:
        discount_pct = 0
    
    offer_price = deal_data.get("offer_price")
    offer_section = ""
    if offer_price:
        offer_section = f"Proposed Offer: ${offer_price:,.0f}"
    
    metadata = deal_data.get("metadata") or deal_data.get("deal_metadata") or {}
    metadata_summary = _summarize_metadata(metadata)
    
    source_agent = deal_data.get("source_agent", "DistressedPropertyAgent")
    confidence = deal_data.get("confidence", 0.7)
    signal_type = metadata.get("signal_type", "opportunity")
    
    if use_llm:
        memo_content = _generate_llm_memo(
            address=address,
            city=city,
            state=state,
            property_type=property_type,
            distress_type=distress_type,
            asking_price=asking_price,
            estimated_value=estimated_value,
            discount_pct=discount_pct,
            offer_section=offer_section,
            source_agent=source_agent,
            confidence=confidence,
            signal_type=signal_type,
            metadata_summary=metadata_summary
        )
    else:
        memo_content = _generate_template_memo(
            address=address,
            city=city,
            state=state,
            property_type=property_type,
            distress_type=distress_type,
            asking_price=asking_price,
            estimated_value=estimated_value,
            discount_pct=discount_pct,
            offer_section=offer_section,
            source_agent=source_agent,
            confidence=confidence,
            signal_type=signal_type
        )
    
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "property": f"{address}, {city}, {state}",
        "discount_pct": round(discount_pct, 1),
        "content": memo_content,
        "llm_generated": use_llm,
        "source_agent": source_agent,
        "recommendation": _extract_recommendation(memo_content)
    }


def _generate_llm_memo(
    address: str,
    city: str,
    state: str,
    property_type: str,
    distress_type: str,
    asking_price: float,
    estimated_value: float,
    discount_pct: float,
    offer_section: str,
    source_agent: str,
    confidence: float,
    signal_type: str,
    metadata_summary: str
) -> str:
    """Generate IC memo using LLM."""
    try:
        from openai import OpenAI
        
        client = OpenAI()
        
        prompt = IC_MEMO_PROMPT.format(
            address=address,
            city=city,
            state=state,
            property_type=property_type,
            distress_type=distress_type,
            asking_price=asking_price,
            estimated_value=estimated_value,
            discount_pct=discount_pct,
            offer_section=offer_section,
            source_agent=source_agent,
            confidence=confidence,
            signal_type=signal_type,
            metadata_summary=metadata_summary
        )
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an institutional real estate investment analyst."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"LLM IC memo generation failed: {e}")
        return _generate_template_memo(
            address=address,
            city=city,
            state=state,
            property_type=property_type,
            distress_type=distress_type,
            asking_price=asking_price,
            estimated_value=estimated_value,
            discount_pct=discount_pct,
            offer_section=offer_section,
            source_agent=source_agent,
            confidence=confidence,
            signal_type=signal_type
        )


def _generate_template_memo(
    address: str,
    city: str,
    state: str,
    property_type: str,
    distress_type: str,
    asking_price: float,
    estimated_value: float,
    discount_pct: float,
    offer_section: str,
    source_agent: str,
    confidence: float,
    signal_type: str
) -> str:
    """Generate IC memo using template (fallback)."""
    recommendation = "ACT" if discount_pct > 25 and confidence > 0.6 else "WATCH" if discount_pct > 15 else "PASS"
    
    return f"""## DEAL SUMMARY
{property_type} property at {address}, {city}, {state} available via {distress_type} at ${asking_price:,.0f}. 
Estimated market value: ${estimated_value:,.0f} ({discount_pct:.1f}% discount).

## INVESTMENT THESIS
- Deep discount of {discount_pct:.1f}% to estimated market value
- {distress_type.title()} status suggests motivated seller
- Multiple exit strategies: flip, rent, wholesale

## RISK FACTORS
- Property condition unknown - requires inspection
- Title/lien status unverified
- {state} market conditions to be assessed
- Execution timeline risk

## UNDERWRITING ASSUMPTIONS
- Renovation estimate: 10-15% of purchase price
- Hold period: 6-12 months
- Target exit: ${estimated_value * 0.95:,.0f}
- Target IRR: 20%+

## RECOMMENDATION
**{recommendation}**

{offer_section if offer_section else 'Proceed with preliminary underwriting.'}

## NEXT STEPS
1. Order title search
2. Schedule property inspection
3. Prepare LOI at ${asking_price * 0.9:,.0f} (10% below ask)
4. Due diligence checklist

---
Generated by {source_agent} | Confidence: {confidence:.0%} | Signal: {signal_type}
"""


def _summarize_metadata(metadata: Dict[str, Any]) -> str:
    """Summarize deal metadata for prompt."""
    if not metadata:
        return "No additional context available."
    
    lines = []
    
    if "price_per_sqft" in metadata:
        lines.append(f"Price/sqft: ${metadata['price_per_sqft']:.0f}")
    if "market_avg_ppsf" in metadata:
        lines.append(f"Market avg price/sqft: ${metadata['market_avg_ppsf']:.0f}")
    if "sqft" in metadata:
        lines.append(f"Square feet: {metadata['sqft']:,}")
    if "bedrooms" in metadata:
        lines.append(f"Bedrooms: {metadata['bedrooms']}")
    if "year_built" in metadata:
        lines.append(f"Year built: {metadata['year_built']}")
    if "days_on_market" in metadata:
        lines.append(f"Days on market: {metadata['days_on_market']}")
    if "auction_date" in metadata:
        lines.append(f"Auction date: {metadata['auction_date']}")
    
    return "\n".join(lines) if lines else "No additional context available."


def _extract_recommendation(content: str) -> str:
    """Extract recommendation from memo content."""
    content_upper = content.upper()
    
    if "**ACT**" in content_upper or "RECOMMENDATION\nACT" in content_upper:
        return "ACT"
    elif "**WATCH**" in content_upper or "RECOMMENDATION\nWATCH" in content_upper:
        return "WATCH"
    elif "**PASS**" in content_upper or "RECOMMENDATION\nPASS" in content_upper:
        return "PASS"
    
    return "WATCH"


def generate_memo_for_deal(deal_id: int, use_llm: bool = True) -> Optional[Dict[str, Any]]:
    """
    Generate IC memo for an existing deal.
    
    Args:
        deal_id: Database ID of the deal
        use_llm: Whether to use LLM generation
    
    Returns:
        Memo dict or None if deal not found
    """
    from models import DistressedDeal, db
    
    deal = DistressedDeal.query.get(deal_id)
    if not deal:
        return None
    
    memo = build_distressed_ic_memo(deal.to_dict(), use_llm=use_llm)
    
    deal.ic_memo = memo["content"]
    deal.ic_memo_generated_at = datetime.utcnow()
    db.session.commit()
    
    return memo
