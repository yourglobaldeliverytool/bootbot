"""
APEX SIGNAL™ Institutional Telegram Engine
Version 4.0.0 - Full Autonomous Production Build
"""

import os
import asyncio
import logging
import sqlite3
from datetime import datetime, time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

try:
    from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False
    Bot = None

logger = logging.getLogger("APEX_TELEGRAM")


# ==============================
# DATABASE LAYER
# ==============================

class TradeDatabase:

    def __init__(self, db_path="apex_trades.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            side TEXT,
            entry REAL,
            stop REAL,
            tp1 REAL,
            tp2 REAL,
            tp3 REAL,
            confidence INTEGER,
            tier TEXT,
            status TEXT,
            pnl REAL DEFAULT 0,
            created_at TEXT
        )
        """)
        self.conn.commit()

    def insert_trade(self, trade):
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO trades(symbol, side, entry, stop, tp1, tp2, tp3, confidence, tier, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, trade)
        self.conn.commit()

    def update_trade_status(self, trade_id, status, pnl):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE trades SET status=?, pnl=? WHERE id=?", (status, pnl, trade_id))
        self.conn.commit()

    def get_stats(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(pnl) FROM trades WHERE status='closed'")
        total, pnl = cursor.fetchone()
        return {
            "total_closed": total or 0,
            "total_pnl": pnl or 0
        }


# ==============================
# SIGNAL STRUCTURE
# ==============================

@dataclass
class SignalData:
    symbol: str
    side: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    tp3: float
    confidence: int
    strategy: str
    indicators: List[str]


# ==============================
# MAIN NOTIFIER
# ==============================

class TelegramNotifier:

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.token and self.chat_id and TELEGRAM_AVAILABLE)

        self.db = TradeDatabase()
        self.bot = Bot(token=self.token) if self.enabled else None
        self.quiet_start = time(23, 0)
        self.quiet_end = time(6, 0)

    # ==========================
    # CONFIDENCE TIER ENGINE
    # ==========================

    def _confidence_tier(self, confidence: int):
        if confidence >= 85:
            return "ELITE 🔥"
        elif confidence >= 70:
            return "STRONG 💪"
        return "MODERATE ⚖️"

    # ==========================
    # QUIET HOURS
    # ==========================

    def _in_quiet_hours(self):
        now = datetime.utcnow().time()
        return now >= self.quiet_start or now <= self.quiet_end

    # ==========================
    # PNL CALCULATION
    # ==========================

    def calculate_pnl(self, side, entry, exit_price):
        if side.upper() == "BUY":
            return round(exit_price - entry, 2)
        return round(entry - exit_price, 2)

    # ==========================
    # FORMAT MESSAGE
    # ==========================

    def _format_signal(self, signal: SignalData):

        tier = self._confidence_tier(signal.confidence)

        return f"""
🛡️ APEX SIGNAL™ 4.0

📊 {signal.symbol}
📍 {signal.side}
🎯 Strategy: {signal.strategy}

💎 Confidence: {signal.confidence}% — {tier}

📌 Entry: {signal.entry}
🛑 Stop: {signal.stop}
🎯 TP1: {signal.tp1}
🎯 TP2: {signal.tp2}
🎯 TP3: {signal.tp3}

🕒 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""

    # ==========================
    # SEND WITH BUTTONS
    # ==========================

    async def _send_async(self, text, signal: Optional[SignalData] = None):

        if not self.enabled:
            print(text)
            return True

        buttons = None

        if signal:
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📈 Copy Trade", callback_data="copy_trade"),
                    InlineKeyboardButton("📊 Stats", callback_data="stats")
                ]
            ])

        await self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            reply_markup=buttons
        )
        return True

    def send_signal(self, raw_signal: Dict[str, Any]):

        signal = SignalData(
            symbol=raw_signal["symbol"],
            side=raw_signal["signal"],
            entry=float(raw_signal["price"]),
            stop=float(raw_signal["sl"]),
            tp1=float(raw_signal["tp1"]),
            tp2=float(raw_signal["tp2"]),
            tp3=float(raw_signal["tp3"]),
            confidence=int(raw_signal["confidence"]),
            strategy=raw_signal.get("strategy_name", "Multi-Factor AI"),
            indicators=raw_signal.get("indicators", [])
        )

        tier = self._confidence_tier(signal.confidence)

        # Store trade
        self.db.insert_trade((
            signal.symbol,
            signal.side,
            signal.entry,
            signal.stop,
            signal.tp1,
            signal.tp2,
            signal.tp3,
            signal.confidence,
            tier,
            "open",
            datetime.utcnow().isoformat()
        ))

        message = self._format_signal(signal)

        asyncio.run(self._send_async(message, signal))

    # ==========================
    # HEARTBEAT
    # ==========================

    def send_heartbeat(self):
        stats = self.db.get_stats()

        message = f"""
🟢 APEX SIGNAL™ LIVE

📊 Closed Trades: {stats["total_closed"]}
💰 Total PNL: {stats["total_pnl"]}

System Status: ACTIVE
"""

        asyncio.run(self._send_async(message))

    # ==========================
    # CLOSE TRADE
    # ==========================

    def close_trade(self, trade_id, exit_price):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT side, entry FROM trades WHERE id=?", (trade_id,))
        row = cursor.fetchone()
        if not row:
            return

        side, entry = row
        pnl = self.calculate_pnl(side, entry, exit_price)
        self.db.update_trade_status(trade_id, "closed", pnl)

