# bot/notifiers/telegram.py
"""
APEX SIGNAL™ - Branded Telegram Notification Adapter
Production-grade messaging with branded templates, async wrappers and a send_notification compatibility API.
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
except Exception:
    TELEGRAM_AVAILABLE = False
    Bot = None

logger = logging.getLogger("APEX_TELEGRAM")


@dataclass
class SignalData:
    symbol: str
    side: str
    timeframe: str
    strategy_name: str
    strategy_id: str
    indicators: List[str]
    confidence: int
    confluence_score: int
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
    Telegram notifier providing:
    - send_notification(message, signal) compatibility
    - send_signal / send_signal_async for structured messages
    - send_message / send_message_async low-level
    """

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None, version: str = "3.0.0"):
        self.token = token
        self.chat_id = chat_id
        self.version = version
        self.enabled = bool(token and chat_id and TELEGRAM_AVAILABLE)

        if self.enabled:
            self.bot = Bot(token=token)
            self._throttle_lock = asyncio.Lock()
            logger.info("✅ Telegram notifier initialized")
        else:
            self.bot = None
            logger.warning("⚠️ Telegram notifier is disabled (missing credentials or lib)")

    def is_enabled(self) -> bool:
        return self.enabled

    def format_signal_message(self, signal: SignalData) -> str:
        targets_str = ", ".join([f"${tp:.2f}" for tp in signal.take_profits]) if signal.take_profits else "N/A"
        indicators_str = ", ".join(signal.indicators) if signal.indicators else "N/A"
        trace_id = f"{signal.trade_id[:8]}.../{signal.strategy_id[:8]}..."
        message = f"""🛡️ APEX SIGNAL™ • v{self.version}
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

    def format_compact_signal_message(self, signal: SignalData) -> str:
        message = f"""🛡️ APEX SIGNAL™ • v{self.version}
{signal.symbol} {signal.side} @ ${signal.entry_price:.2f}
💎 {signal.confidence}% confidence | {signal.strategy_name}
TP: ${signal.take_profits[0]:.2f} | SL: ${signal.stop_loss:.2f}
RR: {signal.risk_reward_ratio} | {signal.position_size:.6f} units
{datetime.utcnow().strftime('%H:%M:%S')} UTC"""
        return message

    def format_heartbeat_message(self, stats: Dict[str, Any]) -> str:
        uptime = stats.get("uptime", "N/A")
        signals_last_hour = stats.get("signals_last_hour", 0)
        last_trade_time = stats.get("last_trade_time", "N/A")
        cpu_percent = stats.get("cpu_percent", 0)
        memory_mb = stats.get("memory_mb", 0)
        message = f"""🛡️ APEX SIGNAL™ • v{self.version} - HEARTBEAT
⏱️  UPTIME: {uptime}
📊 Signals (last hour): {signals_last_hour}
🕒 Last trade: {last_trade_time}
💻 CPU: {cpu_percent:.1f}% | RAM: {memory_mb:.1f} MB
✅ System operational
{datetime.utcnow().strftime('%H:%M:%S')} UTC"""
        return message

    def format_error_message(self, error: str) -> str:
        message = f"""🛡️ APEX SIGNAL™ • v{self.version} - ERROR ALERT
⚠️  {error}
{datetime.utcnow().strftime('%H:%M:%S')} UTC"""
        return message

    # ---------- low level senders ----------
    async def send_message_async(self, message: str, max_retries: int = 3) -> bool:
        if not self.enabled:
            logger.debug(f"Telegram disabled - message would be: {message[:80]}...")
            return True
        for attempt in range(max_retries + 1):
            try:
                # simple rate-limit safety (small)
                async with self._throttle_lock:
                    await self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode="HTML")
                logger.info("✅ Telegram message sent")
                return True
            except TelegramError as e:
                logger.warning(f"TelegramError attempt {attempt+1}: {e}")
                if attempt == max_retries:
                    logger.error("Failed to send Telegram message after retries")
                    return False
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.exception("Unexpected error sending Telegram message")
                return False
        return False

    def send_message(self, message: str) -> bool:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.send_message_async(message))
                return True
            else:
                return asyncio.run(self.send_message_async(message))
        except Exception as e:
            logger.exception("send_message wrapper failed")
            return False

    # ---------- structured signal API ----------
    async def send_signal_async(self, signal: SignalData, compact: bool = False) -> bool:
        message = self.format_compact_signal_message(signal) if compact else self.format_signal_message(signal)
        return await self.send_message_async(message)

    def send_signal(self, signal: SignalData, compact: bool = False) -> bool:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.send_signal_async(signal, compact))
                return True
            else:
                return asyncio.run(self.send_signal_async(signal, compact))
        except Exception:
            logger.exception("send_signal wrapper failed")
            return False

    # ---------- compatibility API used by engine ----------
    def send_notification(self, message: str, raw_signal: Dict[str, Any]) -> bool:
        """
        Compatibility entrypoint used by engine: Accepts engine message + raw signal dict.
        Converts raw_signal into SignalData when possible, else sends the plain message.
        """
        try:
            # try to convert
            try:
                sd = SignalData(
                    symbol=raw_signal.get("symbol", "N/A"),
                    side=raw_signal.get("signal", "N/A"),
                    timeframe=raw_signal.get("timeframe", raw_signal.get("tf", "1m")),
                    strategy_name=raw_signal.get("strategy_name", "unknown"),
                    strategy_id=raw_signal.get("strategy_id", "unknown"),
                    indicators=raw_signal.get("metadata", {}).get("indicators", []) or raw_signal.get("indicators", []),
                    confidence=int(raw_signal.get("confidence", 0) * 100) if isinstance(raw_signal.get("confidence", 0), float) else int(raw_signal.get("confidence", 0) or 0),
                    confluence_score=int(raw_signal.get("confluence_score", raw_signal.get("confluence", 0) or 0)),
                    entry_price=float(raw_signal.get("entry_price", raw_signal.get("metadata", {}).get("price", 0.0) or 0.0)),
                    stop_loss=float(raw_signal.get("stop_loss", raw_signal.get("metadata", {}).get("stop_loss", 0.0) or 0.0)),
                    take_profits=raw_signal.get("take_profits", raw_signal.get("metadata", {}).get("tps", []) or []),
                    position_size=float(raw_signal.get("position_size", 0.0) or 0.0),
                    position_value=float(raw_signal.get("position_value", 0.0) or 0.0),
                    risk_percent=float(raw_signal.get("risk_percent", 0.0) or 0.0),
                    risk_reward_ratio=str(raw_signal.get("risk_reward_ratio", raw_signal.get("rr", "N/A"))),
                    trade_id=raw_signal.get("trade_id", raw_signal.get("id", "")) or hashlib.md5(str(raw_signal).encode()).hexdigest(),
                    log_snippet=str(raw_signal.get("metadata", {}).get("log_snippet", ""))[:400]
                )
                # send structured message
                return self.send_signal(sd)
            except Exception:
                # fallback: send raw message
                return self.send_message(message)
        except Exception:
            logger.exception("send_notification failed")
            return False

    def send_heartbeat(self, stats: Dict[str, Any]) -> bool:
        try:
            return self.send_message(self.format_heartbeat_message(stats))
        except Exception:
            logger.exception("send_heartbeat failed")
            return False

    def send_error(self, error: str) -> bool:
        try:
            return self.send_message(self.format_error_message(error))
        except Exception:
            logger.exception("send_error failed")
            return False


def create_telegram_notifier() -> TelegramNotifier:
    """
    Factory that reads environment and returns an instance (may be disabled).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    return TelegramNotifier(token=token, chat_id=chat_id)
