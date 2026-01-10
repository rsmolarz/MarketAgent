import os
import logging
import anthropic
from telemetry.context import get_current_run

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

ANALYSIS_SYSTEM_PROMPT = """You are an expert financial analyst and trading strategist with deep technical analysis expertise. When presented with a market alert or finding, provide a structured analysis with exactly three sections:

1. **Alert Summary**: A brief, plain-language explanation of what this alert means. Avoid technical jargon - explain it as you would to someone who understands investing basics but isn't a professional trader. Keep this to 2-3 sentences.

2. **Actionability Assessment**: Rate how actionable this alert is for a typical investor on a scale of Low/Medium/High. Consider:
   - How directly tradeable is the signal?
   - What is the time sensitivity?
   - How reliable is the underlying indicator?
   - Current confidence score and what it implies
   Provide a 2-3 sentence explanation of your rating.

3. **Trading Strategies**: Suggest 2-3 specific strategies that could capitalize on this finding. For EACH strategy, you MUST include:

   **Approach**: Clear step-by-step action plan
   
   **Entry Indicators**: Specific technical signals to confirm entry, such as:
   - RSI levels (e.g., "wait for RSI to cross above 30")
   - Moving average crossovers (e.g., "price closes above 20-day MA")
   - Volume confirmation (e.g., "above-average volume on reversal day")
   - MACD signals, Bollinger Band positions, or support/resistance levels
   
   **Exit Strategy**: Precise exit criteria including:
   - Profit target: specific percentage or price level (e.g., "3-5% gain" or "resistance at $X")
   - Stop-loss: specific percentage below entry (e.g., "2-3% below entry point")
   - Trailing stop guidance if applicable
   - Time-based exit if the trade doesn't work within expected timeframe
   
   **Risk Level**: Low/Medium/High with brief explanation
   
   **Timeframe**: Expected holding period (e.g., "1-2 weeks", "3-7 days")

Example strategy format:
**Strategy 1: Short-term Rebound Trade**
- **Approach**: Buy [SYMBOL] in anticipation of a technical bounce...
- **Entry Indicators**: Wait for RSI to cross back above 30, confirming momentum shift. Look for bullish candlestick pattern (hammer/doji) on daily chart with volume above 20-day average.
- **Exit Strategy**: Set profit target at 3-5% (near 50-day MA resistance). Place stop-loss 2-3% below entry. If no movement after 5 trading days, reassess position.
- **Risk Level**: Medium — relies on RSI signal being predictive of reversal
- **Timeframe**: 1-2 weeks

Keep your response focused and practical. Avoid excessive hedging language but do note significant risks."""


