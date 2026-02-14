"""
APEX SIGNAL™ - Branded Telegram Notification Adapter
Production-grade messaging with:
 - AI Confidence Tiers (ELITE / STRONG / MODERATE)
 - Auto PnL tracking (SQLite)
 - Signal performance stats
 - Smart quiet-hours mode
 - Copy-trade inline buttons (callback placeholders)
 - Telegram inline buttons
 - Database-backed trade tracking
Compatible with both sync and async callers.
"""

import os
import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, time
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

try:
    from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, Update
    from telegram.error import TelegramError
    from telegram.ext import CallbackQueryHandler, ApplicationBuilder
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False
    Bot = None

logger = logging.getLogger("APEX_TELEGRAM")
logger.setLevel(logging.INFO)


# --------------------
# Simple SQLite trade DB
# --------------------
class TradeDB:
    def __init__(self, db_path: str = "apex_trades.db"):
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        cur.execute(
            """
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
            );
            """
        )
        self.conn.commit()

    def insert_trade(self, rec: Tuple):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO trades(symbol, side, entry, stop, tp1, tp2, tp3, confidence, tier, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rec,
        )
        self.conn.commit()
        return cur.lastrowid

    def close_trade(self, trade_id: int, pnl: float):
        cur = self.conn.cursor()
        cur.execute("UPDATE trades SET status = 'closed', pnl = ? WHERE id = ?", (pnl, trade_id))
        self.conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM trades")
        total = cur.fetchone()[0] or 0
        cur.execute("SELECT COUNT(*) FROM trades WHERE status='closed'")
        closed = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(pnl) FROM trades WHERE status='closed'")
        s = cur.fetchone()[0]
        total_pnl = float(s) if s is not None else 0.0
        return {"total_trades": total, "closed_trades": closed, "total_pnl": total_pnl}

    def get_open_trades(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, symbol, side, entry, stop, tp1, tp2, tp3, confidence, tier, created_at FROM trades WHERE status='open'")
        rows = cur.fetchall()
        keys = ["id","symbol","side","entry","stop","tp1","tp2","tp3","confidence","tier","created_at"]
        return [dict(zip(keys, r)) for r in rows]


# --------------------
# Signal data structure
# --------------------
@dataclass
class Signal:
    symbol: str
    side: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float  # 0-100
    strategy_name: str
    indicators: List[str]


# --------------------
# Notifier
# --------------------
class TelegramNotifier:
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None, enabled_override: Optional[bool] = None):
        # token/chat can be passed in or read from env
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = enabled_override if enabled_override is not None else bool(self.token and self.chat_id and TELEGRAM_AVAILABLE)
        self.version = "4.0.0"
        self.db = TradeDB(db_path=os.getenv("APEX_TRADE_DB", "apex_trades.db"))

        # quiet hours default (UTC)
        self.quiet_start = time(23, 0)
        self.quiet_end = time(6, 0)

        if self.enabled:
            try:
                self.bot = Bot(token=self.token)
            except Exception as e:
                logger.exception("Failed to initialize Telegram Bot: %s", e)
                self.bot = None
                self.enabled = False
        else:
            self.bot = None
            if not TELEGRAM_AVAILABLE:
                logger.warning("python-telegram-bot not available; Telegram disabled")
            else:
                logger.warning("Telegram disabled: missing token/chat id")

    def is_enabled(self) -> bool:
        return self.enabled

    # Confidence tiers
    def _tier(self, confidence: float) -> str:
        if confidence >= 85:
            return "ELITE"
        if confidence >= 70:
            return "STRONG"
        return "MODERATE"

    def _in_quiet_hours(self) -> bool:
        now = datetime.utcnow().time()
        if self.quiet_start <= self.quiet_end:
            return self.quiet_start <= now <= self.quiet_end
        else:
            # overnight window
            return now >= self.quiet_start or now <= self.quiet_end

    def _format_signal_text(self, s: Signal) -> str:
        tier = self._tier(s.confidence)
        indicators = ", ".join(s.indicators[:8]) if s.indicators else "N/A"
        rr = self._calc_rr(s)
        return (
            f"🛡️ APEX SIGNAL™ • v{self.version}\n\n"
            f"🔔 {s.symbol} — {s.side}\n"
            f"📈 Strategy: {s.strategy_name}\n"
            f"💎 Confidence: {s.confidence:.1f}% ({tier})\n"
            f"📌 Entry: ${s.entry:,.6f}\n"
            f"🛑 SL: ${s.sl:,.6f}\n"
            f"🎯 TP1: ${s.tp1:,.6f} | TP2: ${s.tp2:,.6f} | TP3: ${s.tp3:,.6f}\n"
            f"⚖️ Estimated RR (TP2): {rr:.2f}\n"
            f"🧾 Indicators: {indicators}\n"
            f"⏱ UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"— APEX SIGNAL™ (institutional)"
        )

    def _calc_rr(self, s: Signal) -> float:
        try:
            if s.side.upper() == "BUY":
                return (s.tp2 - s.entry) / (s.entry - s.sl) if (s.entry - s.sl) != 0 else 0.0
            else:
                return (s.entry - s.tp2) / (s.sl - s.entry) if (s.sl - s.entry) != 0 else 0.0
        except Exception:
            return 0.0

    async def _send(self, text: str, signal: Optional[Signal] = None) -> bool:
        if not self.enabled:
            logger.info("[TELEGRAM TEST MODE] %s", text.replace("\n", " | ")[:240])
            return True
        if self._in_quiet_hours():
            logger.info("Quiet hours active — compacting notification")
            # send compact message
            text = text if len(text) < 400 else text[:400] + "..."
        # Build inline buttons if signal
        reply_markup = None
        if signal and self.enabled:
            buttons = [
                [
                    InlineKeyboardButton("📈 Copy Trade", callback_data=f"copy::{signal.symbol}::{signal.entry}"),
                    InlineKeyboardButton("📊 Stats", callback_data="apex_stats"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.bot.send_message(chat_id=self.chat_id, text=text, reply_markup=reply_markup)
            )
            logger.info("✅ Telegram notification sent")
            return True
        except TelegramError as e:
            logger.warning("TelegramError sending message: %s", e)
            return False
        except Exception as e:
            logger.exception("Unexpected error sending Telegram message: %s", e)
            return False

    def send_notification(self, message: str, raw_signal: Dict[str, Any]) -> bool:
        """
        Backwards-compatible API used by engine.
        Accepts free-form message + raw signal dict (from engine).
        Converts to internal Signal and dispatches.
        """
        try:
            # Build Signal object when possible
            sig = None
            try:
                sig = Signal(
                    symbol=raw_signal.get("symbol", raw_signal.get("pair", "UNKNOWN")),
                    side=raw_signal.get("signal", raw_signal.get("side", "N/A")),
                    entry=float(raw_signal.get("price", raw_signal.get("entry", 0.0) or 0.0)),
                    sl=float(raw_signal.get("sl", raw_signal.get("stop_loss", 0.0) or 0.0)),
                    tp1=float(raw_signal.get("tp1", raw_signal.get("tps", [0.0])[0] if raw_signal.get("tps") else 0.0)),
                    tp2=float(raw_signal.get("tp2", raw_signal.get("tps", [0.0,0.0])[1] if raw_signal.get("tps") else 0.0)),
                    tp3=float(raw_signal.get("tp3", raw_signal.get("tps", [0.0,0.0,0.0])[2] if raw_signal.get("tps") else 0.0)),
                    confidence=float(raw_signal.get("confidence", 0.0)),
                    strategy_name=raw_signal.get("strategy_name", raw_signal.get("strategy", "multi")),
                    indicators=raw_signal.get("indicators", raw_signal.get("metadata", {}).get("indicators", []))
                )
            except Exception:
                logger.debug("Could not parse raw_signal into Signal; sending raw message")
                sig = None

            if sig:
                # persist trade in DB
                tier = self._tier(sig.confidence)
                rec = (sig.symbol, sig.side, sig.entry, sig.sl, sig.tp1, sig.tp2, sig.tp3, int(sig.confidence), tier, "open", datetime.utcnow().isoformat())
                trade_id = self.db.insert_trade(rec)
                # add trade id to message
                text = self._format_signal_text(sig) + f"\n\nTradeID: {trade_id}"
                asyncio.create_task(self._send(text, sig))
                return True
            else:
                asyncio.create_task(self._send(message, None))
                return True
        except Exception:
            logger.exception("send_notification failed")
            return False

    def send_heartbeat(self) -> bool:
        stats = self.db.get_stats()
        text = (
            f"🟢 APEX SIGNAL™ - HEARTBEAT\n\n"
            f"Total trades: {stats['total_trades']}\n"
            f"Closed trades: {stats['closed_trades']}\n"
            f"Total PnL: ${stats['total_pnl']:.2f}\n"
            f"UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        asyncio.create_task(self._send(text, None))
        return True

    def close_trade(self, trade_id: int, exit_price: float) -> bool:
        # compute pnl and mark closed
        cur = self.db.conn.cursor()
        cur.execute("SELECT side, entry FROM trades WHERE id = ?", (trade_id,))
        r = cur.fetchone()
        if not r:
            logger.warning("close_trade: trade id not found: %s", trade_id)
            return False
        side, entry = r
        if side.upper() == "BUY":
            pnl = exit_price - entry
        else:
            pnl = entry - exit_price
        self.db.close_trade(trade_id, round(pnl, 6))
        logger.info("Trade %s closed with PnL: %s", trade_id, pnl)
        # notify
        asyncio.create_task(self._send(f"📌 Trade {trade_id} closed. PnL: {pnl:.6f}", None))
        return True


# Factory helper compatible with old create_telegram_notifier usage
def create_telegram_notifier_from_env() -> TelegramNotifier:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    return TelegramNotifier(token=token, chat_id=chat_id)


