import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

openai_client = OpenAI(
    api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
    base_url=AI_INTEGRATIONS_OPENAI_BASE_URL
)

ANALYSIS_SYSTEM_PROMPT = """You are an expert financial analyst and trading strategist. When presented with a market alert or finding, provide a structured analysis with exactly three sections:

1. **Alert Summary**: A brief, plain-language explanation of what this alert means. Avoid technical jargon - explain it as you would to someone who understands investing basics but isn't a professional trader. Keep this to 2-3 sentences.

2. **Actionability Assessment**: Rate how actionable this alert is for a typical investor on a scale of Low/Medium/High. Consider:
   - How directly tradeable is the signal?
   - What is the time sensitivity?
   - How reliable is the underlying indicator?
   Provide a 2-3 sentence explanation of your rating.

3. **Trading Strategies**: Suggest 2-3 specific strategies that could capitalize on this finding. These can be:
   - Directly based on the alert's recommendation
   - Modifications or nuances to improve the suggested approach
   - Alternative or contrarian strategies that might also make sense
   For each strategy, briefly note the risk level and expected timeframe.

Keep your response focused and practical. Avoid excessive hedging language but do note significant risks."""


def analyze_alert_with_chatgpt(finding_data: dict) -> dict:
    """
    Analyze a market finding/alert using ChatGPT and return structured analysis.
    
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

        # the newest OpenAI model is "gpt-5" which was released August 7, 2025.
        # do not change this unless explicitly requested by the user
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": alert_text}
            ],
            max_completion_tokens=1500
        )
        
        analysis_text = response.choices[0].message.content or ""
        
        return {
            'success': True,
            'analysis': analysis_text,
            'model': 'gpt-4o',
            'finding_id': finding_data.get('id'),
            'finding_title': finding_data.get('title')
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"ChatGPT analysis failed: {error_msg}")
        
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
