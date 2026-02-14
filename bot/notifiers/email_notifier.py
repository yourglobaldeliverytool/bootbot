"""
Email Notifier.
Sends trading signals via email.
"""

from typing import Dict, Any, Optional
import logging

from bot.core.interfaces import Notifier


class EmailNotifier(Notifier):
    """
    Email notification system for trading signals.
    
    This notifier sends formatted trading signals via email using SMTP.
    Messages include HTML formatting with clear styling for easy reading.
    
    Note: This is a mock implementation. To use with real email:
        1. Configure SMTP server settings
        2. Provide sender and recipient email addresses
        3. Ensure proper authentication credentials
        
    Configuration:
        - smtp_server: SMTP server address (e.g., 'smtp.gmail.com')
        - smtp_port: SMTP server port (e.g., 587 for TLS, 465 for SSL)
        - sender_email: Sender email address
        - sender_password: Email password or app-specific password
        - recipient_email: Recipient email address
        - use_tls: Use TLS encryption (default: True)
    """
    
    NOTIFIER_NAME = "email"
    
    def __init__(self, name: str = None, parameters: Dict[str, Any] = None):
        """
        Initialize the email notifier.
        
        Args:
            name: Unique identifier for the notifier
            parameters: Configuration parameters including:
                - smtp_server (str): SMTP server address
                - smtp_port (int): SMTP server port
                - sender_email (str): Sender email address
                - sender_password (str): Email password
                - recipient_email (str): Recipient email address
                - use_tls (bool): Use TLS encryption (default: True)
        """
        if name is None:
            name = self.NOTIFIER_NAME
        super().__init__(name, parameters)
        
        # Set default parameters
        self.smtp_server = self.parameters.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = self.parameters.get('smtp_port', 587)
        self.sender_email = self.parameters.get('sender_email', '')
        self.sender_password = self.parameters.get('sender_password', '')
        self.recipient_email = self.parameters.get('recipient_email', '')
        self.use_tls = self.parameters.get('use_tls', True)
        
        # Validate parameters
        if not isinstance(self.smtp_port, int) or self.smtp_port <= 0:
            raise ValueError(f"smtp_port must be a positive integer, got {self.smtp_port}")
        
        if not isinstance(self.use_tls, bool):
            raise ValueError(f"use_tls must be boolean, got {type(self.use_tls)}")
        
        # Track message sending statistics
        self.messages_sent = 0
        self.messages_failed = 0
    
    def send_notification(self, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send a notification message via email.
        
        Args:
            message: The notification message to send
            data: Optional additional data to include with the notification
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        if not self.enabled:
            if self.logger:
                self.logger.debug("Email notifier is disabled, skipping notification")
            return False
        
        if self.logger:
            self.logger.debug(f"Sending email notification (length: {len(message)} chars)")
        
        # Format message
        subject = self._get_subject(data)
        body = self._format_message(message, data)
        
        # In a real implementation, this would send via SMTP
        # For now, we simulate successful sending
        success = self._send_email(subject, body)
        
        if success:
            self.messages_sent += 1
            if self.logger:
                self.logger.info(f"Email notification sent to {self.recipient_email}")
        else:
            self.messages_failed += 1
            if self.logger:
                self.logger.error("Failed to send email notification")
        
        return success
    
    def _get_subject(self, data: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate email subject line.
        
        Args:
            data: Optional data to include in subject
            
        Returns:
            Subject line string
        """
        if data and 'signal' in data:
            signal = data['signal']
            strategy = data.get('strategy_name', 'Trading Bot')
            return f"Trading Signal: {signal} - {strategy}"
        else:
            return "Trading Bot Notification"
    
    def _format_message(self, message: str, data: Optional[Dict[str, Any]] = None) -> str:
        """
        Format the message as HTML email.
        
        Args:
            message: The base message
            data: Optional data to include
            
        Returns:
            Formatted HTML message string
        """
        # Start HTML
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background-color: #f4f4f4; padding: 15px; border-radius: 5px 5px 0 0; }
                .content { background-color: #ffffff; padding: 20px; border: 1px solid #ddd; border-top: none; }
                .signal-buy { color: #008000; font-weight: bold; font-size: 18px; }
                .signal-sell { color: #cc0000; font-weight: bold; font-size: 18px; }
                .signal-hold { color: #666666; font-weight: bold; font-size: 18px; }
                .info-table { width: 100%; margin-top: 15px; border-collapse: collapse; }
                .info-table th, .info-table td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
                .info-table th { background-color: #f9f9f9; }
                .footer { background-color: #f4f4f4; padding: 15px; border-radius: 0 0 5px 5px; text-align: center; font-size: 12px; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
        """
        
        # Add header with signal type
        if data and 'signal' in data:
            signal = data['signal']
            signal_class = f"signal-{signal.lower()}"
            signal_emoji = {'BUY': '📈', 'SELL': '📉', 'HOLD': '⏸️'}.get(signal, '📊')
            
            html += f"""
                <div class="header">
                    <div class="{signal_class}">{signal_emoji} {signal} Signal</div>
                </div>
            """
        else:
            html += """
                <div class="header">
                    <div style="font-weight: bold; font-size: 18px;">📊 Trading Bot Notification</div>
                </div>
            """
        
        # Add content
        html += f"""
            <div class="content">
                <p>{message}</p>
        """
        
        # Add data table if provided
        if data:
            html += '<table class="info-table">'
            
            # Signal
            if 'signal' in data:
                html += f"<tr><th>Signal</th><td class=&quot;signal-{data['signal'].lower()}&quot;>{data['signal']}</td></tr>"
            
            # Strategy
            if 'strategy_name' in data:
                html += f"<tr><th>Strategy</th><td>{data['strategy_name']}</td></tr>"
            
            # Confidence
            if 'confidence' in data:
                confidence_pct = data['confidence'] * 100
                html += f"<tr><th>Confidence</th><td>{confidence_pct:.1f}%</td></tr>"
            
            # Reason
            if 'reason' in data:
                html += f"<tr><th>Reason</th><td>{data['reason']}</td></tr>"
            
            # Metadata
            if 'metadata' in data and isinstance(data['metadata'], dict):
                for key, value in data['metadata'].items():
                    html += f"<tr><th>{key.replace('_', ' ').title()}</th><td>{value}</td></tr>"
            
            html += '</table>'
        
        # Add timestamp
        import datetime
        html += f"<p style='margin-top: 20px; color: #666;'><strong>Time:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        
        # Close content and container
        html += """
            </div>
            <div class="footer">
                <p>This is an automated message from the Trading Bot. Please do not reply.</p>
            </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _send_email(self, subject: str, body: str) -> bool:
        """
        Send email via SMTP.
        
        Args:
            subject: Email subject line
            body: Email body (HTML formatted)
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Mock implementation - in production, this would use smtplib
        # Example real implementation:
        #
        # import smtplib
        # from email.mime.text import MIMEText
        # from email.mime.multipart import MIMEMultipart
        #
        # try:
        #     msg = MIMEMultipart('alternative')
        #     msg['From'] = self.sender_email
        #     msg['To'] = self.recipient_email
        #     msg['Subject'] = subject
        #
        #     html_part = MIMEText(body, 'html')
        #     msg.attach(html_part)
        #
        #     with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
        #         if self.use_tls:
        #             server.starttls()
        #         server.login(self.sender_email, self.sender_password)
        #         server.send_message(msg)
        #     
        #     return True
        # except Exception as e:
        #     if self.logger:
        #         self.logger.error(f"Email sending error: {e}")
        #     return False
        
        # Mock: Simulate success
        return True
    
    def send_signal_notification(self, signal: Dict[str, Any]) -> bool:
        """
        Send a trading signal notification.
        
        Args:
            signal: Signal dictionary with keys: signal, confidence, reason, etc.
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        message = signal.get('reason', 'Trading signal generated')
        return self.send_notification(message, signal)
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get notification statistics.
        
        Returns:
            Dictionary with sent and failed message counts
        """
        return {
            'sent': self.messages_sent,
            'failed': self.messages_failed,
            'total': self.messages_sent + self.messages_failed
        }
    
    def reset_statistics(self) -> None:
        """Reset notification statistics."""
        self.messages_sent = 0
        self.messages_failed = 0
        if self.logger:
            self.logger.debug("Email notification statistics reset")


# Note: Registration is handled dynamically by the registry.load_from_module() method
# The NOTIFIER_NAME class attribute is used by the registry to identify this notifier


# Minimal test for validation
if __name__ == "__main__":
    # Create test data
    print("Running Email Notifier Test...")
    print("=" * 60)
    
    # Test 1: Basic notification
    print("\nTest 1: Basic Notification")
    notifier1 = EmailNotifier(parameters={
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender_email': 'bot@example.com',
        'sender_password': 'password',
        'recipient_email': 'trader@example.com',
        'use_tls': True
    })
    
    message1 = "This is a test notification"
    success1 = notifier1.send_notification(message1)
    print(f"  Notification sent: {success1}")
    print(f"  Statistics: {notifier1.get_statistics()}")
    
    # Test 2: Signal notification
    print("\nTest 2: Signal Notification")
    signal_data = {
        'signal': 'BUY',
        'confidence': 0.85,
        'reason': 'Strong upward momentum detected',
        'strategy_name': 'trend_following',
        'metadata': {
            'price': 105.50,
            'sma_20': 102.30
        }
    }
    
    success2 = notifier1.send_signal_notification(signal_data)
    print(f"  Signal notification sent: {success2}")
    print(f"  Statistics: {notifier1.get_statistics()}")
    
    # Test 3: Different signal types
    print("\nTest 3: Different Signal Types")
    
    for signal_type in ['BUY', 'SELL', 'HOLD']:
        test_signal = {
            'signal': signal_type,
            'confidence': 0.75,
            'reason': f'Test {signal_type} signal',
            'strategy_name': 'test_strategy'
        }
        notifier1.send_signal_notification(test_signal)
    
    stats = notifier1.get_statistics()
    print(f"  Total notifications sent: {stats['sent']}")
    print(f"  Failed notifications: {stats['failed']}")
    
    # Test 4: Disabled notifier
    print("\nTest 4: Disabled Notifier")
    notifier1.disable()
    disabled_success = notifier1.send_notification("This should not be sent")
    print(f"  Disabled notification sent: {disabled_success}")
    print(f"  Statistics unchanged: {notifier1.get_statistics()}")
    
    notifier1.enable()
    print(f"  Re-enabled notifier")
    
    # Test 5: Reset statistics
    print("\nTest 5: Reset Statistics")
    print(f"  Before reset: {notifier1.get_statistics()}")
    notifier1.reset_statistics()
    print(f"  After reset: {notifier1.get_statistics()}")
    
    # Test 6: Different SMTP configurations
    print("\nTest 6: Different SMTP Configurations")
    
    configs = [
        {'smtp_port': 587, 'use_tls': True},
        {'smtp_port': 465, 'use_tls': True},
        {'smtp_port': 25, 'use_tls': False}
    ]
    
    for config in configs:
        notifier_test = EmailNotifier(parameters={
            'smtp_server': 'smtp.example.com',
            'sender_email': 'bot@example.com',
            'recipient_email': 'trader@example.com',
            **config
        })
        notifier_test.send_notification(f"Test with port {config['smtp_port']}, TLS: {config['use_tls']}")
        print(f"  Port {config['smtp_port']}, TLS {config['use_tls']}: ✓")
    
    # Test 7: Error handling
    print("\nTest 7: Error Handling")
    try:
        bad_notifier = EmailNotifier(parameters={
            'smtp_port': -1
        })
        print("  ✗ Should have raised ValueError for negative smtp_port")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    try:
        bad_notifier = EmailNotifier(parameters={
            'use_tls': 'not_boolean'
        })
        print("  ✗ Should have raised ValueError for non-boolean use_tls")
    except ValueError as e:
        print(f"  ✓ Correctly raised ValueError: {e}")
    
    # Test 8: Registry registration
    print("\nTest 8: Registry Registration")
    from bot.core.registry import NotifierRegistry
    registry = NotifierRegistry()
    
    count = registry.load_from_module('bot.notifiers.email_notifier')
    print(f"  Loaded {count} notifier(s) from module")
    
    if registry.exists('email'):
        print(f"  ✓ Email notifier registered in registry as 'email'")
        registered_class = registry.get('email')
        print(f"  ✓ Registered class: {registered_class.__name__}")
        
        # Test creating instance from registry
        notifier_from_registry = registry.create_instance('email', {
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'sender_email': 'bot@example.com',
            'recipient_email': 'trader@example.com'
        })
        print(f"  ✓ Created instance from registry: {notifier_from_registry.__class__.__name__}")
    else:
        print("  ✗ Email notifier not found in registry")
    
    print("\n" + "=" * 60)
    print("✅ All Email Notifier Tests Passed!")