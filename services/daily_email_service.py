"""
Daily Email Service

Sends daily summary emails to whitelisted users via SendGrid.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app import db
from models import Whitelist, Finding, AgentStatus
from notifiers.sendgrid_notifier import SendGridNotifier

logger = logging.getLogger(__name__)


class DailyEmailService:
    """
    Service for sending daily email summaries to whitelisted users
    """
    
    def __init__(self):
        self.notifier = SendGridNotifier()
    
    def get_recipient_emails(self) -> List[str]:
        """Get all whitelisted email addresses"""
        try:
            whitelist_entries = Whitelist.query.all()
            emails = [entry.email for entry in whitelist_entries if entry.email]
            logger.info(f"Found {len(emails)} whitelisted emails for daily summary")
            return emails
        except Exception as e:
            logger.error(f"Failed to get whitelist emails: {e}")
            return []
    
    def get_daily_summary_data(self) -> Dict[str, Any]:
        """Gather summary data for the past 24 hours"""
        try:
            now = datetime.utcnow()
            yesterday = now - timedelta(hours=24)
            
            all_findings = Finding.query.filter(
                Finding.timestamp >= yesterday
            ).all()
            
            total_findings = len(all_findings)
            high_severity = len([f for f in all_findings if f.severity in ['high', 'critical']])
            medium_severity = len([f for f in all_findings if f.severity == 'medium'])
            
            active_agents = AgentStatus.query.filter(
                AgentStatus.is_active == True
            ).count()
            
            top_findings = sorted(
                all_findings,
                key=lambda f: (
                    {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(f.severity, 0),
                    f.confidence or 0
                ),
                reverse=True
            )[:10]
            
            top_findings_data = [{
                'title': f.title,
                'severity': f.severity,
                'agent': f.agent_name,
                'symbol': f.symbol,
                'confidence': f.confidence,
                'description': f.description
            } for f in top_findings]
            
            predictions = self._get_prediction_data(all_findings)
            
            return {
                'total_findings': total_findings,
                'high_severity_findings': high_severity,
                'medium_severity_findings': medium_severity,
                'active_agents': active_agents,
                'top_findings': top_findings_data,
                'predictions': predictions,
                'date': now.strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"Failed to gather summary data: {e}")
            return {
                'total_findings': 0,
                'high_severity_findings': 0,
                'medium_severity_findings': 0,
                'active_agents': 0,
                'top_findings': [],
                'predictions': []
            }
    
    def _get_prediction_data(self, all_findings: List) -> List[Dict[str, Any]]:
        """Extract prediction data from DailyPredictionAgent findings"""
        predictions = []
        
        prediction_findings = [
            f for f in all_findings 
            if f.agent_name == 'DailyPredictionAgent'
        ]
        
        for finding in prediction_findings[:6]:
            try:
                metadata = finding.metadata or {}
                predictions.append({
                    'symbol': finding.symbol or 'N/A',
                    'direction': metadata.get('direction', 'neutral'),
                    'confidence': finding.confidence or 0.5,
                    'target_price': metadata.get('target_price', 'N/A'),
                    'actionability': metadata.get('actionability', 'Low')
                })
            except Exception as e:
                logger.debug(f"Error parsing prediction: {e}")
                continue
        
        return predictions
    
    def send_daily_summary(self) -> bool:
        """
        Send daily summary to all whitelisted users
        
        Returns:
            True if emails sent successfully
        """
        try:
            if not self.notifier.is_configured():
                logger.warning("SendGrid not configured - skipping daily email")
                return False
            
            emails = self.get_recipient_emails()
            if not emails:
                logger.warning("No recipients found for daily email")
                return False
            
            summary_data = self.get_daily_summary_data()
            
            success = self.notifier.send_daily_summary(summary_data, emails)
            
            if success:
                logger.info(f"Daily summary sent to {len(emails)} recipients")
            else:
                logger.error("Failed to send daily summary")
            
            return success
            
        except Exception as e:
            logger.error(f"Error in send_daily_summary: {e}")
            return False
    
    def send_test_email(self, to_email: str = None) -> bool:
        """
        Send a test email to verify configuration
        
        Args:
            to_email: Optional specific email, otherwise uses first whitelisted
            
        Returns:
            True if test email sent successfully
        """
        try:
            if not self.notifier.is_configured():
                logger.error("SendGrid not configured")
                return False
            
            if not to_email:
                emails = self.get_recipient_emails()
                if not emails:
                    logger.error("No recipients available for test email")
                    return False
                to_email = emails[0]
            
            test_summary = {
                'total_findings': 42,
                'high_severity_findings': 5,
                'medium_severity_findings': 15,
                'active_agents': 13,
                'top_findings': [
                    {
                        'title': 'Test Finding - High Volatility Detected',
                        'severity': 'high',
                        'agent': 'TestAgent',
                        'symbol': 'SPY',
                        'confidence': 0.85
                    }
                ],
                'predictions': [
                    {
                        'symbol': 'SPY',
                        'direction': 'bullish',
                        'confidence': 0.72,
                        'target_price': '485.50',
                        'actionability': 'Medium'
                    }
                ]
            }
            
            return self.notifier.send_daily_summary(test_summary, [to_email])
            
        except Exception as e:
            logger.error(f"Failed to send test email: {e}")
            return False


def send_daily_emails():
    """Standalone function for scheduler to call"""
    from app import app
    with app.app_context():
        service = DailyEmailService()
        service.send_daily_summary()
