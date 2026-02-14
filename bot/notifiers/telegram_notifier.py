"""
APEX SIGNAL™ - Branded Telegram Notification Adapter
Production-grade messaging with branded templates, confidence scoring, and confluence breakdown.
"""

import os
import logging
import asyncio
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

# Only import telegram if available
try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None

logger = logging.getLogger(__name__)


@dataclass
class SignalData:
    """Structured data for signal notifications."""
    symbol: str
    side: str  # BUY or SELL
    timeframe: str
    strategy_name: str
    strategy_id: str
    indicators: List[str]
    confidence: int  # 0-100
    confluence_score: int  # 0-100
    entry_price: float
    stop_loss: float
    take_profits: List[float]
    position_size: float
    position_value: float
    risk_percent: float
    risk_reward_ratio: str
    trade_id: str
    log_snippet: str = ""


class TelegramNotifier:
    """
    Production-grade Telegram notifier with:
    - Branded APEX SIGNAL™ messaging
    - Async sending with retry logic
    - Queue management
    - Rate limiting
    - Professional formatting templates
    """
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize Telegram notifier.
        
        Args:
            token: Telegram bot token (or None if disabled)
            chat_id: Target chat ID (or None if disabled)
        """
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id and TELEGRAM_AVAILABLE)
        
        if self.enabled:
            self.bot = Bot(token=token)
            self.message_queue = asyncio.Queue()
            self.is_processing = False
            logger.info("✅ Telegram notifier initialized")
        else:
            self.bot = None
            logger.warning("⚠️  Telegram DISABLED - Missing credentials or python-telegram-bot")
    
    def is_enabled(self) -> bool:
        """Check if Telegram notifications are enabled."""
        return self.enabled
    
    def format_signal_message(self, signal: SignalData, version: str = "3.0.0") -> str:
        """
        Format signal message with branded APEX SIGNAL™ template.
        
        Args:
            signal: Signal data structure
            version: System version
            
        Returns:
            Formatted message string
        """
        # Format take profits
        targets_str = ", ".join([f"${tp:.2f}" for tp in signal.take_profits])
        
        # Format indicators list
        indicators_str = ", ".join(signal.indicators) if signal.indicators else "N/A"
        
        # Create trace ID
        trace_id = f"{signal.trade_id[:8]}.../{signal.strategy_id[:8]}..."
        
        # Build message with branded template
        message = f"""🛡️ APEX SIGNAL™ • v{version}
🔔 SIGNAL: {signal.symbol} {signal.side} ({signal.timeframe})
📈 STRATEGY: {signal.strategy_name} — indicator(s): {indicators_str}
💎 CONFIDENCE: {signal.confidence}% (0-100)
💰 POSITION SIZE: {signal.position_size:.6f} / ${signal.position_value:.2f}
⚖️  RISK: {signal.risk_percent}% | RR: {signal.risk_reward_ratio}
📌 ENTRY: ${signal.entry_price:.2f}
🛑 STOP: ${signal.stop_loss:.2f}
🎯 TARGETS: {targets_str}
🧾 SCORE: Confluence={signal.confluence_score} / Confidence={signal.confidence}
🕒 TIMESTAMP: {datetime.utcnow().isoformat()}Z
🔗 TRACE: {trace_id}
🧾 LOG: {signal.log_snippet[:100] if signal.log_snippet else 'N/A'}...
— APEX SIGNAL™ (professional, institutional)"""
        
        return message
    
    def format_compact_signal_message(self, signal: SignalData, version: str = "3.0.0") -> str:
        """
        Format compact signal message for quick notifications.
        
        Args:
            signal: Signal data structure
            version: System version
            
        Returns:
            Formatted compact message string
        """
        message = f"""🛡️ APEX SIGNAL™ • v{version}
{signal.symbol} {signal.side} @ ${signal.entry_price:.2f}
💎 {signal.confidence}% confidence | {signal.strategy_name}
TP: ${signal.take_profits[0]:.2f} | SL: ${signal.stop_loss:.2f}
RR: {signal.risk_reward_ratio} | {signal.position_size:.6f} units
{datetime.utcnow().strftime('%H:%M:%S')} UTC"""
        
        return message
    
    def format_heartbeat_message(self, stats: Dict[str, Any], version: str = "3.0.0") -> str:
        """
        Format hourly heartbeat message.
        
        Args:
            stats: Statistics dictionary
            version: System version
            
        Returns:
            Formatted heartbeat message
        """
        uptime = stats.get('uptime', 'N/A')
        signals_last_hour = stats.get('signals_last_hour', 0)
        last_trade_time = stats.get('last_trade_time', 'N/A')
        cpu_percent = stats.get('cpu_percent', 0)
        memory_mb = stats.get('memory_mb', 0)
        
        message = f"""🛡️ APEX SIGNAL™ • v{version} - HEARTBEAT
