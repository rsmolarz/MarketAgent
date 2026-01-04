"""
SendGrid Email Notification Client

Sends email notifications for market inefficiency alerts using SendGrid API.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent

logger = logging.getLogger(__name__)


class SendGridNotifier:
    """
    SendGrid email notification client
    """
    
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY", "")
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL", "alerts@marketinefficiency.ai")
        self.client = None
        if self.api_key:
            self.client = SendGridAPIClient(self.api_key)
    
    def is_configured(self) -> bool:
        """Check if SendGrid is properly configured"""
        return bool(self.api_key and self.client)
    
    def send_email(self, 
                   to_emails: List[str],
                   subject: str,
                   html_content: str,
                   text_content: str = None) -> bool:
        """
        Send email via SendGrid
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_content: HTML email body
            text_content: Plain text email body (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if not self.is_configured():
                logger.error("SendGrid not configured - missing API key")
                return False
            
            message = Mail(
                from_email=Email(self.from_email, "Market Inefficiency Alerts"),
                to_emails=[To(email) for email in to_emails],
                subject=subject,
                html_content=html_content
            )
            
            if text_content:
                message.add_content(Content("text/plain", text_content))
            
            response = self.client.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully to {len(to_emails)} recipients")
                return True
            else:
                logger.error(f"SendGrid returned status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send email via SendGrid: {e}")
            return False
    
    def send_daily_summary(self, summary_data: dict, to_emails: List[str]) -> bool:
        """
        Send daily summary email
        
        Args:
            summary_data: Summary statistics and findings
            to_emails: List of recipient emails
            
        Returns:
            True if sent successfully
        """
        try:
            total_findings = summary_data.get('total_findings', 0)
            high_severity = summary_data.get('high_severity_findings', 0)
            active_agents = summary_data.get('active_agents', 0)
            date_str = datetime.now().strftime('%B %d, %Y')
            
            subject = f"Daily Market Summary - {date_str} | {total_findings} Findings"
            
            html_content = self._create_daily_summary_html(summary_data, date_str)
            text_content = self._create_daily_summary_text(summary_data, date_str)
            
            return self.send_email(to_emails, subject, html_content, text_content)
            
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
            return False
    
    def send_finding_alert(self, finding_data: dict, to_emails: List[str]) -> bool:
        """
        Send alert for a specific finding
        
        Args:
            finding_data: Finding data dictionary
            to_emails: List of recipient emails
            
        Returns:
            True if sent successfully
        """
        try:
            agent_name = finding_data.get('agent', 'Unknown Agent')
            severity = finding_data.get('severity', 'medium').upper()
            title = finding_data.get('title', 'Market Anomaly Detected')
            symbol = finding_data.get('symbol', '')
            
            subject = f"[{severity}] {agent_name}: {title}"
            if symbol:
                subject += f" ({symbol})"
            
            html_content = self._create_finding_html(finding_data)
            text_content = self._create_finding_text(finding_data)
            
            return self.send_email(to_emails, subject, html_content, text_content)
            
        except Exception as e:
            logger.error(f"Failed to send finding alert: {e}")
            return False
    
    def _create_daily_summary_html(self, summary_data: dict, date_str: str) -> str:
        """Create HTML content for daily summary"""
        total_findings = summary_data.get('total_findings', 0)
        high_severity = summary_data.get('high_severity_findings', 0)
        medium_severity = summary_data.get('medium_severity_findings', 0)
        active_agents = summary_data.get('active_agents', 0)
        top_findings = summary_data.get('top_findings', [])
        predictions = summary_data.get('predictions', [])
        
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107', 
            'high': '#fd7e14',
            'critical': '#dc3545'
        }
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center; }}
        .header h1 {{ margin: 0 0 10px 0; font-size: 24px; }}
        .header p {{ margin: 0; opacity: 0.8; }}
        .stats {{ display: flex; padding: 20px; background: #f8f9fa; }}
        .stat {{ flex: 1; text-align: center; padding: 10px; }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #1a1a2e; }}
        .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .section {{ padding: 20px; border-bottom: 1px solid #eee; }}
        .section h2 {{ margin: 0 0 15px 0; font-size: 18px; color: #1a1a2e; }}
        .finding {{ padding: 12px; margin-bottom: 10px; background: #f8f9fa; border-radius: 6px; border-left: 4px solid #666; }}
        .finding-high {{ border-left-color: #fd7e14; }}
        .finding-critical {{ border-left-color: #dc3545; }}
        .finding-medium {{ border-left-color: #ffc107; }}
        .finding-title {{ font-weight: 600; margin-bottom: 5px; }}
        .finding-meta {{ font-size: 12px; color: #666; }}
        .prediction {{ padding: 12px; margin-bottom: 10px; background: #e8f4fd; border-radius: 6px; }}
        .prediction-bullish {{ background: #e8f5e9; }}
        .prediction-bearish {{ background: #ffebee; }}
        .prediction-symbol {{ font-weight: 600; font-size: 16px; }}
        .prediction-direction {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
        .bullish {{ background: #28a745; color: white; }}
        .bearish {{ background: #dc3545; color: white; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Daily Market Summary</h1>
            <p>{date_str}</p>
        </div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{total_findings}</div>
                <div class="stat-label">Total Findings</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #fd7e14;">{high_severity}</div>
                <div class="stat-label">High Priority</div>
            </div>
            <div class="stat">
                <div class="stat-value">{active_agents}</div>
                <div class="stat-label">Active Agents</div>
            </div>
        </div>
"""
        
        if predictions:
            html += """
        <div class="section">
            <h2>Today's AI Predictions</h2>
"""
            for pred in predictions[:6]:
                symbol = pred.get('symbol', 'N/A')
                direction = pred.get('direction', 'neutral')
                confidence = pred.get('confidence', 0) * 100
                target = pred.get('target_price', 'N/A')
                
                direction_class = 'bullish' if direction == 'bullish' else 'bearish' if direction == 'bearish' else ''
                pred_class = 'prediction-bullish' if direction == 'bullish' else 'prediction-bearish' if direction == 'bearish' else ''
                
                html += f"""
            <div class="prediction {pred_class}">
                <span class="prediction-symbol">{symbol}</span>
                <span class="prediction-direction {direction_class}">{direction.upper()}</span>
                <span style="float: right; color: #666;">{confidence:.0f}% confidence</span>
                <div style="margin-top: 5px; font-size: 13px; color: #666;">
                    Target: ${target} | {pred.get('actionability', 'Low')} actionability
                </div>
            </div>
"""
            html += "</div>"
        
        if top_findings:
            html += """
        <div class="section">
            <h2>Top Findings</h2>
"""
            for finding in top_findings[:10]:
                severity = finding.get('severity', 'medium')
                title = finding.get('title', 'Unknown Finding')
                agent = finding.get('agent', 'Unknown Agent')
                symbol = finding.get('symbol', '')
                
                html += f"""
            <div class="finding finding-{severity}">
                <div class="finding-title">{title}</div>
                <div class="finding-meta">
                    {agent} {f'| {symbol}' if symbol else ''} | {severity.upper()}
                </div>
            </div>
"""
            html += "</div>"
        
        html += """
        <div class="footer">
            <p>Market Inefficiency Detection Platform</p>
            <p>This is an automated daily summary. Do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _create_daily_summary_text(self, summary_data: dict, date_str: str) -> str:
        """Create plain text content for daily summary"""
        total_findings = summary_data.get('total_findings', 0)
        high_severity = summary_data.get('high_severity_findings', 0)
        active_agents = summary_data.get('active_agents', 0)
        top_findings = summary_data.get('top_findings', [])
        predictions = summary_data.get('predictions', [])
        
        text = f"""
DAILY MARKET SUMMARY - {date_str}
{'=' * 50}

STATISTICS
- Total Findings: {total_findings}
- High Priority: {high_severity}
- Active Agents: {active_agents}

"""
        
        if predictions:
            text += "TODAY'S AI PREDICTIONS\n"
            text += "-" * 30 + "\n"
            for pred in predictions[:6]:
                symbol = pred.get('symbol', 'N/A')
                direction = pred.get('direction', 'neutral').upper()
                confidence = pred.get('confidence', 0) * 100
                text += f"{symbol}: {direction} ({confidence:.0f}% confidence)\n"
            text += "\n"
        
        if top_findings:
            text += "TOP FINDINGS\n"
            text += "-" * 30 + "\n"
            for i, finding in enumerate(top_findings[:10], 1):
                severity = finding.get('severity', 'medium').upper()
                title = finding.get('title', 'Unknown')
                symbol = finding.get('symbol', '')
                text += f"{i}. [{severity}] {title}"
                if symbol:
                    text += f" ({symbol})"
                text += "\n"
        
        text += f"\n{'=' * 50}\nMarket Inefficiency Detection Platform\n"
        return text
    
    def _create_finding_html(self, finding_data: dict) -> str:
        """Create HTML content for a finding alert"""
        severity = finding_data.get('severity', 'medium')
        title = finding_data.get('title', 'Market Anomaly')
        description = finding_data.get('description', 'No description')
        agent = finding_data.get('agent', 'Unknown Agent')
        symbol = finding_data.get('symbol', '')
        confidence = finding_data.get('confidence', 0.5) * 100
        
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107', 
            'high': '#fd7e14',
            'critical': '#dc3545'
        }
        color = severity_colors.get(severity, '#666')
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
        .alert {{ border-left: 4px solid {color}; padding: 20px; background: #f8f9fa; }}
        .severity {{ color: {color}; font-weight: bold; text-transform: uppercase; }}
        h2 {{ margin: 0 0 10px 0; }}
        .meta {{ color: #666; font-size: 14px; margin-bottom: 15px; }}
        .description {{ line-height: 1.6; }}
    </style>
</head>
<body>
    <div class="alert">
        <span class="severity">{severity}</span>
        <h2>{title}</h2>
        <div class="meta">
            Agent: {agent} | Symbol: {symbol if symbol else 'N/A'} | Confidence: {confidence:.0f}%
        </div>
        <div class="description">{description}</div>
    </div>
</body>
</html>
"""
    
    def _create_finding_text(self, finding_data: dict) -> str:
        """Create plain text content for a finding alert"""
        severity = finding_data.get('severity', 'medium').upper()
        title = finding_data.get('title', 'Market Anomaly')
        description = finding_data.get('description', 'No description')
        agent = finding_data.get('agent', 'Unknown Agent')
        symbol = finding_data.get('symbol', '')
        confidence = finding_data.get('confidence', 0.5) * 100
        
        return f"""
[{severity}] {title}

Agent: {agent}
Symbol: {symbol if symbol else 'N/A'}
Confidence: {confidence:.0f}%

{description}

---
Market Inefficiency Detection Platform
"""
