"""
Telegram Notification Client

Sends Telegram notifications for market inefficiency alerts.
"""

import requests
import logging
from typing import List, Optional
from config import Config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Telegram notification client
    """
    
    def __init__(self):
        self.token = Config.TELEGRAM_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None
        
    def send_message(self, message: str, chat_id: str = None, parse_mode: str = 'HTML') -> bool:
        """
        Send a Telegram message
        
        Args:
            message: Message text
            chat_id: Chat ID (uses default if not provided)
            parse_mode: Parse mode (HTML, Markdown, or None)
            
        Returns:
            True if sent successfully
        """
        try:
            if not self._validate_config():
                logger.error("Telegram configuration incomplete")
                return False
            
            target_chat_id = chat_id or self.chat_id
            if not target_chat_id:
                logger.error("No chat ID provided")
                return False
            
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': target_chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.info("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_finding_alert(self, finding_data: dict, chat_id: str = None) -> bool:
        """
        Send alert for a specific finding
        
        Args:
            finding_data: Finding data dictionary
            chat_id: Chat ID (optional)
            
        Returns:
            True if sent successfully
        """
        try:
            # Create formatted message
            agent_name = finding_data.get('agent', 'Unknown Agent')
            severity = finding_data.get('severity', 'medium').upper()
            title = finding_data.get('title', 'Market Anomaly Detected')
            description = finding_data.get('description', 'No description provided')
            symbol = finding_data.get('symbol', '')
            confidence = finding_data.get('confidence', 0.5) * 100
            
            # Severity emoji
            severity_emoji = {
                'LOW': '🟢',
                'MEDIUM': '🟡', 
                'HIGH': '🟠',
                'CRITICAL': '🔴'
            }
            emoji = severity_emoji.get(severity, '⚪')
            
            message = f"""
{emoji} <b>Market Alert - {severity}</b>

<b>Agent:</b> {agent_name}
<b>Finding:</b> {title}
"""
            
            if symbol:
                message += f"<b>Symbol:</b> {symbol}\n"
            
            message += f"<b>Confidence:</b> {confidence:.1f}%\n\n"
            message += f"<b>Description:</b>\n{description}"
            
            # Add key metadata
            metadata = finding_data.get('metadata', {})
            if metadata:
                message += "\n\n<b>Details:</b>"
                # Show only most important metadata to avoid message length limits
                important_keys = ['price_change', 'volume_change', 'funding_rate', 'vix_level', 'amount_eth']
                
                for key in important_keys:
                    if key in metadata:
                        value = metadata[key]
                        if isinstance(value, float):
                            if key.endswith('_change') or key == 'funding_rate':
                                message += f"\n• {key.replace('_', ' ').title()}: {value*100:.2f}%"
                            else:
                                message += f"\n• {key.replace('_', ' ').title()}: {value:.4f}"
                        else:
                            message += f"\n• {key.replace('_', ' ').title()}: {value}"
            
            return self.send_message(message, chat_id)
            
        except Exception as e:
            logger.error(f"Failed to send finding alert: {e}")
            return False
    
    def send_summary(self, summary_data: dict, chat_id: str = None) -> bool:
        """
        Send daily/periodic summary
        
        Args:
            summary_data: Summary statistics
            chat_id: Chat ID (optional)
            
        Returns:
            True if sent successfully
        """
        try:
            total_findings = summary_data.get('total_findings', 0)
            high_severity = summary_data.get('high_severity_findings', 0)
            active_agents = summary_data.get('active_agents', 0)
            
            message = f"""
📊 <b>Market Inefficiency Summary</b>

📈 <b>Total Findings:</b> {total_findings}
🔴 <b>High Severity:</b> {high_severity}
🤖 <b>Active Agents:</b> {active_agents}

<b>Recent Findings:</b>
"""
            
            # Add top findings
            top_findings = summary_data.get('top_findings', [])
            for i, finding in enumerate(top_findings[:5], 1):
                severity = finding.get('severity', 'medium').upper()
                emoji = {'LOW': '🟢', 'MEDIUM': '🟡', 'HIGH': '🟠', 'CRITICAL': '🔴'}.get(severity, '⚪')
                title = finding.get('title', 'Unknown')[:50]  # Truncate long titles
                symbol = f" ({finding['symbol']})" if finding.get('symbol') else ""
                
                message += f"\n{i}. {emoji} {title}{symbol}"
            
            return self.send_message(message, chat_id)
            
        except Exception as e:
            logger.error(f"Failed to send summary: {e}")
            return False
    
    def send_agent_status_update(self, agent_name: str, status: str, chat_id: str = None) -> bool:
        """
        Send agent status update
        
        Args:
            agent_name: Name of the agent
            status: Status (started, stopped, error)
            chat_id: Chat ID (optional)
            
        Returns:
            True if sent successfully
        """
        try:
            status_emoji = {
                'started': '▶️',
                'stopped': '⏹️',
                'error': '❌'
            }
            
            emoji = status_emoji.get(status, '📍')
            
            message = f"""
{emoji} <b>Agent Status Update</b>

<b>Agent:</b> {agent_name}
<b>Status:</b> {status.title()}
"""
            
            return self.send_message(message, chat_id)
            
        except Exception as e:
            logger.error(f"Failed to send agent status update: {e}")
            return False
    
    def _validate_config(self) -> bool:
        """Validate Telegram configuration"""
        return bool(self.token and self.base_url)
    
    def test_connection(self, chat_id: str = None) -> bool:
        """
        Test Telegram connection
        
        Args:
            chat_id: Chat ID to test (optional)
            
        Returns:
            True if connection successful
        """
        try:
            if not self._validate_config():
                return False
            
            # Test with getMe API call
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    logger.info(f"Telegram bot connected: {bot_info.get('result', {}).get('username', 'Unknown')}")
                    
                    # Test sending a message if chat_id provided
                    if chat_id or self.chat_id:
                        test_message = "🔧 Telegram connection test successful!"
                        return self.send_message(test_message, chat_id)
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False
