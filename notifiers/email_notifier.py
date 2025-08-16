"""
Email Notification Client

Sends email notifications for market inefficiency alerts.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from config import Config

logger = logging.getLogger(__name__)

class EmailNotifier:
    """
    Email notification client
    """
    
    def __init__(self):
        self.host = Config.EMAIL_HOST
        self.port = Config.EMAIL_PORT
        self.user = Config.EMAIL_USER
        self.password = Config.EMAIL_PASSWORD
        
    def send_alert(self, 
                   to_emails: List[str],
                   subject: str,
                   message: str,
                   finding_data: dict = None) -> bool:
        """
        Send email alert
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            message: Email message
            finding_data: Optional finding data for rich formatting
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if not self._validate_config():
                logger.error("Email configuration incomplete")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.user
            msg['To'] = ', '.join(to_emails)
            
            # Create text and HTML versions
            text_content = self._create_text_content(message, finding_data)
            html_content = self._create_html_content(message, finding_data)
            
            # Attach parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
            
            logger.info(f"Alert email sent to {len(to_emails)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
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
            
            message = finding_data.get('description', 'No description provided')
            
            return self.send_alert(to_emails, subject, message, finding_data)
            
        except Exception as e:
            logger.error(f"Failed to send finding alert: {e}")
            return False
    
    def send_daily_summary(self, summary_data: dict, to_emails: List[str]) -> bool:
        """
        Send daily summary email
        
        Args:
            summary_data: Summary statistics
            to_emails: List of recipient emails
            
        Returns:
            True if sent successfully
        """
        try:
            total_findings = summary_data.get('total_findings', 0)
            high_severity = summary_data.get('high_severity_findings', 0)
            active_agents = summary_data.get('active_agents', 0)
            
            subject = f"Market Inefficiency Daily Summary - {total_findings} Findings"
            
            message = f"""
Daily Market Inefficiency Summary

Total Findings: {total_findings}
High Severity Findings: {high_severity}
Active Agents: {active_agents}

Top Findings:
"""
            
            # Add top findings
            top_findings = summary_data.get('top_findings', [])
            for i, finding in enumerate(top_findings[:5], 1):
                message += f"\n{i}. [{finding.get('severity', 'medium').upper()}] {finding.get('title', 'Unknown')}"
                if finding.get('symbol'):
                    message += f" ({finding['symbol']})"
            
            return self.send_alert(to_emails, subject, message, summary_data)
            
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
            return False
    
    def _validate_config(self) -> bool:
        """Validate email configuration"""
        return all([
            self.host,
            self.port,
            self.user,
            self.password
        ])
    
    def _create_text_content(self, message: str, finding_data: dict = None) -> str:
        """Create plain text email content"""
        content = message
        
        if finding_data:
            content += f"\n\nDetails:\n"
            content += f"Agent: {finding_data.get('agent', 'Unknown')}\n"
            content += f"Severity: {finding_data.get('severity', 'medium').upper()}\n"
            content += f"Confidence: {finding_data.get('confidence', 0.5)*100:.1f}%\n"
            
            if finding_data.get('symbol'):
                content += f"Symbol: {finding_data['symbol']}\n"
                
            if finding_data.get('market_type'):
                content += f"Market: {finding_data['market_type']}\n"
            
            # Add metadata if present
            metadata = finding_data.get('metadata', {})
            if metadata:
                content += f"\nAdditional Data:\n"
                for key, value in metadata.items():
                    content += f"{key}: {value}\n"
        
        content += f"\n\nGenerated by Market Inefficiency Detection Platform"
        return content
    
    def _create_html_content(self, message: str, finding_data: dict = None) -> str:
        """Create HTML email content"""
        
        # Determine severity color
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107', 
            'high': '#fd7e14',
            'critical': '#dc3545'
        }
        
        severity = finding_data.get('severity', 'medium') if finding_data else 'medium'
        color = severity_colors.get(severity, '#6c757d')
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
        .severity {{ color: {color}; font-weight: bold; text-transform: uppercase; }}
        .details {{ background-color: #f8f9fa; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .footer {{ color: #6c757d; font-size: 12px; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td {{ padding: 5px 10px; border-bottom: 1px solid #dee2e6; }}
        .label {{ font-weight: bold; width: 120px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>Market Inefficiency Alert</h2>
    </div>
    
    <div style="margin: 20px 0;">
        <p>{message}</p>
    </div>
"""
        
        if finding_data:
            html += f"""
    <div class="details">
        <h3>Finding Details</h3>
        <table>
            <tr>
                <td class="label">Agent:</td>
                <td>{finding_data.get('agent', 'Unknown')}</td>
            </tr>
            <tr>
                <td class="label">Severity:</td>
                <td><span class="severity">{finding_data.get('severity', 'medium')}</span></td>
            </tr>
            <tr>
                <td class="label">Confidence:</td>
                <td>{finding_data.get('confidence', 0.5)*100:.1f}%</td>
            </tr>
"""
            
            if finding_data.get('symbol'):
                html += f"""
            <tr>
                <td class="label">Symbol:</td>
                <td>{finding_data['symbol']}</td>
            </tr>
"""
            
            if finding_data.get('market_type'):
                html += f"""
            <tr>
                <td class="label">Market:</td>
                <td>{finding_data['market_type'].title()}</td>
            </tr>
"""
            
            html += "</table></div>"
            
            # Add metadata if present
            metadata = finding_data.get('metadata', {})
            if metadata:
                html += '<div class="details"><h3>Additional Data</h3><table>'
                for key, value in metadata.items():
                    html += f'<tr><td class="label">{key}:</td><td>{value}</td></tr>'
                html += '</table></div>'
        
        html += """
    <div class="footer">
        <p>Generated by Market Inefficiency Detection Platform</p>
    </div>
</body>
</html>
"""
        
        return html
