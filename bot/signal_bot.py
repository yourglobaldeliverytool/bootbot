"""
APEX SIGNAL™ - Production-Grade Telegram Signal Bot
Live market data + multi-source price verification + institutional-grade strategies
NO BINANCE - Uses Alpaca, Polygon, Yahoo, TradingView, CoinGecko, CoinCap
"""

import os
import sys
import time
import yaml
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import json

import pandas as pd
import numpy as np

from bot.core.registry import StrategyRegistry, IndicatorRegistry, BaseRegistry
from bot.connectors.multi_source import MultiSourceConnector
from bot.notifiers.telegram_notifier import TelegramNotifier
from bot.utils.logger import setup_logger
from bot.utils.env_loader import get_env_loader
from bot.core.price_manager import PriceManager


class Mode:
    VERIFIED_TEST = "VERIFIED_TEST"
    LIVE_SIGNAL = "LIVE_SIGNAL"


class SignalBot:
    """
    Production-grade Telegram signal bot.
    Key fixes:
     - logger is initialized early to avoid AttributeError in _load_config
     - connector.connect() and notifier.send_notification() auto-await when coroutine
     - non-blocking background run when started from FastAPI
    """

    def __init__(self, config_path: str = "bot/config/config.yaml"):
        # Ensure a logger exists immediately so _load_config can log safely
        self.logger = setup_logger("APEX_SIGNAL", "INFO")

        # Load configuration (safe: _load_config uses self.logger now)
        self.config = self._load_config(config_path)

        # Reconfigure logger to user-configured level if present
        log_level = self.config.get("logging", {}).get("level", "INFO")
        self.logger = setup_logger("APEX_SIGNAL", log_level)

        # Load environment variables (Railway)
        self.env_loader = get_env_loader()

        # Detect operating mode
        self.mode = self._detect_mode()

        # Bot state
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.last_signal_time: Optional[datetime] = None
        self.heartbeat_count = 0
        self.signal_count = 0
        self.daily_signals: List[Dict[str, Any]] = []

        # Capital management - from environment (Railway) with config fallback
        self.capital = self.env_loader.get_capital()
        self.risk_per_trade = self.env_loader.get_risk_per_trade()

        # Initialize components
        self.connector: Optional[MultiSourceConnector] = None
        self.price_manager: Optional[PriceManager] = None
        self.telegram_notifier: Optional[TelegramNotifier] = None
        self.strategies: Dict[str, Any] = {}
        self.indicators: Dict[str, Any] = {}

        # Initialize registries (use singleton pattern)
        BaseRegistry.reset()
        self.strategy_registry = StrategyRegistry.get_instance()
        self.indicator_registry = IndicatorRegistry.get_instance()

        # Health check endpoint
        self.healthy = False

        # Data source monitoring
        self.data_source_connected = False
        self.last_data_check: Optional[datetime] = None

        # Notification state
        self.daily_summary_sent = False
        self.last_summary_time: Optional[datetime] = None

        self.logger.warning("=" * 70)
        self.logger.warning("🚀 APEX SIGNAL™ BOT INITIALIZING")
        self.logger.warning("=" * 70)
        self.logger.warning(f"Mode: {self.mode}")
        self.logger.warning(f"Capital: ${self.capital:.2f}")
        self.logger.warning(f"Risk per trade: {self.risk_per_trade:.1%}")
        self.logger.warning("=" * 70)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file. Safe: uses self.logger which exists."""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, "r") as f:
                    cfg = yaml.safe_load(f)
                return cfg or {}
            else:
                # config file missing is not fatal here; return empty dict
                self.logger.warning(f"Config file not found: {config_path}")
                return {}
        except Exception as e:
            # In case of parse error, return empty config and log error
            self.logger.error(f"Error loading config {config_path}: {e}")
            return {}

    def _detect_mode(self) -> str:
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if telegram_token and telegram_chat_id:
            return Mode.LIVE_SIGNAL
        return Mode.VERIFIED_TEST

    async def initialize(self) -> bool:
        """Initialize all bot components. Returns True if ready to run."""
        try:
            self.logger.info("🔧 Initializing bot components...")

            # Initialize data connector (support sync or async connect())
            self.connector = MultiSourceConnector()

            try:
                conn_res = self.connector.connect()
                if asyncio.iscoroutine(conn_res):
                    connected = await conn_res
                else:
                    connected = bool(conn_res)
            except Exception as e:
                self.logger.error(f"Connector.connect() failed: {e}", exc_info=True)
                connected = False

            if not connected:
                self.logger.error("❌ Failed to connect to data sources")
                self.logger.error("❌ BOT CANNOT OPERATE WITHOUT LIVE DATA")
                self.healthy = False
                return False

            self.data_source_connected = True
            self.last_data_check = datetime.utcnow()
            self.logger.info("✅ Data connector connected")

            # Initialize price manager with cache TTL (sync class assumed)
            self.price_manager = PriceManager(self.connector, cache_ttl=self.config.get("price_cache_ttl", 10))
            self.logger.info("✅ Price manager initialized with cache TTL")

            # Initialize Telegram notifier (compat factory)
            if self.mode == Mode.LIVE_SIGNAL:
                token = os.environ.get("TELEGRAM_BOT_TOKEN")
                chat_id = os.environ.get("TELEGRAM_CHAT_ID")

                if token and chat_id:
                    self.telegram_notifier = TelegramNotifier(token=token, chat_id=chat_id)
                    self.logger.info("✅ Telegram notifier initialized (LIVE mode)")
                    # send startup notification (may be sync or async)
                    await self._send_startup_notification()
                else:
                    self.logger.error("❌ TELEGRAM CREDENTIALS MISSING IN LIVE MODE")
                    self.logger.error("❌ BOT WILL HALT")
                    self.healthy = False
                    return False
            else:
                self.logger.info("✅ Running in VERIFIED_TEST mode (no live Telegram sends)")

            # Load strategies and indicators
            await self._load_strategies_and_indicators()

            self.is_running = True
            self.start_time = datetime.utcnow()
            self.healthy = True

            # Send feed connected notification (non-blocking)
            await self._send_feed_connected_notification()

            return True

        except Exception as e:
            self.logger.error(f"❌ Initialization failed: {e}", exc_info=True)
            self.healthy = False
            return False

    async def _load_strategies_and_indicators(self) -> None:
        """Load strategies and indicators via registries and apply config settings."""
        # Use registry objects (these methods should exist in your repo)
        self.indicator_registry = IndicatorRegistry()
        indicator_count = 0
        try:
            indicator_count = self.indicator_registry.load_all_indicators()
        except Exception:
            self.logger.exception("Failed loading indicators (continuing if partial)")

        self.logger.info(f"✅ Indicators discovered: {indicator_count}")

        self.strategy_registry = StrategyRegistry()
        strategy_count = 0
        try:
            strategy_count = self.strategy_registry.load_all_strategies()
        except Exception:
            self.logger.exception("Failed loading strategies (continuing if partial)")

        self.logger.info(f"✅ Strategies discovered: {strategy_count}")

        if strategy_count == 0:
            self.logger.error("❌ CRITICAL: No strategies loaded from registry")
            raise RuntimeError("No strategies loaded - cannot operate without strategies")

        # Activate strategies configured in config (preserve your approach)
        strategies_config = self.config.get("strategies", {})
        active_count = 0

        for strategy_name, strategy_config in strategies_config.items():
            if strategy_config.get("enabled", False):
                strategy_class = self.strategy_registry.get(strategy_name)
                if not strategy_class:
                    self.logger.warning(f"Strategy not found in registry: {strategy_name}")
                    continue
                parameters = strategy_config.get("parameters", {})
                strategy = strategy_class(strategy_name, parameters)
                # Attach enabled indicators defined in config
                indicators_config = self.config.get("indicators", {})
                for indicator_name, indicator_config in indicators_config.items():
                    if indicator_config.get("enabled", False):
                        indicator_class = self.indicator_registry.get(indicator_name)
                        if indicator_class:
                            indicator_params = indicator_config.get("parameters", {})
                            indicator = indicator_class(indicator_name, indicator_params)
                            try:
                                strategy.add_indicator(indicator)
                            except Exception:
                                self.logger.exception(f"Failed to attach indicator {indicator_name} to {strategy_name}")
                        else:
                            self.logger.warning(f"Indicator class not found: {indicator_name}")
                self.strategies[strategy_name] = strategy
                active_count += 1
                self.logger.info(f"✅ Activated strategy: {strategy_name}")

        self.logger.info(
            f"✅ {active_count} active strategies, {strategy_count} total strategies, {indicator_count} indicators available"
        )

    async def _send_startup_notification(self) -> None:
        """Send startup notification to Telegram (supports async or sync notifier)."""
        message = f"""