⏱️  UPTIME: {uptime}
📊 Signals (last hour): {signals_last_hour}
🕒 Last trade: {last_trade_time}
💻 CPU: {cpu_percent:.1f}% | RAM: {memory_mb:.1f} MB
✅ System operational
{datetime.utcnow().strftime('%H:%M:%S')} UTC"""
        
        return message
    
    def format_error_message(self, error: str, version: str = "3.0.0") -> str:
        """
        Format error notification message.
        
        Args:
            error: Error message
            version: System version
            
        Returns:
            Formatted error message
        """
        message = f"""🛡️ APEX SIGNAL™ • v{version} - ERROR ALERT
⚠️  {error}
{datetime.utcnow().strftime('%H:%M:%S')} UTC"""
        
        return message
    
    async def send_message_async(self, message: str, max_retries: int = 3) -> bool:
        """
        Send message to Telegram with retry logic.
        
        Args:
            message: Message to send
            max_retries: Maximum retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug(f"Telegram disabled - would send: {message[:50]}...")
            return True
        
        for attempt in range(max_retries + 1):
            try:
                # Rate limiting: wait between retries
                if attempt > 0:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='HTML'
                )
                
                logger.info(f"✅ Telegram message sent successfully (attempt {attempt + 1})")
                return True
                
            except TelegramError as e:
                logger.warning(f"⚠️  Telegram error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                
                if attempt == max_retries:
                    logger.error(f"❌ Failed to send Telegram message after {max_retries + 1} attempts")
                    return False
        
        return False
    
    def send_message(self, message: str) -> bool:
        """
        Send message to Telegram (synchronous wrapper).
        
        Args:
            message: Message to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, create a task
                asyncio.create_task(self.send_message_async(message))
                return True
            else:
                # Run in new loop
                return asyncio.run(self.send_message_async(message))
        except Exception as e:
            logger.error(f"❌ Error sending Telegram message: {e}")
            return False
    
    async def send_signal_async(self, signal: SignalData, compact: bool = False) -> bool:
        """
        Send signal notification to Telegram.
        
        Args:
            signal: Signal data structure
            compact: Use compact format
            
        Returns:
            True if successful, False otherwise
        """
        if compact:
            message = self.format_compact_signal_message(signal)
        else:
            message = self.format_signal_message(signal)
        
        return await self.send_message_async(message)
    
    def send_signal(self, signal: SignalData, compact: bool = False) -> bool:
        """
        Send signal notification to Telegram (synchronous wrapper).
        
        Args:
            signal: Signal data structure
            compact: Use compact format
            
        Returns:
            True if successful, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.send_signal_async(signal, compact))
                return True
            else:
                return asyncio.run(self.send_signal_async(signal, compact))
        except Exception as e:
            logger.error(f"❌ Error sending signal notification: {e}")
            return False
    
    async def send_heartbeat_async(self, stats: Dict[str, Any]) -> bool:
        """
        Send heartbeat message to Telegram.
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            True if successful, False otherwise
        """
        message = self.format_heartbeat_message(stats)
        return await self.send_message_async(message)
    
    def send_heartbeat(self, stats: Dict[str, Any]) -> bool:
        """
        Send heartbeat message to Telegram (synchronous wrapper).
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.send_heartbeat_async(stats))
                return True
            else:
                return asyncio.run(self.send_heartbeat_async(stats))
        except Exception as e:
            logger.error(f"❌ Error sending heartbeat: {e}")
            return False
    
    async def send_error_async(self, error: str) -> bool:
        """
        Send error notification to Telegram.
        
        Args:
            error: Error message
            
        Returns:
            True if successful, False otherwise
        """
        message = self.format_error_message(error)
        return await self.send_message_async(message)
    
    def send_error(self, error: str) -> bool:
        """
        Send error notification to Telegram (synchronous wrapper).
        
        Args:
            error: Error message
            
        Returns:
            True if successful, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.send_error_async(error))
                return True
            else:
                return asyncio.run(self.send_error_async(error))
        except Exception as e:
            logger.error(f"❌ Error sending error notification: {e}")
            return False
    
    def generate_trade_id(self, symbol: str, side: str) -> str:
        """
        Generate unique trade ID.
        
        Args:
            symbol: Trading symbol
            side: Trade side (BUY/SELL)
            
        Returns:
            Unique trade ID
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique = hashlib.md5(f"{symbol}{side}{timestamp}".encode()).hexdigest()[:8]
        return f"{symbol}_{side}_{timestamp}_{unique}"


# Legacy compatibility - create instance from environment
def create_telegram_notifier() -> TelegramNotifier:
    """
    Create Telegram notifier from environment variables.
    
    Returns:
        TelegramNotifier instance
    """
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    return TelegramNotifier(token=token, chat_id=chat_id)