def analyze_alert_with_claude(finding_data: dict) -> dict:
    """
    Analyze a market finding/alert using Claude and return structured analysis.
    
    Args:
        finding_data: Dictionary containing the alert details (title, description, metadata, etc.)
    
    Returns:
        Dictionary with analysis results or error information
    """
    try:
        alert_text = f"""
Market Alert to Analyze:

Title: {finding_data.get('title', 'N/A')}
Agent: {finding_data.get('agent_name', 'N/A')}
Symbol: {finding_data.get('symbol', 'N/A')}
Severity: {finding_data.get('severity', 'N/A')}
Confidence: {finding_data.get('confidence', 'N/A')}
Market Type: {finding_data.get('market_type', 'N/A')}
Timestamp: {finding_data.get('timestamp', 'N/A')}

Description:
{finding_data.get('description', 'No description provided')}

Additional Metadata:
{_format_metadata(finding_data.get('metadata', {}))}
"""

        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": alert_text}
            ]
        )
        
        run = get_current_run()
        if run and hasattr(response, "usage") and response.usage:
            run.add_llm_usage(
                tokens_in=int(response.usage.input_tokens or 0),
                tokens_out=int(response.usage.output_tokens or 0),
                cost_usd=0.0
            )
        
        analysis_text = response.content[0].text if response.content else ""
        
        return {
            'success': True,
            'analysis': analysis_text,
            'model': 'claude-sonnet-4-20250514',
            'finding_id': finding_data.get('id'),
            'finding_title': finding_data.get('title')
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Claude analysis failed: {error_msg}")
        
        if "FREE_CLOUD_BUDGET_EXCEEDED" in error_msg:
            return {
                'success': False,
                'error': 'budget_exceeded',
                'message': 'Your cloud budget has been exceeded. Please upgrade your plan to continue using AI analysis.'
            }
        
        return {
            'success': False,
            'error': 'api_error',
            'message': f'Failed to analyze alert: {error_msg}'
        }


def analyze_alert_with_chatgpt(finding_data: dict) -> dict:
    """
    Main analysis function using the LLM Council.
    Kept for backward compatibility - now runs a 3-LLM council (GPT, Claude, Gemini).
    
    Returns structured consensus + narrative analysis from primary model.
    """
    try:
        from services.llm_council import analyze_with_council_sync
        
        council_result = analyze_with_council_sync(finding_data)
        
        if not council_result.get("ok") or not council_result.get("consensus"):
            logger.warning("LLM Council failed, falling back to Claude-only")
            return analyze_alert_with_claude(finding_data)
        
        consensus = council_result["consensus"]
        
        narrative_parts = []
        
        narrative_parts.append("**LLM Council Analysis**\n")
        narrative_parts.append(f"**Consensus Decision**: {consensus.get('verdict', 'WATCH')}")
        narrative_parts.append(f"**Confidence**: {consensus.get('confidence', 0.5):.1%}")
        if council_result.get("uncertainty_spike"):
            narrative_parts.append("⚠️ **High Uncertainty**: Models disagreed significantly\n")
        else:
            narrative_parts.append("")
        
        if consensus.get("one_paragraph_summary"):
            narrative_parts.append(f"**Summary**: {consensus['one_paragraph_summary']}\n")
        
        if consensus.get("key_drivers"):
            narrative_parts.append("**Key Drivers**:")
            for driver in consensus["key_drivers"][:5]:
                narrative_parts.append(f"- {driver}")
            narrative_parts.append("")
        
        if consensus.get("what_to_verify"):
            narrative_parts.append("**To Verify**:")
            for item in consensus["what_to_verify"][:4]:
                narrative_parts.append(f"- {item}")
            narrative_parts.append("")
        
        positioning = consensus.get("positioning", {})
        if positioning:
            narrative_parts.append(f"**Market Bias**: {positioning.get('bias', 'neutral').title()}")
            if positioning.get("suggested_actions"):
                narrative_parts.append("**Suggested Actions**:")
                for action in positioning["suggested_actions"][:3]:
                    narrative_parts.append(f"- {action}")
            narrative_parts.append("")
        
        narrative_parts.append(f"**Time Horizon**: {consensus.get('time_horizon', 'days').title()}")
        
        models_used = [m.get("model", "unknown") for m in council_result.get("models", []) if m.get("ok")]
        narrative_parts.append(f"\n*Analyzed by {len(models_used)} LLMs: {', '.join(models_used)}*")
        
        analysis_text = "\n".join(narrative_parts)
        
        return {
            'success': True,
            'analysis': analysis_text,
            'model': 'llm-council',
            'finding_id': finding_data.get('id'),
            'finding_title': finding_data.get('title'),
            'consensus': consensus.get('verdict', 'WATCH'),
            'confidence': consensus.get('confidence', 0.5),
            'uncertainty_spike': council_result.get('uncertainty_spike', False),
            'models_used': models_used,
            'votes': council_result.get('consensus', {}).get('majority', {}),
            'full_council_result': council_result
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM Council analysis failed: {error_msg}, falling back to Claude")
        return analyze_alert_with_claude(finding_data)


def _format_metadata(metadata: dict) -> str:
    """Format metadata dictionary for display in the prompt."""
    if not metadata:
        return "None"
    
    lines = []
    for key, value in metadata.items():
        if isinstance(value, (dict, list)):
            lines.append(f"- {key}: {str(value)[:200]}")
        else:
            lines.append(f"- {key}: {value}")
    
    return '\n'.join(lines) if lines else "None"