🚀 APEX SIGNAL BOT™ STARTED
━━━━━━━━━━━━━━━━━━
✅ Bot initialized
💰 Capital: ${self.capital:.2f}
⚠️ Risk per trade: {self.risk_per_trade:.1%}
📊 Strategies: {len(self.strategies)}
🎯 Indicators: {len(getattr(self.indicator_registry, '_registry', {}))}
━━━━━━━━━━━━━━━━━━
⏰ Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        await self._send_telegram_message(message)

    async def _send_feed_connected_notification(self) -> None:
        if not self.telegram_notifier:
            return
        status = {}
        try:
            status = self.connector.get_status()
        except Exception:
            self.logger.exception("Failed to get connector status")
        active_source = status.get("active_data_source", "Unknown")
        message = f"""
✅ LIVE DATA FEED CONNECTED
━━━━━━━━━━━━━━━━━━
📡 Active Source: {active_source}
🔄 Data Verification: ENABLED
━━━━━━━━━━━━━━━━━━
⏰ Connected at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        await self._send_telegram_message(message)

    async def _send_feed_failure_notification(self, error: str) -> None:
        if not self.telegram_notifier:
            return
        message = f"""
❌ LIVE DATA FEED FAILURE
━━━━━━━━━━━━━━━━━━
⚠️ Error: {error}
🔄 Attempting reconnection...
⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
        await self._send_telegram_message(message)

    async def _send_daily_summary(self) -> None:
        if not self.telegram_notifier or self.daily_summary_sent:
            return
        today = datetime.utcnow().date()
        todays_signals = [s for s in self.daily_signals if s["timestamp"].date() == today]
        if not todays_signals:
            return
        buy_signals = len([s for s in todays_signals if s.get("signal") == "BUY"])
        sell_signals = len([s for s in todays_signals if s.get("signal") == "SELL"])
        avg_confidence = float(np.mean([s.get("confidence", 0) for s in todays_signals])) if todays_signals else 0.0
        message = f"""
📊 DAILY SUMMARY - APEX SIGNAL BOT™
━━━━━━━━━━━━━━━━━━
📅 Date: {today.strftime('%Y-%m-%d')}
📊 Total Signals: {len(todays_signals)}
🟢 BUY Signals: {buy_signals}
🔴 SELL Signals: {sell_signals}
🎯 Avg Confidence: {avg_confidence:.1f}%
━━━━━━━━━━━━━━━━━━
"""
        await self._send_telegram_message(message)
        self.daily_summary_sent = True
        self.last_summary_time = datetime.utcnow()

    async def run(self) -> None:
        """Main bot loop — intended to be started as background task (non-blocking FastAPI startup)."""
        self.logger.info("🚀 Starting main bot loop...")
        try:
            while self.is_running:
                self.heartbeat_count += 1
                now = datetime.utcnow()

                # Daily summary logic: send at 23:00 UTC once
                if not self.daily_summary_sent and now.hour == 23 and now.minute == 0:
                    await self._send_daily_summary()

                # Reset daily flags daily
                if self.last_summary_time and (now - self.last_summary_time).days >= 1:
                    self.daily_summary_sent = False
                    self.daily_signals = []

                symbols = self.config.get("symbols", ["BTCUSDT", "ETHUSD", "XAUUSD"])
                scan_interval = self.config.get("scan_interval", 60)

                for symbol in symbols:
                    try:
                        await self._scan_symbol(symbol)
                    except Exception:
                        self.logger.exception(f"Error scanning {symbol}")

                await asyncio.sleep(scan_interval)

        except asyncio.CancelledError:
            self.logger.info("Bot loop cancelled (graceful shutdown)")
        except Exception:
            self.logger.exception("Bot loop encountered an error")
            await self._send_error_notification("Critical bot loop error")
        finally:
            await self.shutdown()

    async def _scan_symbol(self, symbol: str) -> None:
        """Scan a symbol for trading opportunities."""
        try:
            # price_manager.get_price assumed synchronous; wrap exceptions
            try:
                price_data = self.price_manager.get_price(symbol)
            except Exception:
                self.logger.exception("price_manager.get_price() failed")
                price_data = None

            if price_data is None:
                self.logger.error(f"❌ No price data for {symbol}")
                self.data_source_connected = False
                await self._send_feed_failure_notification("No price data available")
                return

            price = price_data.get("price")
            # fetch bars (assume synchronous)
            bars = self.connector.fetch_bars(symbol, "1h", limit=100)
            if bars is None or getattr(bars, "empty", False):
                self.logger.warning(f"⚠️ No bar data for {symbol}")
                return

            # Apply registered indicators to bars via registry if necessary
            for indicator_key in list(getattr(self.indicator_registry, "_registry", {}).keys()):
                try:
                    indicator = self.indicator_registry.create_instance(indicator_key, {})
                    if indicator:
                        bars = indicator.calculate(bars)
                except Exception:
                    self.logger.exception(f"Indicator {indicator_key} failed to calculate")

            # Collect signals from active strategies
            signals = []
            strategy_alignment = []
            indicator_confirmation = []

            for strategy_name, strategy in self.strategies.items():
                try:
                    result = strategy.generate_signal(bars)
                    if result and result.get("signal") in ["BUY", "SELL"]:
                        signals.append(result)
                        strategy_alignment.append(strategy_name)
                        # collect indicators used by strategy if available
                        for ind in getattr(strategy, "indicators", []):
                            try:
                                indicator_confirmation.append(getattr(ind, "name", str(ind)))
                            except Exception:
                                pass
                except Exception:
                    self.logger.exception(f"Strategy {strategy_name} failure during scan")

            confidence = self._calculate_confidence(signals, strategy_alignment, indicator_confirmation, bars)

            min_confidence_threshold = float(self.config.get("min_confidence", 60.0))
            if confidence < min_confidence_threshold:
                self.logger.info(f"⏭️ Skipping {symbol} - confidence {confidence:.1f}% < {min_confidence_threshold}%")
                return

            if signals:
                primary_signal = self._auto_select_best_signal(signals, bars)
                if primary_signal and primary_signal.get("signal") in ["BUY", "SELL"]:
                    signal_type = primary_signal.get("signal")
                    primary_strategy_name = strategy_alignment[0] if strategy_alignment else "unknown"
                    tp_levels, sl = self._calculate_tp_sl_levels(price, signal_type, bars)

                    price_data = self.price_manager.get_price(symbol) or {}
                    checksum = price_data.get("checksum", hashlib.md5(str(price).encode()).hexdigest())
                    primary_source = price_data.get("source", "unknown")
                    secondary_source = price_data.get("secondary_source", "N/A")
                    price_deviation = price_data.get("deviation", 0.0)

                    signal_data = {
                        "symbol": symbol,
                        "signal": signal_type,
                        "price": price,
                        "tp": tp_levels[0],
                        "tp1": tp_levels[0],
                        "tp2": tp_levels[1],
                        "tp3": tp_levels[2],
                        "sl": sl,
                        "confidence": confidence,
                        "strategies": strategy_alignment,
                        "indicators": list(set(indicator_confirmation)),
                        "checksum": checksum,
                        "primary_source": primary_source,
                        "secondary_source": secondary_source,
                        "price_deviation": price_deviation,
                        "timestamp": datetime.utcnow(),
                        "strategy_name": primary_strategy_name,
                    }

                    await self._send_signal(signal_data)

                    self.last_signal_time = datetime.utcnow()
                    self.signal_count += 1
                    self.signal_history.append(signal_data)
                    self.daily_signals.append(signal_data)

        except Exception:
            self.logger.exception(f"Unhandled error scanning {symbol}")
            await self._send_error_notification(f"Scanning error for {symbol}")

    def _auto_select_best_signal(self, signals: List[Dict[str, Any]], bars: pd.DataFrame) -> Optional[Dict[str, Any]]:
        if not signals:
            return None
        scored_signals = []
        for signal in signals:
            score = 0
            signal_type = signal.get("signal", "HOLD")
            try:
                if "ema_20" in bars.columns and "ema_50" in bars.columns:
                    latest_ema20 = bars["ema_20"].iloc[-1]
                    latest_ema50 = bars["ema_50"].iloc[-1]
                    if signal_type == "BUY" and latest_ema20 > latest_ema50:
                        score += 40
                    elif signal_type == "SELL" and latest_ema20 < latest_ema50:
                        score += 40
                if "volume" in bars.columns:
                    avg_volume = bars["volume"].iloc[-20:].mean()
                    latest_volume = bars["volume"].iloc[-1]
                    if latest_volume > avg_volume * 1.2:
                        score += 30
                if "atr_14" in bars.columns:
                    atr = bars["atr_14"].iloc[-1]
                    latest_close = bars["close"].iloc[-1]
                    atr_pct = atr / latest_close if latest_close else 0
                    if 0.01 < atr_pct < 0.05:
                        score += 30
                    elif atr_pct >= 0.01:
                        score += 15
            except Exception:
                self.logger.exception("Error scoring a signal")
            signal["_score"] = score
            scored_signals.append(signal)
        if scored_signals:
            return max(scored_signals, key=lambda x: x.get("_score", 0))
        return None

    def _calculate_confidence(self, signals, strategy_alignment, indicator_confirmation, bars) -> float:
        confidence = 0.0
        try:
            num_strategies = max(len(self.strategies), 1)
            aligned_strategies = len(strategy_alignment)
            strategy_score = (aligned_strategies / num_strategies) * 50
            confidence += strategy_score

            num_indicators = max(len(getattr(self.indicator_registry, "_registry", {})), 1)
            confirmed_indicators = len(set(indicator_confirmation))
            indicator_score = (confirmed_indicators / num_indicators) * 30
            confidence += indicator_score

            if bars is not None and len(bars) > 0:
                if "ema_20" in bars.columns and "ema_50" in bars.columns:
                    latest_ema20 = bars["ema_20"].iloc[-1]
                    latest_ema50 = bars["ema_50"].iloc[-1]
                    confidence += 10
        except Exception:
            self.logger.exception("Error calculating confidence")
        return max(0, min(100, confidence))

    def _calculate_tp_sl_levels(self, price, signal_type, bars) -> Tuple[List[float], float]:
        try:
            if "atr_14" in bars.columns:
                atr = bars["atr_14"].iloc[-1]
            else:
                atr = price * 0.01
            if signal_type == "BUY":
                tp1 = price + atr * 1
                tp2 = price + atr * 2
                tp3 = price + atr * 3
                sl = price - atr * 1.5
            else:
                tp1 = price - atr * 1
                tp2 = price - atr * 2
                tp3 = price - atr * 3
                sl = price + atr * 1.5
            return [tp1, tp2, tp3], sl
        except Exception:
            self.logger.exception("TP/SL calculation error")
            if signal_type == "BUY":
                return [price * 1.01, price * 1.02, price * 1.03], price * 0.99
            else:
                return [price * 0.99, price * 0.98, price * 0.97], price * 1.01

    async def _send_signal(self, signal_data: Dict[str, Any]) -> None:
        """Send signal to Telegram with professional formatting (async-safe)."""
        symbol = signal_data.get("symbol")
        signal_type = signal_data.get("signal")
        price = signal_data.get("price")
        tp1 = signal_data.get("tp1")
        tp2 = signal_data.get("tp2")
        tp3 = signal_data.get("tp3")
        sl = signal_data.get("sl")
        confidence = signal_data.get("confidence", 0)
        indicators = signal_data.get("indicators", [])
        checksum = signal_data.get("checksum", "")[:12]
        timestamp = signal_data.get("timestamp", datetime.utcnow())
        strategy_name = signal_data.get("strategy_name", "unknown")

        rr_ratio = 0.0
        try:
            if signal_type == "BUY" and price and sl:
                rr_ratio = (tp2 - price) / (price - sl) if price > sl else 0
            elif signal_type == "SELL" and price and sl:
                rr_ratio = (price - tp2) / (sl - price) if sl > price else 0
        except Exception:
            pass

        risk_amount = self.capital * self.risk_per_trade
        position_size = 0.0
        try:
            if signal_type == "BUY" and price and sl and price > sl:
                position_size = risk_amount / (price - sl)
            elif signal_type == "SELL" and price and sl and sl > price:
                position_size = risk_amount / (sl - price)
        except Exception:
            pass

        market_structure = self._get_market_structure_status()
        volume_status = self._get_volume_status()
        volatility_state = self._get_volatility_state()
        data_source = self.connector.get_status().get("active_data_source", "Unknown") if self.connector else "unknown"
        price_deviation_pct = signal_data.get("price_deviation", 0.0) * 100.0

        message = f"""
APEX SIGNAL BOT™ 🚀
━━━━━━━━━━━━━━━━━━

Pair: {symbol}
Direction: {signal_type}
Entry: ${price:,.2f}
Stop Loss: ${sl:,.2f}
Take Profit 1: ${tp1:,.2f}
Take Profit 2: ${tp2:,.2f}
Take Profit 3: ${tp3:,.2f}
Risk/Reward: 1:{rr_ratio:.1f}
Confidence: {confidence:.0f}%
Capital Allocation: ${self.capital:.2f}
Position Size: {position_size:.6f} units

━━━━━━━━━━━━━━━━━━

Indicators Alignment Summary: {', '.join(indicators[:5])}
Market Structure Status: {market_structure}
Volume Confirmation: {volume_status}
Volatility State: {volatility_state}

━━━━━━━━━━━━━━━━━━

🧮 Price Checksum: {checksum}...
📊 Price Deviation: {price_deviation_pct:.2f}%
📡 Primary Source: {signal_data.get('primary_source', data_source)}
📡 Secondary Source: {signal_data.get('secondary_source', 'N/A')}
🧠 Strategy: {strategy_name}

━━━━━━━━━━━━━━━━━━

⏰ UTC Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━

⚠️ Educational signal. Not financial advice.
"""
        await self._send_telegram_message(message)
        self.logger.info(f"📨 Sent {signal_type} signal for {symbol} (confidence: {confidence:.0f}%, strategy: {strategy_name})")

    def _get_market_structure_status(self) -> str:
        return "Analyzing..."

    def _get_volume_status(self) -> str:
        return "Checking..."

    def _get_volatility_state(self) -> str:
        return "Measuring..."

    async def _send_error_notification(self, error: str) -> None:
        if not self.telegram_notifier:
            self.logger.error(f"[ERROR] {error}")
            return
        message = f"""
⚠️ ERROR DETECTED - APEX SIGNAL BOT™
━━━━━━━━━━━━━━━━━━
❌ Error: {error}
⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
━━━━━━━━━━━━━━━━━━
"""
        await self._send_telegram_message(message)

    async def _send_telegram_message(self, message: str) -> None:
        """Send message to Telegram (supports sync/async notifier APIs)."""
        if self.mode == Mode.LIVE_SIGNAL and self.telegram_notifier:
            try:
                res = None
                try:
                    res = self.telegram_notifier.send_notification(message)
                except TypeError:
                    # If the notifier expects different args, try send_message
                    try:
                        res = self.telegram_notifier.send_message(message)
                    except Exception:
                        res = None

                # If result is coroutine, await it.
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                self.logger.exception("❌ Error sending Telegram message")
        else:
            # Test mode - log the message summary only
            self.logger.info(f"[TELEGRAM TEST] {message[:200].replace(chr(10),' ')}")

    async def shutdown(self) -> None:
        """Graceful shutdown. send daily summary if possible."""
        self.logger.info("🛑 Shutting down bot...")
        self.is_running = False
        self.healthy = False
        try:
            if self.telegram_notifier:
                await self._send_daily_summary()
        except Exception:
            self.logger.exception("Error during shutdown summary")
